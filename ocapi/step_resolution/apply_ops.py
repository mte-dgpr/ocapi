from bs4 import BeautifulSoup
import networkx as nx

from ocapi.types import ArreteFile, ArticlesContentMap, Content, Operation, NodeId, ArreteId, OperationType
from ocapi.utils.llm_utils import call_llm_api, query_llm_for_subtarget
from ocapi.step_detection.subtarget_detection import SubTarget, is_simple_subtarget, parse_subtarget, replace_subtarget

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


def apply_replace(subtarget: SubTarget, operand: Content, tgt_content: Content) -> Content:
    """
    """
    parsed = parse_subtarget(subtarget)
    if is_simple_subtarget(parsed):
        soup = BeautifulSoup(tgt_content, "html.parser")
        modified_soup = replace_subtarget(soup, parsed, operand)
        return str(modified_soup)   
    else:
        prompt = query_llm_for_subtarget(OperationType.REPLACE, tgt_content, subtarget)
        raw = call_llm_api(prompt)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", operand)
                break
        return output


def apply_remove(operation: Operation, input: Content) -> Content:
    """
    Applique une opération REMOVE.
    Retire la partie ciblée ou marque l'article comme abrogé.
    
    Returns:
        Content: Le contenu modifié
    """
    parsed = parse_subtarget(operation.sub_target)
    if is_simple_subtarget(parsed):
        soup = BeautifulSoup(input, "html.parser")
        modified_soup = replace_subtarget(soup, parsed, "")
        return str(modified_soup)   
    else:
        prompt = query_llm_for_subtarget(OperationType.REMOVE, input, operation.sub_target)
        raw = call_llm_api(prompt)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", "")
                break
        return output


def apply_add(operation: Operation, input: Content) -> Content:
    """
    Applique une opération ADD.
    Insère un nouveau passage ou article (peut nécessiter renumérotation).
    
    Returns:
        Content: Le contenu modifié
    """    
    parsed = parse_subtarget(operation.sub_target)
    if is_simple_subtarget(parsed):
        soup = BeautifulSoup(input, "html.parser")
        # TODO : implementer add? 
    else:
        prompt = query_llm_for_subtarget(OperationType.ADD, input, operation.sub_target)
        raw = call_llm_api(prompt)
        for line in raw.splitlines():
            if "<NEWCONTENT>" in line:
                output = line.replace("<NEWCONTENT>", operation.operand)
                break
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
            if op.operation_type == "REPLACE":
                output = apply_replace(op, input_content)
            elif op.operation_type in ["DELETE", "ABROGATION"]:
                output = apply_remove(op, input_content)
            elif op.operation_type == "ADD":
                output = apply_add(op, input_content)
            else:
                raise ValueError(f"Type d'opération inconnu: {op.operation_type}")
            output_content_map[tgt] = output

    return output_content_map

def apply_all_operations(
        operations_graph: nx.MultiDiGraph, 
        arrete_list: list[ArreteFile], 
        initial_articles_content_map: ArticlesContentMap
    ) -> list[ArticlesContentMap]:

    articles_content_map : ArticlesContentMap = initial_articles_content_map
    versions: list[ArticlesContentMap] = [articles_content_map]
    for arrete_file in arrete_list :
        subG = build_subgraph(operations_graph, arrete_file.id)
        articles_content_map = apply_subgraph_operations(subG, articles_content_map)
        versions.append(articles_content_map)
    
    return versions


def build_initial_articles_content_map(operations_graph: nx.MultiDiGraph, arrete_files: list[ArreteFile]) -> ArticlesContentMap:
    articles_content_map : ArticlesContentMap = {}
    soups : dict[ArreteId, BeautifulSoup] = {
        arrete_file.id: arrete_file.soup for arrete_file in arrete_files}
    for node in operations_graph.nodes:
        if operations_graph.in_degree(node) != 0:
            arrete_id, article_id = parse_node_id(node)
            soup = soups[arrete_id]
            section_tag = soup.select_one(f"section.arretify-section[data-num='{article_id}']")
            if section_tag is None: 
                raise ValueError(f"Section {article_id} not found in arrete {arrete_id}")
            articles_content_map[node] = str(section_tag)

    return articles_content_map


def build_subgraph(operations_graph: nx.MultiDiGraph, arrete_id: ArreteId) -> nx.MultiDiGraph:

    filtered_nodes: set[NodeId] = set()
    for node in operations_graph.nodes:
        node_arrete_id, _ = parse_node_id(node)

        if node_arrete_id == arrete_id:
            filtered_nodes.add(node)
            for node in operations_graph.successors(node):
                filtered_nodes.add(node)
    return operations_graph.subgraph(filtered_nodes).copy()


def parse_node_id(node_id_str: str) -> tuple[NodeId, ArreteId]:
    parts = node_id_str.split("::")
    arrete_id = parts[0]
    article_id = parts[1] if len(parts) > 1 else None
    return arrete_id, article_id





