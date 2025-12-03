"""
Construire un graphe de dépendances d'opérations à partir des fichiers
operations_mapped/*.mapped.json.

- noeud : article (préférer uid si présent, sinon fallback "doc::ref")
- arête : opération dirigée source -> target, attributs = op_id, type, source_file, target_file
- sortie : graphml + gpickle + résumé console

Usage (depuis la racine du repo) :
  python permis/scripts/3_consolidation/build_op_graph.py
Options :
  --input DIR  ; dossier contenant les *.mapped.json
  --out DIR    ; dossier de sortie pour graphes (par défaut data/.../graphs)
"""

# TODO: comment gérer les parents enfant dans le graphe au niveau des dépendances

# TODO: Comment gérer edges avec même src / target ? adapter en multigraph ?



import networkx as nx

from ocapi.types import NodeId, Operation

OPERATION_EDGE_ATTRS = {"id", "operation_type", "operand", "sub_target"}

def add_node(G: nx.MultiDiGraph, node_id: NodeId):
    # TODO : ajouter le contenu si possible
    if not G.has_node(node_id):
        G.add_node(node_id)

def add_edge(G: nx.MultiDiGraph, operation: Operation):
    edge_data = operation.model_dump(include=OPERATION_EDGE_ATTRS)
    # TODO : ne fonctionne pas 
    G.add_edge(operation.source_id, operation.target_id, **edge_data)


def build_graph(ops: list[Operation]) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for op in ops:
        add_node(G, op.source_id)
        add_node(G, op.target_id)
        add_edge(G, op)
    return G

