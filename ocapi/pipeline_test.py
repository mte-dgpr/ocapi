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
from typing import cast
from unittest.mock import MagicMock, patch

from arretify.types import DocumentContext

from ocapi.pipeline import run_pipeline
from ocapi.step_detection.step_detection import _OPERATION_ID_COUNTER
from ocapi.types import NodeId, Operation, OperationType, SubTarget, SubTargetType
from ocapi.utils.testing import make_testing_arrete


@patch("ocapi.pipeline.step_detection", return_value=[])
def test_start_date_skips_earlier_arretes(mock_detection: MagicMock) -> None:
    """start_date excludes the initial arrêté (<=): only strictly later arrêtés are detected."""
    arretes = [
        make_testing_arrete("2009-12-08"),
        make_testing_arrete("2014-01-09"),
        make_testing_arrete("2023-12-04"),
    ]

    run_pipeline(arretes, start_date="2014-01-09", enable_rendering=False)

    detected_ids = [call.args[0].id for call in mock_detection.call_args_list]
    assert "2009-12-08" not in detected_ids
    assert "2014-01-09" not in detected_ids
    assert "2023-12-04" in detected_ids
    assert mock_detection.call_count == 1


@patch("ocapi.pipeline.step_detection", return_value=[])
def test_start_date_none_defaults_to_first_arrete(mock_detection: MagicMock) -> None:
    """Without start_date, the first arrêté is excluded from detection by default."""
    arretes = [make_testing_arrete("2009-12-08"), make_testing_arrete("2014-01-09")]

    run_pipeline(arretes, start_date=None, enable_rendering=False)

    detected_ids = [call.args[0].id for call in mock_detection.call_args_list]
    assert "2009-12-08" not in detected_ids
    assert "2014-01-09" in detected_ids
    assert mock_detection.call_count == 1


@patch("ocapi.pipeline.step_detection", return_value=[])
def test_start_date_after_all_arretes_processes_none(mock_detection: MagicMock) -> None:
    arretes = [make_testing_arrete("2009-12-08"), make_testing_arrete("2014-01-09")]

    run_pipeline(arretes, start_date="2025-01-01", enable_rendering=False)

    assert mock_detection.call_count == 0


@patch("ocapi.pipeline.step_rendering")
@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.step_detection", return_value=[])
def test_start_date_passes_all_arretes_to_resolution(
    mock_detection: MagicMock,
    mock_resolution: MagicMock,
    mock_rendering: MagicMock,
) -> None:
    """start_date filters detection, but all arrêtés must still reach resolution."""
    arretes = [
        make_testing_arrete("2009-12-08"),
        make_testing_arrete("2014-01-09"),
        make_testing_arrete("2023-12-04"),
    ]

    run_pipeline(arretes, start_date="2014-01-09", enable_rendering=False)

    assert mock_detection.call_count == 1
    mock_resolution.assert_called_once()
    resolved_arretes = mock_resolution.call_args[0][1]
    resolved_ids = [a.id for a in resolved_arretes]
    assert "2009-12-08" in resolved_ids
    assert "2014-01-09" in resolved_ids
    assert "2023-12-04" in resolved_ids


@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.step_detection", return_value=[])
def test_run_pipeline_with_preloaded_operations(
    mock_detection: MagicMock,
    mock_resolution: MagicMock,
) -> None:
    """When operations are provided and enable_detection=False, detection is skipped."""
    arretes = [make_testing_arrete("2009-12-08"), make_testing_arrete("2014-01-09")]
    preloaded = [
        Operation(
            id="1",
            source_id=NodeId(arrete_id="2014-01-09", article_id="1"),
            target_id=NodeId(arrete_id="2009-12-08", article_id="1"),
            operation_type=OperationType.REPLACE,
            operand="<p>test</p>",
            sub_target=None,
        )
    ]
    mock_resolution.return_value = ({}, arretes, preloaded)

    ops, history, _arretes, _permis = run_pipeline(
        arretes,
        enable_detection=False,
        enable_rendering=False,
        operations=preloaded,
    )

    assert ops == preloaded
    assert mock_detection.call_count == 0
    mock_resolution.assert_called_once_with(preloaded, arretes, enable_llm=True)


