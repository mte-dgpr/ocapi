#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
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
import json
from unittest import mock
from unittest.mock import Mock, patch

import pytest
from langchain_core.documents import Document

from ocapi.exceptions import OperationError
from ocapi.llm_utils import ConfidenceScoreConfig, prompt_detection
from ocapi.step_detection.step_detection import (
    _OPERATION_ID_COUNTER,
    _filter_low_confidence_operations,
    _parse_and_validate_raw_operations,
    _raw_operation_to_operation,
    step_detection,
)
from ocapi.types import (
    ErrorCode,
    NodeId,
    OperationOrigin,
    OperationType,
    RawOperation,
    RawOperationType,
    SubTarget,
    SubTargetType,
)
from ocapi.utils.testing import make_testing_arrete, make_testing_raw_op


@pytest.fixture(autouse=True)
def reset_operation_id_counter() -> None:
    _OPERATION_ID_COUNTER.value = 0


@patch("ocapi.step_detection.step_detection.extract_operand_with_images")
@patch("ocapi.step_detection.step_detection.parse_subtarget")
def test_convert_raw_operation_to_operation(
    mock_parse_subtarget: Mock,
    mock_extract_operand_with_images: Mock,
) -> None:
    mock_extract_operand_with_images.return_value = "<mocked>operand content</mocked>"
    mock_parse_subtarget.return_value = SubTarget(type=SubTargetType.TABLEAU, position=1)

    html_block = Document(page_content="<section>Test content</section>", metadata={})

    raw_operations = [
        RawOperation(
            operation_type=RawOperationType.REPLACE,
            origin=OperationOrigin.LLM,
            source_arrete="1980-01-01",
            source_article="1",
            target_arrete="1981-01-01",
            target_article="2",
            sub_target="le tableau",
            new_content_start_marker="<start>",
            new_content_end_marker="<end>",
        ),
        RawOperation(
            operation_type=RawOperationType.REMOVE,
            origin=OperationOrigin.LLM,
            source_arrete="1980-01-01",
            source_article="2",
            target_arrete="1981-01-01",
            target_article="3",
        ),
    ]
    operations = [
        _raw_operation_to_operation(html_block.page_content, raw_op, {})
        for raw_op in raw_operations
    ]

    assert len(operations) == 2

    op1 = operations[0]
    assert op1.sub_target is not None
    assert op1.source_id == NodeId(arrete_id="1980-01-01", article_id="1")
    assert op1.target_id == NodeId(arrete_id="1981-01-01", article_id="2")
    assert op1.operation_type == OperationType.REPLACE
    assert op1.origin == OperationOrigin.LLM
    assert op1.sub_target.type == SubTargetType.TABLEAU
    assert op1.error_codes == frozenset()
    mock_extract_operand_with_images.assert_called_once()
    mock_parse_subtarget.assert_called_once_with("le tableau")

    op2 = operations[1]
    assert op2.source_id == NodeId(arrete_id="1980-01-01", article_id="2")
    assert op2.target_id == NodeId(arrete_id="1981-01-01", article_id="3")
    assert op2.operation_type == OperationType.REMOVE
    assert op2.origin == OperationOrigin.LLM
    assert op2.sub_target is None
    assert op2.operand is None
    assert op2.error_codes == frozenset()
    assert op2.id == "2"


def test_convert_raw_operation_replace_all_refonte() -> None:
    """REPLACE with target_article=ALL is converted to REMOVE (abrogation)."""
    html_block = Document(page_content="<section>Refonte complète</section>", metadata={})
    raw_op = RawOperation(
        operation_type=RawOperationType.REPLACE,
        source_arrete="2021-09-24",
        source_article="1.1.2",
        target_arrete="2020-04-20",
        target_article="ALL",
        sub_target=None,
        new_content_start_marker=None,
        new_content_end_marker=None,
    )

    operation = _raw_operation_to_operation(html_block.page_content, raw_op, {})

    assert operation.operation_type == OperationType.REMOVE
    assert operation.source_id == NodeId(arrete_id="2021-09-24", article_id="1.1.2")
    assert operation.target_id == NodeId(arrete_id="2020-04-20", article_id="ALL")
    assert operation.operand is None


