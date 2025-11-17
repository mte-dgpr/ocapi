import argparse
from pathlib import Path
import networkx as nx
from typing import Set, List

from permis.scripts.constants import FULL_SECTION, PROJECT_ROOT
from permis.scripts.types import Content, Operation, OperationTrace, NodeId


DEFAULT_IN_PATH = PROJECT_ROOT / "permis" / "data" / "0005804239" / "graphs" / "op_graph.graphml"


def load_graph(in_path: Path) -> nx.DiGraph:
    """
    Charge le graphe d'opérations depuis un fichier GraphML.
    
    Returns:
        nx.DiGraph: Le graphe chargé
    """
    G = nx.read_graphml(in_path)
    return G


def get_source_nodes(G: nx.DiGraph) -> Set[NodeId]:
    """
    Retourne les nœuds sources (out-degree > 0, in-degree == 0).
    Ce sont les opérations sans dépendances à résoudre en premier.
    
    Returns:
        Set[NodeId]: Ensemble des identifiants de nœuds sources
    """
    return {n for n, d in G.out_degree() if d > 0 and G.in_degree(n) == 0}


def apply_operation(operation: Operation, input_content: Content) -> OperationTrace:
    """
    Applique une opération unique sur un contenu donné.
    Délègue à apply_replace, apply_remove ou apply_add selon op_type.
    
    Args:
        operation: L'opération à appliquer
        input_content: Le contenu avant modification
        
    Returns:
        OperationTrace: Trace avec input, output et operation_id
    """
    if operation.op_type == "REPLACE":
        output = apply_replace(operation, input_content)
    elif operation.op_type in ["DELETE", "ABROGATION"]:
        output = apply_remove(operation, input_content)
    elif operation.op_type == "ADD":
        output = apply_add(operation, input_content)
    else:
        raise ValueError(f"Type d'opération inconnu: {operation.op_type}")

    return OperationTrace(
        input=input_content,
        output=output,
        operation=operation.id,
    )


def apply_replace(operation: Operation, input: Content) -> Content:
    """
    Applique une opération REPLACE.
    Si sub_target == FULL_SECTION, remplace tout.
    Sinon, remplace la partie ciblée (TODO: LLM).
    
    Returns:
        Content: Le contenu modifié
    """
    if operation.sub_target == FULL_SECTION:
        output = operation.new_content
    else:
        # TODO: gérer le remplacement partiel (LLM ?)
        output = input

    return output


def apply_remove(operation: Operation, input: Content) -> Content:
    """
    Applique une opération REMOVE.
    Retire la partie ciblée ou marque l'article comme abrogé.
    
    Returns:
        Content: Le contenu modifié
    """
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
    # TODO: implémenter la logique d'ajout
    output = input  # Placeholder
    return output


def process_pass(G: nx.DiGraph, source_nodes: Set[NodeId]) -> List[OperationTrace]:
    """
    Traite une passe complète : applique toutes les opérations des nœuds sources,
    collecte les traces, puis supprime ces nœuds et edges du graphe.
    
    Args:
        G: Le graphe (modifié in-place)
        source_nodes: Les nœuds à traiter dans cette passe
        
    Returns:
        List[OperationTrace]: Les traces d'application pour cette passe
    """
    traces = []
    for node in source_nodes:
        operation = G.nodes[node]["operation"]
        input_content = G.nodes[node]["content"]
        trace = apply_operation(operation, input_content)
        traces.append(trace)
        # Mettre à jour le contenu des nœuds cibles
        for succ in G.successors(node):
            G.nodes[succ]["content"] = trace.output
        # TODO : mettre à jour l'operand des opérations changées


        # Suppression du noeud traité
        G.remove_node(node)


    return traces


def apply_all_operations(G: nx.DiGraph) -> List[OperationTrace]:
    """
    Applique toutes les opérations du graphe par passes successives.
    À chaque passe :
      1. Identifie les nœuds sources (sans dépendances)
      2. Les traite avec process_pass
      3. Continue jusqu'à ce que le graphe soit vide
      
    Returns:
        List[OperationTrace]: Toutes les traces d'application, dans l'ordre
    """
    all_traces = []
    while len(G) > 0:
        source_nodes = get_source_nodes(G)
        traces = process_pass(G, source_nodes)
        all_traces.extend(traces)

    return all_traces


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