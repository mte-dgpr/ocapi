import unittest
from unittest.mock import patch

from ocapi.step_detection.step_detection import _OPERATION_ID_COUNTER, convert_raw_operation_to_operation
from ocapi.types import NodeId, RawOperation, RawOperationType, SubTarget, SubTargetType

class TestConvertOperationsRawToOperations(unittest.TestCase):

    def setUp(self):
        _OPERATION_ID_COUNTER.value = 0

    @patch('ocapi.step_detection.step_detection.extract_operand_with_images')
    @patch('ocapi.step_detection.step_detection.parse_subtarget')
    def test_simple(self, mock_parse_subtarget, mock_extract_operand_with_images):
        # Configurer les mocks
        mock_extract_operand_with_images.return_value = "<mocked>operand content</mocked>"
        mock_parse_subtarget.return_value = SubTarget(type=SubTargetType.TABLEAU, position=1)
        
        block_html = "<section>Test content</section>"
        source_arrete_id = "AP001"
        
        raw_operations = [
            RawOperation(
                operation_type=RawOperationType.REPLACE,
                source_article="1",
                target_arrete="AP002",
                target_article="2",
                sub_target="le tableau",
                new_content_start_marker="<start>",
                new_content_end_marker="<end>",
            ),
            RawOperation(
                operation_type=RawOperationType.REMOVE,
                source_article="2",
                target_arrete="AP002",
                target_article="3",
            ),
        ]
        operations = [
            convert_raw_operation_to_operation(block_html, raw_op, source_arrete_id, {}) 
            for raw_op in raw_operations
        ]

        assert len(operations) == 2

        op1 = operations[0]
        assert op1.source_id == NodeId(arrete_id="AP001", article_id="1")
        assert op1.target_id == NodeId(arrete_id="AP002", article_id="2")
        assert op1.operation_type == "REPLACE"  # Comparaison avec string car use_enum_values=True
    assert op1.sub_target.type == "TABLEAU"
        # Vérifier que extract_operand_with_images a été appelé
        mock_extract_operand_with_images.assert_called_once()
        mock_parse_subtarget.assert_called_once_with("le tableau")

        op2 = operations[1]
        assert op2.source_id == NodeId(arrete_id="AP001", article_id="2")
        assert op2.target_id == NodeId(arrete_id="AP002", article_id="3")
        assert op2.operation_type == "REMOVE"  # Comparaison avec string car use_enum_values=True
        assert op2.sub_target is None
        assert op2.operand is None
        assert op2.id == "2"
