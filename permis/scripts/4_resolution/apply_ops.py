import argparse
from pathlib import Path
from bs4 import BeautifulSoup
import networkx as nx
from typing import Set, List

from permis.scripts.constants import FULL_SECTION, PROJECT_ROOT
from permis.scripts.types import Content, Operation, OperationTrace, NodeId, OperationId, ArreteId
from permis.scripts.utils.llm_utils import query_llm_for_subtarget

"""
t1   t2   t3   t4 
A <- B <- C 
A            <- D
G1   G2   G3   G4 

dans G4, la branche A<- B <- C sera repliée en branche A <- C
chaque Gi n'a que des branches de taille 1

ordre chronologique mais dès qu'on détecte une branche >1, sous résolution de cette branche en remontant.
2 graphes : 1 graphe canonique et 1 graphe de résolution des conflits
sous graphe pour chaque arrêté -- snapshot temporel dans la création du graphe
construire la liste d'historiques de modifications pour chaque article

t1   t2   t3  
A <- B1
A <- B2
A       <- C

à un ti donné, on garde une seule trace. 
à chaque ti donné on a une map id_article -> contenu actuel
"""

ArticlesContentMap = dict[NodeId, Content]

DEFAULT_IN_PATH = PROJECT_ROOT / "permis" / "data" / "0005804239" / "graphs" / "op_graph.graphml"


def load_graph(in_path: Path) -> nx.DiGraph:
    """
    Charge le graphe d'opérations depuis un fichier GraphML.
    """
    G = nx.read_graphml(in_path)
    return G


def _edge_to_operation(G: nx.MultiDiGraph, src: NodeId, tgt: NodeId, key: int) -> Operation:
    """
    Convertit un edge du graphe en une instance Operation.
    """
    data = G[src][tgt][key]
    operation = Operation(
        id=data["id"],
        source_uid=src,
        target_uid=tgt,
        op_type=data["op_type"],
        operand=data.get("operand", None),
        sub_target=data.get("sub_target", None),
    )
    return operation


def apply_replace(operation: Operation, input: Content) -> Content:
    """
    Applique une opération REPLACE.
    Si sub_target == FULL_SECTION, remplace tout.
    Sinon, remplace la partie ciblée (TODO: LLM).
    
    Returns:
        Content: Le contenu modifié
    """
    if operation.sub_target == FULL_SECTION:
        return operation.operand
    else:
        
        # TODO: appel LLM 
        return output


def apply_remove(operation: Operation, input: Content) -> Content:
    """
    Applique une opération REMOVE.
    Retire la partie ciblée ou marque l'article comme abrogé.
    
    Returns:
        Content: Le contenu modifié
    """
    if operation.sub_target == FULL_SECTION:
        return ""
    # TODO: implémenter la logique de suppression ou d'abrogation
    output = input  # Placeholder
    return output


def apply_add(operation: Operation, input: Content) -> Content:
    """
    Applique une opération ADD.
    Insère un nouveau passage ou article (peut nécessiter renumérotation).
    
    Returns:
        Content: Le contenu modifié
    """    
    if operation.sub_target == FULL_SECTION:
        return operation.operand
    # TODO: implémenter la logique d'ajout
    output = input  # Placeholder
    return output


def apply_subgraph_operations(subG: nx.MultiDiGraph, articles_content_map:ArticlesContentMap) -> ArticlesContentMap:
    output_content_map = articles_content_map.copy()
    start_nodes = [node for node in subG.nodes if subG.in_degree(node) == 0]
    for start_node in start_nodes:
        for succ in subG.successors(start_node):
            if len(list(subG.successors(succ))) > 1:
                raise NotImplementedError("Branches with multiple successors are not supported yet.")
    
        for src, tgt, key in subG.out_edges(start_node, keys=True):
            op = _edge_to_operation(subG, src, tgt, key)
            input_content = output_content_map[tgt]
            if op.op_type == "REPLACE":
                output = apply_replace(op, input_content)
            elif op.op_type in ["DELETE", "ABROGATION"]:
                output = apply_remove(op, input_content)
            elif op.op_type == "ADD":
                output = apply_add(op, input_content)
            else:
                raise ValueError(f"Type d'opération inconnu: {op.op_type}")
            output_content_map[tgt] = output

    return output_content_map

def apply_all_operations(G: nx.MultiDiGraph, arrete_list: list[ArreteId], initial_articles_content_map: ArticlesContentMap) -> List[OperationTrace]:

    articles_content_map : ArticlesContentMap = initial_articles_content_map
    versions: list[ArticlesContentMap] = [articles_content_map]
    for arrete_id in arrete_list :
        subG = build_subgraph(G, arrete_id)
        articles_content_map = apply_subgraph_operations(subG, articles_content_map)
        versions.append(articles_content_map)
    
    return versions


def build_initial_articles_content_map(G: nx.MultiDiGraph, soups : dict[ArreteId,BeautifulSoup]) -> ArticlesContentMap:
    articles_content_map : ArticlesContentMap = {}
    for node in G.nodes:
        if G.in_degree(node) != 0:
            arrete_id, article_id = parse_node_id(node)
            soup = soups[arrete_id]
            section_tag = soup.select_one(f"section.arretify-section[data-num='{article_id}']")
            if section_tag is None: 
                raise ValueError(f"Section {article_id} not found in arrete {arrete_id}")
            articles_content_map[node] = str(section_tag)

    return articles_content_map


def build_subgraph(G: nx.MultiDiGraph, arrete_id: ArreteId) -> nx.MultiDiGraph:

    filtered_nodes: set[NodeId] = set()
    for node in G.nodes:
        node_arrete_id, _ = parse_node_id(node)

        if node_arrete_id == arrete_id:
            filtered_nodes.add(node)
            for node in G.successors(node):
                filtered_nodes.add(node)
    return G.subgraph(filtered_nodes).copy()


def parse_node_id(node_id_str: str) -> tuple[NodeId, ArreteId]:
    parts = node_id_str.split("::")
    arrete_id = parts[0]
    article_id = parts[1] if len(parts) > 1 else None
    return arrete_id, article_id


def main(in_path: Path):
    """
    Point d'entrée : charge le graphe, applique les opérations, sauvegarde les traces.
    """
    G = load_graph(in_path)
    traces = apply_all_operations(G)
    # TODO: sauvegarder traces dans un fichier JSON
    print(f"Applied {len(traces)} operations")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Apply operations from dependency graph in topological passes"
    )
    p.add_argument("--in", "-i", help="input graph path", default=str(DEFAULT_IN_PATH), dest="input")
    args = p.parse_args()
    main(Path(args.input))