@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.extract_operations_from_tagged_soup")
def test_pipeline_renumbers_conflicting_preloaded_operation_ids(
    mock_extract_tagged: MagicMock,
    mock_resolution: MagicMock,
) -> None:
    arrete = make_testing_arrete("2024-01-10")
    tagged_op = Operation(
        id="1",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu regex</q>",
    )
    preloaded_duplicate = Operation(
        id="1",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="3"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu préchargé</q>",
    )

    mock_extract_tagged.return_value = [tagged_op]

    run_pipeline(
        [arrete],
        enable_detection=False,
        enable_tagging=True,
        enable_rendering=False,
        operations=[preloaded_duplicate],
    )

    resolved_ops = mock_resolution.call_args[0][0]
    assert [op.id for op in resolved_ops] == ["1", "2"]


@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.extract_operations_from_tagged_soup")
def test_pipeline_prefers_precise_candidate_over_full_tagged_operation(
    mock_extract_tagged: MagicMock,
    mock_resolution: MagicMock,
) -> None:
    arrete = make_testing_arrete("2024-01-10")
    tagged_full = Operation(
        id="1",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu regex</q>",
    )
    precise_candidate = Operation(
        id="2",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu LLM</q>",
        sub_target=SubTarget(
            type=SubTargetType.PARAGRAPHE,
            position=1,
            description="paragraphe 1",
        ),
    )

    mock_extract_tagged.return_value = [tagged_full]

    run_pipeline(
        [arrete],
        enable_detection=False,
        enable_tagging=True,
        enable_rendering=False,
        operations=[precise_candidate],
    )

    resolved_ops = mock_resolution.call_args[0][0]
    assert resolved_ops == [precise_candidate]


@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.extract_operations_from_tagged_soup")
@patch("ocapi.pipeline.step_detection")
def test_pipeline_filters_preloaded_ops_with_tagging_when_detection_disabled(
    mock_detection: MagicMock,
    mock_extract_tagged: MagicMock,
    mock_resolution: MagicMock,
) -> None:
    arrete = make_testing_arrete("2024-01-10")
    tagged_op = Operation(
        id="1",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu regex</q>",
    )
    preloaded_duplicate = Operation(
        id="2",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu préchargé</q>",
    )

    mock_extract_tagged.return_value = [tagged_op]
    mock_detection.return_value = [preloaded_duplicate]

    run_pipeline(
        [arrete],
        enable_detection=False,
        enable_tagging=True,
        enable_rendering=False,
        operations=[preloaded_duplicate],
    )

    mock_extract_tagged.assert_called_once()
    mock_detection.assert_not_called()
    mock_resolution.assert_called_once_with([tagged_op], [arrete], enable_llm=True)


@patch("ocapi.pipeline.step_detection", return_value=[])
def test_start_date_equal_to_first_arrete_skips_it(mock_detection: MagicMock) -> None:
    """Boundary: start_date == earliest arrêté excludes that arrêté from detection (<=)."""
    arretes = [make_testing_arrete("2009-12-08"), make_testing_arrete("2014-01-09")]

    run_pipeline(arretes, start_date="2009-12-08", enable_rendering=False)

    detected_ids = [call.args[0].id for call in mock_detection.call_args_list]
    assert "2009-12-08" not in detected_ids
    assert "2014-01-09" in detected_ids
    assert mock_detection.call_count == 1


@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.step_detection", return_value=[])
def test_run_pipeline_resets_operation_id_counter(
    _mock_detection: MagicMock,
    _mock_resolution: MagicMock,
) -> None:
    """Each pipeline run must restart operation ids from 1 (per-AIOT counter)."""
    _OPERATION_ID_COUNTER.value = 42

    run_pipeline([make_testing_arrete("2009-12-08")], enable_rendering=False)

    assert _OPERATION_ID_COUNTER.value == 0