@patch("ocapi.step_detection.step_detection.parse_subtarget")
def test_all_with_non_full_section_subtarget_sets_error(
    mock_parse_subtarget: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """target_article=ALL with a COMPLEX sub-target → ERROR_EXTRACTING_OPERAND."""
    mock_parse_subtarget.return_value = SubTarget(
        type=SubTargetType.COMPLEX, description="annexe 1"
    )
    raw_op = RawOperation(
        operation_type=RawOperationType.REPLACE,
        source_arrete="2025-02-10",
        source_article="5",
        target_arrete="2006-12-14",
        target_article="ALL",
        sub_target="annexe 1",
    )
    with caplog.at_level("WARNING"):
        op = _raw_operation_to_operation("<section/>", raw_op, {})

    assert ErrorCode.ERROR_EXTRACTING_OPERAND in op.error_codes
    assert any("not fully defined" in msg for msg in caplog.messages)


def test_all_with_full_section_subtarget_converts_to_remove() -> None:
    """target_article=ALL with FULL_SECTION sub-target is valid → REMOVE."""
    raw_op = RawOperation(
        operation_type=RawOperationType.REPLACE,
        source_arrete="2021-09-24",
        source_article="1",
        target_arrete="2020-04-20",
        target_article="ALL",
        sub_target=None,
    )
    op = _raw_operation_to_operation("<section/>", raw_op, {})

    assert op.operation_type == OperationType.REMOVE
    assert op.error_codes == frozenset()
    assert op.operand is None


def test_raw_operation_to_operation_requires_source_article() -> None:
    raw = RawOperation(
        operation_type=RawOperationType.REMOVE,
        source_arrete="2022-01-01",
        target_arrete="2021-01-01",
        source_article=None,
        target_article="1",
    )
    with pytest.raises(OperationError, match="source_article"):
        _raw_operation_to_operation("<p/>", raw, {})


def test_raw_operation_to_operation_requires_target_article() -> None:
    raw = RawOperation(
        operation_type=RawOperationType.REMOVE,
        source_arrete="2022-01-01",
        target_arrete="2021-01-01",
        source_article="1",
        target_article=None,
    )
    with pytest.raises(OperationError, match="target_article"):
        _raw_operation_to_operation("<p/>", raw, {})


def test_add_all_without_subtarget_flagged_as_not_an_operation() -> None:
    """ADD + target_article=ALL without sub_target is not a consolidation op."""
    raw_op = RawOperation(
        operation_type=RawOperationType.ADD,
        source_arrete="2010-12-24",
        source_article="1",
        target_arrete="2008-12-10",
        target_article="ALL",
        sub_target=None,
    )
    op = _raw_operation_to_operation("<section/>", raw_op, {})

    assert op.operation_type == OperationType.ADD
    assert ErrorCode.NOT_AN_OPERATION in op.error_codes


@patch("ocapi.step_detection.step_detection.parse_subtarget")
def test_add_all_with_full_section_subtarget_flagged_as_not_an_operation(
    mock_parse_subtarget: Mock,
) -> None:
    """ADD + ALL + FULL_SECTION sub-target is also NOT_AN_OPERATION."""
    mock_parse_subtarget.return_value = SubTarget(type=SubTargetType.FULL_SECTION)
    raw_op = RawOperation(
        operation_type=RawOperationType.ADD,
        source_arrete="2010-12-24",
        source_article="1",
        target_arrete="2008-12-10",
        target_article="ALL",
        sub_target="ALL",
    )
    op = _raw_operation_to_operation("<section/>", raw_op, {})

    assert ErrorCode.NOT_AN_OPERATION in op.error_codes


@patch("ocapi.step_detection.step_detection.parse_subtarget")
def test_add_all_with_partial_subtarget_is_an_operation(
    mock_parse_subtarget: Mock,
) -> None:
    """ADD + ALL + non-FULL_SECTION sub-target keeps ERROR_EXTRACTING_OPERAND."""
    mock_parse_subtarget.return_value = SubTarget(
        type=SubTargetType.COMPLEX, description="annexe 1"
    )
    raw_op = RawOperation(
        operation_type=RawOperationType.ADD,
        source_arrete="2010-12-24",
        source_article="1",
        target_arrete="2008-12-10",
        target_article="ALL",
        sub_target="annexe 1",
    )
    op = _raw_operation_to_operation("<section/>", raw_op, {})

    assert ErrorCode.ERROR_EXTRACTING_OPERAND in op.error_codes
    assert ErrorCode.NOT_AN_OPERATION not in op.error_codes


def test_prompt_detection_includes_replace_all_schema() -> None:
    """The detection prompt must allow REPLACE with target_article ALL (refonte)."""
    html_block = "<html>test</html>"
    prompt = prompt_detection(html_block)
    assert '"target_article": "ALL" | "x.x.x"' in prompt
    assert "refonte" in prompt.lower()


def test_prompt_detection_includes_confidence_score_field() -> None:
    """The detection prompt must ask for a confidence_score on every operation."""
    prompt = prompt_detection("<html>test</html>")
    assert "confidence_score" in prompt


# ---------------------------------------------------------------------------
# confidence_score propagation through convert_raw_operation_to_operation
# ---------------------------------------------------------------------------


@patch("ocapi.step_detection.step_detection.extract_operand_with_images")
def test_convert_raw_operation_propagates_confidence_score(
    mock_extract: mock.Mock,
) -> None:
    mock_extract.return_value = None
    raw_op = RawOperation(
        operation_type=RawOperationType.REMOVE,
        source_arrete="2022-01-01",
        source_article="1",
        target_arrete="2021-01-01",
        target_article="2",
        confidence_score=85,
    )
    op = _raw_operation_to_operation("<section/>", raw_op, {})
    assert op.confidence_score == 85


@patch("ocapi.step_detection.step_detection.extract_operand_with_images")
def test_convert_raw_operation_confidence_score_none_when_absent(
    mock_extract: mock.Mock,
) -> None:
    mock_extract.return_value = None
    raw_op = RawOperation(
        operation_type=RawOperationType.REMOVE,
        source_arrete="2022-01-01",
        source_article="1",
        target_arrete="2021-01-01",
        target_article="2",
    )
    op = _raw_operation_to_operation("<section/>", raw_op, {})
    assert op.confidence_score is None


# ---------------------------------------------------------------------------
# _filter_low_confidence_operations
# ---------------------------------------------------------------------------


def test_filter_low_confidence_keeps_all_when_above_threshold() -> None:
    ops = [make_testing_raw_op(80), make_testing_raw_op(100), make_testing_raw_op(70)]
    kept, had_low = _filter_low_confidence_operations(ops, min_threshold=70, arrete_id="2022-01-01")
    assert len(kept) == 3
    assert had_low is False


def test_filter_low_confidence_drops_below_threshold(caplog: pytest.LogCaptureFixture) -> None:
    ops = [make_testing_raw_op(80), make_testing_raw_op(40), make_testing_raw_op(None)]
    with caplog.at_level("WARNING"):
        kept, had_low = _filter_low_confidence_operations(
            ops, min_threshold=70, arrete_id="2022-01-01"
        )
    assert len(kept) == 2
    assert had_low is True
    assert any("confidence_score=40" in msg for msg in caplog.messages)


def test_filter_low_confidence_keeps_op_with_none_score() -> None:
    """Operations without a confidence score are always kept (score is optional)."""
    ops = [make_testing_raw_op(None)]
    kept, had_low = _filter_low_confidence_operations(ops, min_threshold=70, arrete_id="2022-01-01")
    assert len(kept) == 1
    assert had_low is False


# ---------------------------------------------------------------------------
# step_detection – confidence filtering integration
# ---------------------------------------------------------------------------


def _llm_response_with_ops(*scores: int | None) -> str:
    ops = [
        {
            "operation_type": "REMOVE",
            "source_article": str(i + 1),
            "target_arrete": "2020-01-01",
            "target_article": str(i + 2),
            "confidence_score": score,
        }
        for i, score in enumerate(scores)
    ]
    return json.dumps(ops)


@patch("ocapi.step_detection.step_detection.chunk_arrete")
@patch("ocapi.step_detection.step_detection.get_confidence_score_config")
@patch("ocapi.step_detection.step_detection.call_llm_api")
@patch(
    "ocapi.step_detection.step_detection.extract_operand_with_images",
    return_value=None,
)
def test_step_detection_pass_skips_low_confidence_ops(
    _mock_extract: mock.Mock,
    mock_llm: mock.Mock,
    mock_conf: mock.Mock,
    mock_chunk: mock.Mock,
) -> None:
    """action=pass -> low-confidence operation is dropped, no retry."""
    mock_conf.return_value = ConfidenceScoreConfig(
        enabled=True, min_threshold=70, action_below_threshold="pass"
    )
    mock_llm.return_value = _llm_response_with_ops(90, 40)
    mock_chunk.return_value = ([Document(page_content="<section/>", metadata={})], {})

    ops = step_detection(make_testing_arrete("2022-01-01", "<html/>"))

    assert len(ops) == 1
    assert ops[0].confidence_score == 90
    mock_llm.assert_called_once()


@patch("ocapi.step_detection.step_detection.chunk_arrete")
@patch("ocapi.step_detection.step_detection.get_confidence_score_config")
@patch("ocapi.step_detection.step_detection.call_llm_api")
@patch(
    "ocapi.step_detection.step_detection.extract_operand_with_images",
    return_value=None,
)
def test_step_detection_retry_reruns_llm_on_low_confidence(
    _mock_extract: mock.Mock,
    mock_llm: mock.Mock,
    mock_conf: mock.Mock,
    mock_chunk: mock.Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """action=retry -> LLM is called a second time when low confidence detected."""
    mock_conf.return_value = ConfidenceScoreConfig(
        enabled=True, min_threshold=70, action_below_threshold="retry"
    )
    mock_llm.side_effect = [
        _llm_response_with_ops(40),
        _llm_response_with_ops(95),
    ]
    mock_chunk.return_value = ([Document(page_content="<section/>", metadata={})], {})

    with caplog.at_level("WARNING"):
        ops = step_detection(make_testing_arrete("2022-01-01", "<html/>"))

    assert mock_llm.call_count == 2
    assert len(ops) == 1
    assert ops[0].confidence_score == 95
    assert any("Retrying LLM call" in msg for msg in caplog.messages)


@patch("ocapi.step_detection.step_detection.chunk_arrete")
@patch("ocapi.step_detection.step_detection.get_confidence_score_config")
@patch("ocapi.step_detection.step_detection.call_llm_api")
@patch(
    "ocapi.step_detection.step_detection.extract_operand_with_images",
    return_value=None,
)
def test_step_detection_retry_still_drops_low_confidence_after_retry(
    _mock_extract: mock.Mock,
    mock_llm: mock.Mock,
    mock_conf: mock.Mock,
    mock_chunk: mock.Mock,
) -> None:
    """action=retry -> if the retry also returns low confidence, the op is still dropped."""
    mock_conf.return_value = ConfidenceScoreConfig(
        enabled=True, min_threshold=70, action_below_threshold="retry"
    )
    mock_llm.side_effect = [
        _llm_response_with_ops(30),
        _llm_response_with_ops(20),
    ]
    mock_chunk.return_value = ([Document(page_content="<section/>", metadata={})], {})

    ops = step_detection(make_testing_arrete("2022-01-01", "<html/>"))

    assert mock_llm.call_count == 2
    assert len(ops) == 0


@patch("ocapi.step_detection.step_detection.chunk_arrete")
@patch("ocapi.step_detection.step_detection.get_confidence_score_config")
@patch("ocapi.step_detection.step_detection.call_llm_api")
@patch(
    "ocapi.step_detection.step_detection.extract_operand_with_images",
    return_value=None,
)
def test_step_detection_disabled_keeps_all_ops_regardless_of_score(
    _mock_extract: mock.Mock,
    mock_llm: mock.Mock,
    mock_conf: mock.Mock,
    mock_chunk: mock.Mock,
) -> None:
    """When confidence filtering is disabled all operations pass through."""
    mock_conf.return_value = ConfidenceScoreConfig(
        enabled=False, min_threshold=70, action_below_threshold="pass"
    )
    mock_llm.return_value = _llm_response_with_ops(10, 0)
    mock_chunk.return_value = ([Document(page_content="<section/>", metadata={})], {})

    ops = step_detection(make_testing_arrete("2022-01-01", "<html/>"))

    assert len(ops) == 2
    mock_llm.assert_called_once()


# ---------------------------------------------------------------------------
# step_detection – origin
# ---------------------------------------------------------------------------


def test_parse_and_validate_sets_llm_origin_when_missing() -> None:
    raw = json.dumps(
        [
            {
                "operation_type": "REMOVE",
                "source_article": "1",
                "target_arrete": "2020-01-01",
                "target_article": "2",
            }
        ]
    )

    parsed = _parse_and_validate_raw_operations(raw, "2022-01-01")

    assert len(parsed) == 1
    assert parsed[0].origin == OperationOrigin.LLM
