import unittest
from unittest.mock import patch

from ocapi.step_detection.step_detection import _OPERATION_ID_COUNTER, convert_raw_operation_to_operation

from .build_op_graph import build_graph

from ocapi.types import Operation, OperationType, NodeId, SubTarget, SubTargetType, RawOperation, RawOperationType



class TestBuildOpGraph(unittest.TestCase):

    def test_build_graph(self):
        operations = [
            Operation(
                id="1",
                source_id=NodeId(arrete_id="AP001", article_id="1"),
                target_id=NodeId(arrete_id="AP001", article_id="2"),
                operation_type=OperationType.REPLACE,
                operand="article",
                sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
            ),
            Operation(
                id="2",
                source_id=NodeId(arrete_id="AP001", article_id="2"),
                target_id=NodeId(arrete_id="AP001", article_id="3"),
                operation_type=OperationType.REMOVE,
                operand="section",
            ),
        ]
        G = build_graph(operations)

        assert len(G.nodes) == 3
        assert len(G.edges) == 2

        # Les clés des noeuds sont maintenant des objets NodeId
        node1 = NodeId(arrete_id="AP001", article_id="1")
        node2 = NodeId(arrete_id="AP001", article_id="2")
        node3 = NodeId(arrete_id="AP001", article_id="3")

        assert G.has_edge(node1, node2) == True
        assert G.has_edge(node2, node3) == True

        edge_data_1 = G.get_edge_data(node1, node2, 0)
        assert edge_data_1["operation_type"] == 'REPLACE'
        assert edge_data_1["operand"] == "article"

        edge_data_2 = G.get_edge_data(node2, node3, 0)
        assert edge_data_2["operation_type"] == 'REMOVE'
        assert edge_data_2["operand"] == "section"