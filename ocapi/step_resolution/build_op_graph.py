"""
Ce fichier contient des fonctions pour construire un graphe orienté des opérations
à partir d'une liste d'opérations.
Chaque nœud du graphe représente un article d'arrêté, et chaque arête représente une opération
entre deux articles.
"""
# TODO: gérer les dépendances parents-enfant dans le graphe (articles imbriqués)

import networkx as nx
from ocapi.types import NodeId, Operation

OPERATION_EDGE_ATTRS = {"id", "operation_type", "operand", "sub_target"}

def add_node(G: nx.MultiDiGraph, node_id: NodeId):
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

