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

from bs4 import BeautifulSoup

from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import (
    ArreteFile,
    ArticleHistory,
    ErrorCode,
    FileType,
    NodeId,
    Operation,
    OperationType,
)


@patch("ocapi.step_resolution.step_resolution.apply_all_ops")
@patch("ocapi.step_resolution.step_resolution.build_graph")
def test_step_resolution_returns_history_and_arretes(
    mock_build_graph: MagicMock,
    mock_apply_all_ops: MagicMock,
) -> None:
    """Verify that step_resolution orchestrates build_graph and apply_all_ops and returns their results."""  # noqa: E501
    fake_history: ArticleHistory = {NodeId(arrete_id="2020-01-01", article_id="1"): []}
    fake_arretes = cast(list[ArreteFile], [MagicMock(id="2020-01-01")])
    mock_build_graph.return_value = (MagicMock(), fake_arretes, [], [])
    mock_apply_all_ops.return_value = (fake_history, [], {})

    history, arretes, _ops = step_resolution([], fake_arretes)

    mock_build_graph.assert_called_once_with([], fake_arretes)
    mock_apply_all_ops.assert_called_once()
    assert history is fake_history
    assert arretes is fake_arretes


@patch("ocapi.step_resolution.step_resolution.apply_all_ops")
@patch("ocapi.step_resolution.step_resolution.build_graph")
def test_step_resolution_empty_history(
    mock_build_graph: MagicMock,
    mock_apply_all_ops: MagicMock,
) -> None:
    mock_build_graph.return_value = (MagicMock(), [], [], [])
    mock_apply_all_ops.return_value = ({}, [], {})

    history, arretes, _ops = step_resolution([], cast(list[ArreteFile], []))

    assert history == {}
    assert arretes == []


def test_step_resolution_replace_all_marks_target_arrete_abrogated() -> None:
    """REPLACE ALL (refonte) must mark the target arrêté as abrogated."""
    html_2020 = """
    <section data-spec="section" data-number="1">Article 1</section>
    """
    html_2021 = """
    <section data-spec="section" data-number="1.1.2">Article refonte</section>
    """

    arrete_files = [
        ArreteFile(
            id="2020-04-20",
            aiot="aiot1",
            filename="2020-04-20.html",
            soup=BeautifulSoup(html_2020, "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="2021-09-24",
            aiot="aiot1",
            filename="2021-09-24.html",
            soup=BeautifulSoup(html_2021, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]

    operations = [
        Operation(
            id="1",
            source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
            target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
            operation_type=OperationType.REPLACE,
            operand="<section>refonte body</section>",
        ),
    ]

    history, updated_arrete_files, _ops = step_resolution(operations, arrete_files)

    arrete_2020 = next(af for af in updated_arrete_files if af.id == "2020-04-20")
    assert arrete_2020.status is False
    arrete_2021 = next(af for af in updated_arrete_files if af.id == "2021-09-24")
    assert arrete_2021.status is True


@patch("ocapi.step_resolution.step_resolution.apply_all_ops")
@patch("ocapi.step_resolution.step_resolution.build_graph")
def test_step_resolution_sets_resolved_status_on_operations(
    mock_build_graph: MagicMock,
    mock_apply_all_ops: MagicMock,
) -> None:
    """Operations returned by step_resolution carry their resolved status_code."""
    op_ok = Operation(
        id="op-ok",
        source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
    )
    op_err = Operation(
        id="op-err",
        source_id=NodeId(arrete_id="2021-01-01", article_id="2"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
        operation_type=OperationType.ADD,
    )
    mock_build_graph.return_value = (MagicMock(), [], [], [op_ok, op_err])
    mock_apply_all_ops.return_value = (
        {},
        [],
        {
            "op-ok": frozenset(),
            "op-err": frozenset({ErrorCode.ERROR_FINDING_SUBTARGET}),
        },
    )

    _history, _arretes, updated_ops = step_resolution([op_ok, op_err], cast(list[ArreteFile], []))

    by_id = {op.id: op for op in updated_ops}
    assert by_id["op-ok"].status_code == frozenset()
    assert by_id["op-err"].status_code == frozenset({ErrorCode.ERROR_FINDING_SUBTARGET})


@patch("ocapi.step_resolution.step_resolution.apply_all_ops")
@patch("ocapi.step_resolution.step_resolution.build_graph")
def test_step_resolution_preserves_status_for_unprocessed_operations(
    mock_build_graph: MagicMock,
    mock_apply_all_ops: MagicMock,
) -> None:
    """Operations absent from resolved_status keep their original status_code."""
    op_skipped = Operation(
        id="op-skipped",
        source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
        status_code=frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND}),
    )
    mock_build_graph.return_value = (MagicMock(), [], [], [op_skipped])
    mock_apply_all_ops.return_value = ({}, [], {})

    _history, _arretes, updated_ops = step_resolution([op_skipped], cast(list[ArreteFile], []))

    assert updated_ops[0].status_code == frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND})
