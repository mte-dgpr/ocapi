"""
Ce fichier contient des fonctions pour appliquer les opérations détectées sur le contenu des articles d'arrêtés.
Chaque opération est appliquée en fonction de son type (REPLACE, REMOVE, ADD) et de sa cible (subtarget).
Lorsque la subtarget est complexe, un LLM est utilisé pour savoir où insérer le contenu modifié.
Pour chaque arrêté, un sous-graphe des opérations le concernant est construit et les opérations sont appliquées dans l'ordre.
Cela permet de construire l'historique des versions des articles modifiés au fil des modifications apportées par les opérations.
"""
from bs4 import BeautifulSoup
import networkx as nx

from ocapi.types import ArreteFile, Content, Operation, NodeId, ArreteId, OperationId, OperationType, ArticleHistory, ArticleVersion  
from ocapi.utils.llm_utils import call_llm_api, query_llm_for_subtarget
from ocapi.step_detection.subtarget_detection import is_simple_subtarget, parse_subtarget, replace_subtarget

# TODO : s'assurer qu'à la création de ArticleHistory, on initialise bien avec la version 0 (contenu initial) de chaque article.

def _edge_to_operation(operations_graph: nx.MultiDiGraph, src: NodeId, tgt: NodeId, key: int) -> Operation:
    """
    Convertit un edge du graphe en une instance Operation.
    """
    data = operations_graph[src][tgt][key]
    operation = Operation(
        id=data["id"],
        source_id=src,
        target_id=tgt,
        operation_type=data["operation_type"],
        operand=data.get("operand", None),
        sub_target=data.get("sub_target", None),
    )
    return operation


def apply_replace(operation: Operation, soup_input: BeautifulSoup) -> Content:
    if is_simple_subtarget(operation.sub_target):
        modified_soup = replace_subtarget(soup_input, operation.sub_target, operation.operand)
        return str(modified_soup)   
    else:
        prompt = query_llm_for_subtarget(OperationType.REPLACE, str(soup_input), operation.sub_target.description)
        raw = call_llm_api(prompt)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", operation.operand)
                break
        return output


def apply_remove(operation: Operation, soup_input: BeautifulSoup) -> Content:
    parsed = parse_subtarget(operation.sub_target)
    
    if is_simple_subtarget(parsed):
        modified_soup = replace_subtarget(soup_input, parsed, "")
        return str(modified_soup)   
    else:
        prompt = query_llm_for_subtarget(OperationType.REMOVE, str(soup_input), operation.sub_target.description)
        raw = call_llm_api(prompt)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", "")
                break
        return output


def apply_add(operation: Operation, soup_input: BeautifulSoup) -> Content:
    parsed = parse_subtarget(operation.sub_target)
    if is_simple_subtarget(parsed):
        pass
        # TODO : implementer add? 
    else:
        prompt = query_llm_for_subtarget(OperationType.ADD, str(soup_input), operation.sub_target.description)
        raw = call_llm_api(prompt)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", operation.operand)
                break
        return output

def apply_subgraph_operations(subG: nx.MultiDiGraph, history: ArticleHistory) -> tuple[ArticleHistory, list[tuple[OperationId, str]]]:
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
                raise NotImplementedError("Branches with multiple successors are not supported yet.")
    
        for src, tgt, key in subG.out_edges(start_node, keys=True):
            op_id = None
            try:
                op = _edge_to_operation(subG, src, tgt, key)
                op_id = op.id
                
                # Récupérer le contenu actuel (dernière version) de l'article cible
                article_key = (tgt.arrete_id, tgt.article_id)
                if article_key not in history:
                    # Initialiser l'historique avec la version 0 (contenu initial)
                    history[article_key] = [
                        ArticleVersion(version=0, content=tgt.content, operation_id=None)
                    ]
                
                current_content = history[article_key][-1]["content"]
                
                # Appliquer l'opération
                if op.operation_type == "REPLACE":
                    new_content = apply_replace(op, BeautifulSoup(current_content, "html.parser"))
                elif op.operation_type == "REMOVE":
                    new_content = apply_remove(op, BeautifulSoup(current_content, "html.parser"))
                elif op.operation_type == "ADD":
                    new_content = apply_add(op, BeautifulSoup(current_content, "html.parser"))
                else:
                    raise ValueError(f"Type d'opération inconnu: {op.operation_type}")
                
                # Ajouter la nouvelle version à l'historique
                new_version = ArticleVersion(
                    version=len(history[article_key]),
                    content=new_content,
                    operation_id=op.id
                )
                history[article_key].append(new_version)
            except Exception as e:
                error_msg = f"⚠️  Opération {op_id or 'inconnue'} ignorée: {str(e)}"
                print(error_msg)
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
        print(f"\n⚠️  {len(all_skipped_ops)} opération(s) ignorée(s) lors de l'application")
    
    return history, all_skipped_ops

def build_next_subgraph(
        operations_graph: nx.MultiDiGraph, 
        history: ArticleHistory, 
        arrete_id: ArreteId
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
        article_key = (node.arrete_id, node.article_id)
        if article_key in history and len(history[article_key]) > 0:
            latest_version = history[article_key][-1]
            new_graph.nodes[node]['content'] = latest_version["content"]
    
    return new_graph