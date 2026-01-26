import unittest

from .build_op_graph import build_graph

from ocapi.types import Operation, OperationType, NodeId, SubTarget, SubTargetType


class TestBuildOpGraph(unittest.TestCase):

    def test_build_graph(self):
        operations = [
            Operation(
                id="1",
                source_id=NodeId(arrete_id="APC2", article_id="1"),
                target_id=NodeId(arrete_id="APC1", article_id="2"),
                operation_type=OperationType.REPLACE,
                operand="article",
                sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
            ),
            Operation(
                id="2",
                source_id=NodeId(arrete_id="APC2", article_id="2"),
                target_id=NodeId(arrete_id="APC1", article_id="3"),
                operation_type=OperationType.REMOVE,
            ),
        ]
        G = build_graph(operations)

        assert len(G.nodes) == 4
        assert len(G.edges) == 2

        # Les clés des noeuds sont maintenant des objets NodeId
        node1 = NodeId(arrete_id="APC1", article_id="2")
        node2 = NodeId(arrete_id="APC1", article_id="3")
        node3 = NodeId(arrete_id="APC2", article_id="1")
        node4 = NodeId(arrete_id="APC2", article_id="2")

        assert G.has_edge(node3, node1) == True
        assert G.has_edge(node4, node2) == True

        edge_data_1 = G.get_edge_data(node3, node1, 0)
        assert edge_data_1 == {
            "id": "1",
            "operation_type": "REPLACE",
            "operand": "article",
            "sub_target": {"type": "FULL_SECTION"},
        }

        edge_data_2 = G.get_edge_data(node4, node2, 0)
        assert edge_data_2 == {"id": "2", "operation_type": "REMOVE"}
