import argparse
from pathlib import Path
import networkx as nx
from typing import Set, List

from permis.scripts.constants import FULL_SECTION, PROJECT_ROOT
from permis.scripts.types import Content, Operation, OperationTrace, NodeId, OperationId


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
        id=data["operation_id"],
        source_uid=src,
        target_uid=tgt,
        op_type=data["operation"],
        operand=data.get("operand", None),
        sub_target=data.get("sub_target", None),
    )
    return operation

def get_next_ops(G: nx.DiGraph) -> list[Operation]:
    """
    Retourne les opérations à traiter à la prochaine passe. Deux cas : 
        - les opérations sans conflit (target.in-degree == 1)
        - les opérations en conflit (target.in-degree > 1) où toutes les sources sont déjà traitées (source.in-degree == 0)
    
    Returns:
        Set[tuple]: liste des edges (src, tgt, key) à traiter
    """
    # TODO : prendre arrete par arrete ? pour traiter tt les modifs d'un arrete en meme temps 
    next_ops = []
    for src, tgt, key in G.edges(keys=True, data=True):
        if G.in_degree(src)==0 and G.in_degree(tgt) == 1:
            next_ops.append(_edge_to_operation(G,src, tgt, key))
        elif G.in_degree(tgt) > 1:
            all_sources_processed = all(
                G.in_degree(pred) == 0 for pred in G.predecessors(tgt)
            )
            if all_sources_processed:
                next_ops.append(_edge_to_operation(G,src, tgt, key))
    return next_ops

def apply_operations(ops: list[Operation], input_content: Content) -> OperationTrace:
    """
    Applique une opération unique sur un contenu donné.
    Délègue à apply_replace, apply_remove ou apply_add selon op_type.
    
    Args:
        operation: L'opération à appliquer
        input_content: Le contenu avant modification
        
    Returns:
        OperationTrace: Trace avec input, output et operation_id
    """
    initial_input = input_content
    for op in ops:
        if op.op_type == "REPLACE":
            output = apply_replace(op, input_content)
        elif op.op_type in ["DELETE", "ABROGATION"]:
            output = apply_remove(op, input_content)
        elif op.op_type == "ADD":
            output = apply_add(op, input_content)
        else:
            raise ValueError(f"Type d'opération inconnu: {op.op_type}")
        input_content = output

    return OperationTrace(
        input=initial_input,
        output=output,
        operations=[op.id for op in ops],
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


def process_pass(G: nx.DiGraph, pass_ops) -> List[OperationTrace]:
    """
    Traite une passe complète : applique toutes les opérations des nœuds sources,
    collecte les traces, mets à jour les operand des tgt, puis supprime ces nœuds et edges du graphe.
    TODO gérer abrogation ? 
    
    Args:
        G: Le graphe (modifié in-place)
        pass_ops: Les edges (src, tgt, key) à traiter dans cette passe
        
    Returns:
        List[OperationTrace]: Les traces d'application pour cette passe
    """
    traces = []
    for operation in pass_ops:
        filtered_traces = 
        input_content = get_node_content(G, operation.target_uid) # ajouter le contenu html dans les noeuds ? 
        
        trace = apply_operations(operation, input_content)
        traces.append(trace)
        
        # Mettre à jour le contenu du nœud cible
        G.nodes[tgt]["content"] = trace.output
        if G.out_degree(tgt) > 1:
            G.nodes[tgt]["content"] = update_operand(trace.output)
        
        # TODO : mettre à jour l'operand des opérations affectées

        # Suppression de l'edge traité
        G.remove_edge(src, tgt, key)
        
        # Si le nœud source n'a plus d'edges sortants, le supprimer
        if G.out_degree(src) == 0:
            G.remove_node(src)

    return traces

def update_operand(new_content: Content) -> Content:
    """
    Met à jour l'operand avec le nouveau contenu.
    Args:
        new_content: Le contenu modifié
        
    Returns:
        Content: Le nouvel operand
    """
    return new_content

def get_node_content(G: nx.DiGraph, node_id: NodeId) -> Content:
    """
    Récupère le contenu html associé à l'identifiant du nœud dans le graphe.
    Args:
        G: Le graphe
        node_id: L'identifiant du nœud
        
    Returns:
        html 
    """
    pass

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
        pass_ops = get_next_ops(G)
        traces = process_pass(G, pass_ops)
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