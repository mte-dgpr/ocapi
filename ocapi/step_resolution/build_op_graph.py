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
Ce fichier contient des fonctions pour construire un graphe orienté des opérations
à partir d'une liste d'opérations.
Chaque nœud du graphe représente un article d'arrêté, et chaque arête représente une opération
entre deux articles.
"""

# TODO: gérer les dépendances parents-enfant dans le graphe (articles imbriqués)

from typing import Tuple

import networkx as nx
from bs4 import BeautifulSoup

from ocapi.types import ArreteFile, ArreteId, Content, NodeId, Operation, OperationType
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def add_node(G: nx.MultiDiGraph, node_id: NodeId, node_content: Content | None = None) -> None:
    if not G.has_node(node_id):
        node_data = {"content": node_content} if node_content is not None else {}
        G.add_node(node_id, **node_data)


def update_node_content(G: nx.MultiDiGraph, node_id: NodeId, node_content: Content) -> None:
    G.nodes[node_id]["content"] = node_content


def add_edge(G: nx.MultiDiGraph, operation: Operation) -> None:
    edge_data = operation.model_dump(
        exclude={"source_id", "target_id"}, exclude_none=True, mode="json"
    )
    G.add_edge(operation.source_id, operation.target_id, **edge_data)


def get_node_content(node: NodeId, soup: BeautifulSoup) -> str:
    """Récupère le contenu HTML d'un article à partir de son NodeId."""
    arrete_id, article_id = node.arrete_id, node.article_id

    # Cas spécial : NEW_ARTICLE (article qui n'existe pas encore, sera créé par l'opération)
    if article_id.startswith("NEW_ARTICLE"):
        return ""

    # Si l'article_id commence par APPENDIX, on essaie de récupérer le contenu de l'appendice
    if article_id.startswith("APPENDIX"):
        article_id = article_id.split("APPENDIX:", 1)[1]
        appendix_tag = soup.select_one('footer[data-spec="appendix"]')
        if appendix_tag is None:
            raise ValueError(f"Section {article_id} not found in arrete {arrete_id}")
        else:
            section_tag = appendix_tag.select_one(
                f'section[data-spec="section"][data-number="{article_id}"]'
            )
            if section_tag is None:
                raise ValueError(
                    f"Section {article_id} not found in Appendix of arrete {arrete_id}"
                )
            return str(section_tag)

    section_tag = soup.select_one(f'section[data-spec="section"][data-number="{article_id}"]')
    if section_tag is None:
        raise ValueError(f"Section {article_id} not found in arrete {arrete_id}")
    return str(section_tag)


def build_graph(
    ops: list[Operation], arrete_files: list[ArreteFile]
) -> Tuple[nx.MultiDiGraph, list[ArreteFile], list[tuple[Operation, str]]]:
    """
    Construit le graphe des opérations.
    Retourne le graphe, la liste des arrêtés, et la liste des opérations qui ont échoué.
    """
    G = nx.MultiDiGraph()
    soups: dict[ArreteId, BeautifulSoup] = {
        arrete_file.id: arrete_file.soup for arrete_file in arrete_files
    }
    skipped_ops: list[tuple[Operation, str]] = (
        []
    )  # Liste des opérations qui ont échoué avec la raison

    for op in ops:
        try:
            if _is_abrogation_arrete(op):
                # Trouver l'arrêté dans la liste et marquer son status comme False
                for arrete_file in arrete_files:
                    if arrete_file.id == op.target_id.arrete_id:
                        arrete_file.status = False
                        break
                continue
            target_soup = soups[op.target_id.arrete_id]
            # Vérifier que le contenu de l'article cible existe et le stocker dans le graphe.
            target_content = get_node_content(op.target_id, target_soup)
            add_node(G, op.source_id)
            add_node(G, op.target_id, target_content)
            add_edge(G, op)
        except Exception as e:
            error_msg = f"Opération {op.id} ignorée: {str(e)}"
            _LOGGER.warning(error_msg)
            skipped_ops.append((op, str(e)))
            continue

    if skipped_ops:
        _LOGGER.warning(
            f"{len(skipped_ops)} opération(s) ignorée(s) lors de la construction du graphe"
        )

    return G, arrete_files, skipped_ops


def _is_abrogation_arrete(operation: Operation) -> bool:
    return (
        operation.operation_type == OperationType.REMOVE and operation.target_id.article_id == "ALL"
    )
