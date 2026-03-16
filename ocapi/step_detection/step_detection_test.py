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
from unittest import mock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from ocapi.step_detection.prompts import prompt_detection
from ocapi.step_detection.step_detection import (
    _OPERATION_ID_COUNTER,
    convert_raw_operation_to_operation,
)
from ocapi.types import (
    NodeId,
    OperationType,
    RawOperation,
    RawOperationType,
    SubTarget,
    SubTargetType,
)


@pytest.fixture(autouse=True)
def reset_operation_id_counter() -> None:
    _OPERATION_ID_COUNTER.value = 0


@patch("ocapi.step_detection.step_detection.extract_operand_with_images")
@patch("ocapi.step_detection.step_detection.parse_subtarget")
def test_convert_raw_operation_to_operation(
    mock_parse_subtarget: mock.Mock,
    mock_extract_operand_with_images: mock.Mock,
) -> None:
    mock_extract_operand_with_images.return_value = "<mocked>operand content</mocked>"
    mock_parse_subtarget.return_value = SubTarget(type=SubTargetType.TABLEAU, position=1)

    block_html = Document(page_content="<section>Test content</section>", metadata={})
    source_arrete_id = "1980-01-01"

    raw_operations = [
        RawOperation(
            operation_type=RawOperationType.REPLACE,
            source_article="1",
            target_arrete="1981-01-01",
            target_article="2",
            sub_target="le tableau",
            new_content_start_marker="<start>",
            new_content_end_marker="<end>",
        ),
        RawOperation(
            operation_type=RawOperationType.REMOVE,
            source_article="2",
            target_arrete="1981-01-01",
            target_article="3",
        ),
    ]
    operations = [
        convert_raw_operation_to_operation(block_html.page_content, raw_op, source_arrete_id, {})
        for raw_op in raw_operations
    ]

    assert len(operations) == 2

    op1 = operations[0]
    assert op1.sub_target is not None
    assert op1.source_id == NodeId(arrete_id="1980-01-01", article_id="1")
    assert op1.target_id == NodeId(arrete_id="1981-01-01", article_id="2")
    assert op1.operation_type == OperationType.REPLACE
    assert op1.sub_target.type == SubTargetType.TABLEAU
    assert op1.extractable_content is True
    mock_extract_operand_with_images.assert_called_once()
    mock_parse_subtarget.assert_called_once_with("le tableau")

    op2 = operations[1]
    assert op2.source_id == NodeId(arrete_id="1980-01-01", article_id="2")
    assert op2.target_id == NodeId(arrete_id="1981-01-01", article_id="3")
    assert op2.operation_type == OperationType.REMOVE
    assert op2.sub_target is None
    assert op2.operand is None
    assert op2.extractable_content is True
    assert op2.id == "2"


@patch("ocapi.step_detection.step_detection.extract_operand_with_images")
def test_extractable_content_false_when_operand_extraction_fails(
    mock_extract_operand_with_images: mock.Mock,
) -> None:
    mock_extract_operand_with_images.return_value = "ERROR_EXTRACTING_CONTENT"
    block_html = Document(page_content="<section>Test content</section>", metadata={})
    raw_operation = RawOperation(
        operation_type=RawOperationType.REPLACE,
        source_article="1",
        target_arrete="1981-01-01",
        target_article="2",
        new_content_start_marker="<start>",
        new_content_end_marker="<end>",
    )

    operation = convert_raw_operation_to_operation(
        block_html.page_content, raw_operation, "1980-01-01", {}
    )

    assert operation.extractable_content is False
    assert operation.operand is None


def test_convert_raw_operation_replace_all_refonte() -> None:
    """REPLACE with target_article=ALL (arrêté refonte) is converted correctly."""
    block_html = Document(page_content="<section>Refonte complète</section>", metadata={})
    raw_op = RawOperation(
        operation_type=RawOperationType.REPLACE,
        source_article="1.1.2",
        target_arrete="2020-04-20",
        target_article="ALL",
        sub_target=None,
        new_content_start_marker=None,
        new_content_end_marker=None,
    )

    operation = convert_raw_operation_to_operation(
        block_html.page_content, raw_op, "2021-09-24", {}
    )

    assert operation.operation_type == OperationType.REPLACE
    assert operation.source_id == NodeId(arrete_id="2021-09-24", article_id="1.1.2")
    assert operation.target_id == NodeId(arrete_id="2020-04-20", article_id="ALL")
    assert operation.operand is None


def test_prompt_detection_includes_replace_all_schema() -> None:
    """The detection prompt must allow REPLACE with target_article ALL (refonte)."""
    prompt = prompt_detection("<html>test</html>")
    assert '"target_article": "ALL" | "x.x.x"' in prompt
    assert "refonte" in prompt.lower()
