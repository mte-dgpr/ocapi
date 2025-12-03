import unittest

from .build_op_graph import Operation, OperationType, build_graph, convert_operations_raw_to_operations, _OPERATION_ID_COUNTER


class TestConvertOperationsRawToOperations(unittest.TestCase):

    def setUp(self):
        _OPERATION_ID_COUNTER.value = 0

    def test_simple(self):
        raw_operations = [
            {
                "source_uid": "node1",
                "target_uid": "node2",
                "modification_type": "REPLACE",
                "new_content_html": "article",
                "target_element": "bla",
            },
            {
                "source_uid": "node2",
                "target_uid": "node3",
                "modification_type": "REMOVE",
                "new_content_html": "section",
            },
        ]
        operations = convert_operations_raw_to_operations(raw_operations)

        assert len(operations) == 2

        op1 = operations[0]
        assert op1.source_uid == "node1"
        assert op1.target_uid == "node2"
        assert op1.operation_type == "REPLACE"
        assert op1.operand == "article"
        assert op1.sub_target == "bla"
        assert op1.id == "1"

        op2 = operations[1]
        assert op2.source_uid == "node2"
        assert op2.target_uid == "node3"
        assert op2.operation_type == "REMOVE"
        assert op2.operand == "section"
        assert op2.sub_target is None
        assert op2.id == "2"


class TestBuildOpGraph(unittest.TestCase):

    def test_build_graph(self):
        operations = [
            Operation(
                id="1",
                source_id="node1",
                target_id="node2",
                operation_type=OperationType.REPLACE,
                operand="article",
                sub_target="bla",
            ),
            Operation(
                id="2",
                source_id="node2",
                target_id="node3",
                operation_type=OperationType.REMOVE,
                operand="section",
            ),
        ]
        G = build_graph(operations)

        assert len(G.nodes) == 3
        assert len(G.edges) == 2

        assert G.has_edge("node1", "node2") == True
        assert G.has_edge("node2", "node3") == True

        edge_data_1 = G.get_edge_data("node1", "node2", 0)
        assert edge_data_1["operation_type"] == 'REPLACE'
        assert edge_data_1["operand"] == "article"
        assert edge_data_1["sub_target"] == "bla"

        edge_data_2 = G.get_edge_data("node2", "node3", 0)
        assert edge_data_2["operation_type"] == 'REMOVE'
        assert edge_data_2["operand"] == "section"