@patch("ocapi.pipeline.step_tagging")
@patch("ocapi.pipeline.step_detection", return_value=[])
def test_step_tagging_runs_when_enabled(
    mock_detection: MagicMock,
    mock_tagging: MagicMock,
) -> None:
    arretes = [make_testing_arrete("2009-12-08"), make_testing_arrete("2014-01-09")]
    dcs = cast(list[DocumentContext], [MagicMock(soup=a.soup) for a in arretes])

    run_pipeline(  # type: ignore[arg-type]
        arretes,
        enable_rendering=False,
        enable_tagging=True,
        document_contexts=dcs,
    )

    assert mock_tagging.call_count == 2


@patch("ocapi.pipeline.step_tagging")
@patch("ocapi.pipeline.step_detection", return_value=[])
def test_step_tagging_disabled_by_default(
    mock_detection: MagicMock,
    mock_tagging: MagicMock,
) -> None:
    arretes = [make_testing_arrete("2009-12-08")]
    dcs = cast(list[DocumentContext], [MagicMock(soup=arretes[0].soup)])

    run_pipeline(arretes, enable_rendering=False, document_contexts=dcs)  # type: ignore[arg-type]

    mock_tagging.assert_not_called()


@patch("ocapi.pipeline.step_tagging")
@patch("ocapi.pipeline.step_detection", return_value=[])
def test_step_tagging_skipped_when_disabled(
    mock_detection: MagicMock,
    mock_tagging: MagicMock,
) -> None:
    arretes = [make_testing_arrete("2009-12-08")]
    dcs = [MagicMock(soup=arretes[0].soup)]

    run_pipeline(
        arretes,
        enable_rendering=False,
        enable_tagging=False,
        document_contexts=dcs,  # type: ignore[arg-type]
    )

    mock_tagging.assert_not_called()


@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.extract_operations_from_tagged_soup")
@patch("ocapi.pipeline.step_detection")
def test_pipeline_filters_llm_ops_with_tagging_when_enabled(
    mock_detection: MagicMock,
    mock_extract_tagged: MagicMock,
    mock_resolution: MagicMock,
) -> None:
    arrete = make_testing_arrete("2024-01-10")
    tagged_op = Operation(
        id="1",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu regex</q>",
    )
    llm_duplicate = Operation(
        id="2",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu LLM</q>",
    )

    mock_extract_tagged.return_value = [tagged_op]
    mock_detection.return_value = [llm_duplicate]

    run_pipeline(
        [arrete],
        start_date="2023-01-01",
        enable_tagging=True,
        enable_rendering=False,
    )

    mock_extract_tagged.assert_called_once()
    mock_resolution.assert_called_once_with([tagged_op], [arrete], enable_llm=True)


@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.extract_operations_from_tagged_soup")
@patch("ocapi.pipeline.step_detection")
def test_pipeline_does_not_filter_with_tagging_disabled(
    mock_detection: MagicMock,
    mock_extract_tagged: MagicMock,
    mock_resolution: MagicMock,
) -> None:
    arrete = make_testing_arrete("2024-01-10")
    llm_op = Operation(
        id="2",
        source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.REPLACE,
        operand="<q>Contenu LLM</q>",
    )

    mock_extract_tagged.return_value = [
        Operation(
            id="1",
            source_id=NodeId(arrete_id="2024-01-10", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
            operation_type=OperationType.REPLACE,
            operand="<q>Contenu regex</q>",
        )
    ]
    mock_detection.return_value = [llm_op]

    run_pipeline(
        [arrete],
        start_date="2023-01-01",
        enable_tagging=False,
        enable_rendering=False,
    )

    mock_extract_tagged.assert_not_called()
    mock_resolution.assert_called_once_with([llm_op], [arrete], enable_llm=True)
