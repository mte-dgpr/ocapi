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

import networkx as nx

from ocapi.types import NodeId, Operation


def add_node(G: nx.MultiDiGraph, node_id: NodeId) -> None:
    if not G.has_node(node_id):
        G.add_node(node_id)


def add_edge(G: nx.MultiDiGraph, operation: Operation) -> None:
    edge_data = operation.model_dump(
        exclude={"source_id", "target_id"}, exclude_none=True, mode="json"
    )
    G.add_edge(operation.source_id, operation.target_id, **edge_data)


def build_graph(ops: list[Operation]) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for op in ops:
        add_node(G, op.source_id)
        add_node(G, op.target_id)
        add_edge(G, op)
    return G
