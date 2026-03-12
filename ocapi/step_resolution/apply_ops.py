#
# Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Ce fichier contient des fonctions pour appliquer les opérations détectées
sur le contenu des articles d'arrêtés.

Chaque opération est appliquée en fonction de son type (REPLACE, REMOVE, ADD)
et de sa cible (subtarget). Lorsque la subtarget est complexe, un LLM est
utilisé pour savoir où insérer le contenu modifié.

Pour chaque arrêté, un sous-graphe des opérations le concernant est construit
et les opérations sont appliquées dans l'ordre. Cela permet de construire
l'historique des versions des articles modifiés au fil des modifications
apportées par les opérations.
"""

from typing import Literal

import networkx as nx
from bs4 import BeautifulSoup

from ocapi.types import (
    ArreteFile,
    ArreteId,
    ArticleHistory,
    ArticleVersion,
    Content,
    NodeId,
    Operation,
    OperationId,
    OperationType,
)
from ocapi.utils.llm_utils import call_llm_api, config_model_llm, query_llm_for_subtarget
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.subtarget_utils import is_simple_subtarget, replace_subtarget

_LOGGER = get_logger(__name__)
LLM_CFG = config_model_llm()


def _to_operation_type(raw_type: OperationType | str) -> OperationType:
    """
    Garantit que l'on manipule toujours une instance d'OperationType.
    """
    if isinstance(raw_type, OperationType):
        return raw_type
    raw_str = getattr(raw_type, "value", raw_type)
    return OperationType(raw_str)


def _edge_to_operation(
    operations_graph: nx.MultiDiGraph, src: NodeId, tgt: NodeId, key: int
) -> Operation:
    """
    Convertit un edge du graphe en une instance Operation.
    """
    data = operations_graph[src][tgt][key]
    op_type = _to_operation_type(data["operation_type"])
    operation = Operation(
        id=data["id"],
        source_id=src,
        target_id=tgt,
        operation_type=op_type,
        operand=data.get("operand", None),
        sub_target=data.get("sub_target", None),
        extractable_content=data.get("extractable_content", True),
    )
    return operation


def _ensure_soup(soup_input: Content | BeautifulSoup) -> BeautifulSoup:
    return (
        soup_input
        if isinstance(soup_input, BeautifulSoup)
        else BeautifulSoup(soup_input, "html.parser")
    )


def apply_replace(operation: Operation, soup_input: Content | BeautifulSoup) -> Content:
    if operation.sub_target is None or operation.operand is None:
        raise ValueError("REPLACE operations require sub_target and operand.")
    soup = _ensure_soup(soup_input)
    if is_simple_subtarget(operation.sub_target):
        try:
            modified_soup = replace_subtarget(soup, operation.sub_target, operation.operand)
            return str(modified_soup)
        except ValueError:
            # Ambiguïté détectée, fallback vers LLM
            # TODO : mettre un warning dans les logs
            pass
    # Cas complexe ou ambigu : utiliser le LLM
    prompt = query_llm_for_subtarget(
        OperationType.REPLACE, str(soup), operation.sub_target.description or ""
    )
    raw = call_llm_api(LLM_CFG, prompt)
    output = str(soup)
    for line in raw.splitlines():
        if "<NEWCONTENT>" in line:
            output = line.replace("<NEWCONTENT>", operation.operand)
            break
    return output


def apply_remove(operation: Operation, soup_input: Content | BeautifulSoup) -> Content:
    if operation.sub_target is None:
        raise ValueError("REMOVE operations require sub_target.")
    sub_target = operation.sub_target
    soup = _ensure_soup(soup_input)
    if is_simple_subtarget(sub_target):
        modified_soup = replace_subtarget(soup, sub_target, "")
        return str(modified_soup)
    else:
        prompt = query_llm_for_subtarget(
            OperationType.REMOVE, str(soup), sub_target.description or ""
        )
        raw = call_llm_api(LLM_CFG, prompt)
        output = str(soup)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", "")
                break
        return output


def apply_add(operation: Operation, soup_input: Content | BeautifulSoup) -> Content:
    if operation.sub_target is None or operation.operand is None:
        raise ValueError("ADD operations require sub_target and operand.")
    sub_target = operation.sub_target
    soup = _ensure_soup(soup_input)
    if is_simple_subtarget(sub_target):
        raise NotImplementedError("apply_add is not implemented for simple subtargets yet.")
    else:
        desc = sub_target.description or ""
        prompt = query_llm_for_subtarget(OperationType.ADD, str(soup), desc)
        raw = call_llm_api(LLM_CFG, prompt)
        output = str(soup)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", operation.operand)
                break
        return output


def apply_subgraph_operations(
    subG: nx.MultiDiGraph, history: ArticleHistory
) -> tuple[ArticleHistory, list[tuple[OperationId, str]]]:
    """
    Applique les opérations du sous-graphe et met à jour l'historique des articles.
    Pour chaque opération, ajoute une nouvelle version à l'historique de l'article cible.
    Retourne l'historique mis à jour et la liste des opérations qui ont échoué.
    """
    skipped_ops: list[tuple[OperationId, str]] = []  # Liste des (operation_id, error_message)
    start_nodes = [node for node in subG.nodes if subG.in_degree(node) == 0]
    for start_node in start_nodes:
        for succ in subG.successors(start_node):
            if len(list(subG.successors(succ))) > 1:
                raise NotImplementedError(
                    "Branches with multiple successors are not supported yet."
                )

        for src, tgt, key in subG.out_edges(start_node, keys=True):
            op_id = None
            try:
                op = _edge_to_operation(subG, src, tgt, key)
                op_id = op.id

                # Récupérer le contenu actuel (dernière version) de l'article cible
                if tgt not in history:
                    initial_content = subG.nodes[tgt].get("content", "")
                    history[tgt] = [
                        ArticleVersion(
                            version=0,
                            content=initial_content,
                            operation_id=None,
                        )
                    ]

                current_content = history[tgt][-1]["content"]

                # Appliquer l'opération.
                # Si l'operand n'a pas pu être extrait, on conserve le contenu courant.
                status_code: Literal["RESOLVED", "ERROR_EXTRACTING_CONTENT"]
                if not op.extractable_content:
                    new_content = current_content
                    status_code = "ERROR_EXTRACTING_CONTENT"
                elif op.operation_type == OperationType.REPLACE:
                    new_content = apply_replace(op, BeautifulSoup(current_content, "html.parser"))
                    status_code = "RESOLVED"
                elif op.operation_type == OperationType.REMOVE:
                    new_content = apply_remove(op, BeautifulSoup(current_content, "html.parser"))
                    status_code = "RESOLVED"
                elif op.operation_type == OperationType.ADD:
                    new_content = apply_add(op, BeautifulSoup(current_content, "html.parser"))
                    status_code = "RESOLVED"
                else:
                    raise ValueError(f"Type d'opération inconnu: {op.operation_type}")

                # Ajouter la nouvelle version à l'historique
                new_version = ArticleVersion(
                    version=len(history[tgt]),
                    content=new_content,
                    operation_id=op.id,
                )
                if status_code != "RESOLVED":
                    new_version["status_code"] = status_code
                history[tgt].append(new_version)
            except Exception as e:
                error_msg = f"Opération {op_id or 'inconnue'} ignorée: {str(e)}"
                _LOGGER.warning(error_msg)
                skipped_ops.append((op_id or "unknown", str(e)))
                continue

    return history, skipped_ops


def apply_all_ops(
    operations_graph: nx.MultiDiGraph,
    arrete_list: list[ArreteFile],
) -> tuple[ArticleHistory, list[tuple[OperationId, str]]]:
    """
    Construit l'historique complet des articles en parcourant chronologiquement les arrêtés.
    Retourne un dictionnaire {(arrete_id, article_id): [versions]} avec toutes les modifications
    et la liste des opérations qui ont échoué.
    """
    history: ArticleHistory = {}
    all_skipped_ops: list[tuple[OperationId, str]] = []

    for arrete_file in arrete_list:
        subG = build_next_subgraph(operations_graph, history, arrete_file.id)
        if subG.number_of_edges() > 0:
            history, skipped_ops = apply_subgraph_operations(subG, history)
            all_skipped_ops.extend(skipped_ops)

    if all_skipped_ops:
        _LOGGER.warning(f"{len(all_skipped_ops)} opération(s) ignorée(s) lors de l'application")

    return history, all_skipped_ops


def build_next_subgraph(
    operations_graph: nx.MultiDiGraph, history: ArticleHistory, arrete_id: ArreteId
) -> nx.MultiDiGraph:
    """
    Construit le sous-graphe des opérations définies par l'arrêté donné.
    Met à jour le contenu des nœuds avec leur dernière version depuis l'historique.
    """
    filtered_nodes: set[NodeId] = set()
    for node in operations_graph.nodes:
        node_arrete_id = node.arrete_id

        if node_arrete_id == arrete_id:
            filtered_nodes.add(node)
            for successor in operations_graph.successors(node):
                filtered_nodes.add(successor)

    new_graph = operations_graph.subgraph(filtered_nodes).copy()

    # Mettre à jour le contenu des nœuds avec leur dernière version depuis l'historique
    for node in new_graph.nodes:
        if node in history and len(history[node]) > 0:
            latest_version = history[node][-1]
            new_graph.nodes[node]["content"] = latest_version["content"]

    return new_graph
