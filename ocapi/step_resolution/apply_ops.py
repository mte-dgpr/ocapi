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

import networkx as nx
from bs4 import BeautifulSoup

from ocapi.constants import DEFAULT_LLM_MODEL
from ocapi.step_detection.subtarget_detection import is_simple_subtarget, replace_subtarget
from ocapi.types import (
    ArreteFile,
    ArreteId,
    ArticlesContentMap,
    Content,
    NodeId,
    Operation,
    OperationType,
)
from ocapi.utils.llm_utils import call_llm_api, config_model_llm, query_llm_for_subtarget

_DEFAULT_LLM_CFG = config_model_llm(DEFAULT_LLM_MODEL)


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
        modified_soup = replace_subtarget(soup, operation.sub_target, operation.operand)
        return str(modified_soup)
    else:
        prompt = query_llm_for_subtarget(
            OperationType.REPLACE, str(soup), operation.sub_target.description or ""
        )
        raw = call_llm_api(_DEFAULT_LLM_CFG, prompt)
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
        raw = call_llm_api(_DEFAULT_LLM_CFG, prompt)
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
        raw = call_llm_api(_DEFAULT_LLM_CFG, prompt)
        output = str(soup)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", operation.operand)
                break
        return output


def apply_subgraph_operations(
    subG: nx.MultiDiGraph, articles_content_map: ArticlesContentMap
) -> ArticlesContentMap:
    output_content_map = articles_content_map.copy()
    start_nodes = [node for node in subG.nodes if subG.in_degree(node) == 0]
    for start_node in start_nodes:
        for succ in subG.successors(start_node):
            if len(list(subG.successors(succ))) > 1:
                raise NotImplementedError(
                    "Branches with multiple successors are not supported yet."
                )

        for src, tgt, key in subG.out_edges(start_node, keys=True):
            op = _edge_to_operation(subG, src, tgt, key)
            op_type = _to_operation_type(op.operation_type)
            input_content = output_content_map[tgt]
            if op_type == OperationType.REPLACE:
                output = apply_replace(op, input_content)
            elif op_type == OperationType.REMOVE:
                output = apply_remove(op, input_content)
            elif op_type == OperationType.ADD:
                output = apply_add(op, input_content)
            else:
                raise ValueError(f"Type d'opération inconnu: {op_type}")
            output_content_map[tgt] = output

    return output_content_map


def apply_all_operations(
    operations_graph: nx.MultiDiGraph,
    arrete_list: list[ArreteFile],
    initial_articles_content_map: ArticlesContentMap,
) -> list[ArticlesContentMap]:

    articles_content_map: ArticlesContentMap = initial_articles_content_map
    versions: list[ArticlesContentMap] = [articles_content_map]
    for arrete_file in arrete_list:
        subG = build_subgraph(operations_graph, arrete_file.id)
        if subG.number_of_edges() > 0:
            articles_content_map = apply_subgraph_operations(subG, articles_content_map)
            versions.append(articles_content_map)

    return versions


def build_initial_articles_content_map(
    operations_graph: nx.MultiDiGraph, arrete_files: list[ArreteFile]
) -> ArticlesContentMap:
    articles_content_map: ArticlesContentMap = {}
    soups: dict[ArreteId, BeautifulSoup] = {
        arrete_file.id: arrete_file.soup for arrete_file in arrete_files
    }
    for node in operations_graph.nodes:
        if operations_graph.in_degree(node) != 0:
            arrete_id, article_id = node.arrete_id, node.article_id
            soup = soups[arrete_id]
            section_tag = soup.select_one(f"section.arretify-section[data-num='{article_id}']")
            # TODO : gérer le cas où l'article n'existe pas (article ajouté?)
            if section_tag is None:
                raise ValueError(f"Section {article_id} not found in arrete {arrete_id}")
            articles_content_map[node] = str(section_tag)

    return articles_content_map


def build_subgraph(operations_graph: nx.MultiDiGraph, arrete_id: ArreteId) -> nx.MultiDiGraph:

    filtered_nodes: set[NodeId] = set()
    for node in operations_graph.nodes:
        node_arrete_id = node.arrete_id

        if node_arrete_id == arrete_id:
            filtered_nodes.add(node)
            for successor in operations_graph.successors(node):
                filtered_nodes.add(successor)
    return operations_graph.subgraph(filtered_nodes).copy()
