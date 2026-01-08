"""
Ce fichier contient des fonctions pour construire un graphe orienté des opérations
à partir d'une liste d'opérations.
Chaque nœud du graphe représente un article d'arrêté, et chaque arête représente une opération
entre deux articles.
"""
# TODO: gérer les dépendances parents-enfant dans le graphe (articles imbriqués)
# TODO : VITE -- si erreur de détection d'une section SOURCE, c'est ok on essaie de pas skip. skip une op pour source que si ERROR EXTRACTING CONTENT

from typing import Tuple
from bs4 import BeautifulSoup
import networkx as nx
from ocapi.types import ArreteFile, ArreteId, NodeId, Operation

def add_node(G: nx.MultiDiGraph, node_id: NodeId):
    if not G.has_node(node_id):
        G.add_node(node_id)

def add_edge(G: nx.MultiDiGraph, operation: Operation):
    edge_data = operation.model_dump(exclude={"source_id", "target_id"}, exclude_none=True)
    G.add_edge(operation.source_id, operation.target_id, **edge_data)


def add_node_content(node:NodeId, soup:BeautifulSoup):
    arrete_id, article_id = node.arrete_id, node.article_id
    
    # Cas spécial : NEW_ARTICLE (article qui n'existe pas encore, sera créé par l'opération)
    if article_id.startswith("NEW_ARTICLE"):
        node.content = ""
        return node
    
    # Si l'article_id commence par APPENDIX, on essaie de récupérer le contenu de l'appendice
    if article_id.startswith("APPENDIX"):
        article_id = article_id.split("APPENDIX:", 1)[1]
        appendix_tag = soup.select_one('footer[data-spec="appendix"]')
        if appendix_tag is None:
            raise ValueError(f"Section {article_id} not found in arrete {arrete_id}")
        else:
            section_tag = appendix_tag.select_one(f'section[data-spec="section"][data-number="{article_id}"]')
            if section_tag is None:
                raise ValueError(f"Section {article_id} not found in Appendix of arrete {arrete_id}")
            node.content = str(section_tag)
        return node

    section_tag = soup.select_one(f'section[data-spec="section"][data-number="{article_id}"]')
    if section_tag is None: 
        raise ValueError(f"Section {article_id} not found in arrete {arrete_id}")
    node.content = str(section_tag)
    return node
    

def build_graph(ops: list[Operation], arrete_files: list[ArreteFile]) -> Tuple[nx.MultiDiGraph, list[ArreteFile], list[tuple[Operation, str]]]:
    """
    Construit le graphe des opérations.
    Retourne le graphe, la liste des arrêtés, et la liste des opérations qui ont échoué.
    """
    G = nx.MultiDiGraph()
    soups : dict[ArreteId, BeautifulSoup] = {
        arrete_file.id: arrete_file.soup for arrete_file in arrete_files}
    skipped_ops: list[tuple[Operation, str]] = []  # Liste des opérations qui ont échoué avec la raison
    
    for op in ops:
        try:
            if _is_abrogation_arrete(op):
                # Trouver l'arrêté dans la liste et marquer son status comme False
                for arrete_file in arrete_files:
                    if arrete_file.id == op.target_id.arrete_id:
                        arrete_file.status = False
                        break
                continue
            source_soup = soups[op.source_id.arrete_id]
            target_soup = soups[op.target_id.arrete_id]
            op.source_id=add_node_content(op.source_id, source_soup)
            op.target_id=add_node_content(op.target_id, target_soup)
            add_node(G, op.source_id)
            add_node(G, op.target_id)
            add_edge(G, op)
        except Exception as e:
            error_msg = f"⚠️  Opération {op.id} ignorée: {str(e)}"
            print(error_msg)
            skipped_ops.append((op, str(e)))
            continue
    
    if skipped_ops:
        print(f"\n⚠️  {len(skipped_ops)} opération(s) ignorée(s) lors de la construction du graphe")
    
    return G, arrete_files, skipped_ops

def _is_abrogation_arrete(operation: Operation) -> bool:
    return (operation.operation_type == "REMOVE" and 
            operation.target_id.article_id == "ALL")