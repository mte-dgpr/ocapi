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
from typing import cast
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import ArreteFile, ArticleHistory, FileType, NodeId, Operation, OperationType


@patch("ocapi.step_resolution.step_resolution.apply_all_ops")
@patch("ocapi.step_resolution.step_resolution.build_graph")
def test_step_resolution_returns_history_and_arretes(
    mock_build_graph: MagicMock,
    mock_apply_all_ops: MagicMock,
) -> None:
    """Verify that step_resolution orchestrates build_graph and apply_all_ops and returns their results."""  # noqa: E501
    fake_history: ArticleHistory = {NodeId(arrete_id="2020-01-01", article_id="1"): []}
    fake_arretes = cast(list[ArreteFile], [MagicMock(id="2020-01-01")])
    mock_build_graph.return_value = (MagicMock(), fake_arretes, [])
    mock_apply_all_ops.return_value = (fake_history, [])

    history, arretes = step_resolution([], fake_arretes)

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
    mock_build_graph.return_value = (MagicMock(), [], [])
    mock_apply_all_ops.return_value = ({}, [])

    history, arretes = step_resolution([], cast(list[ArreteFile], []))

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
        ),
    ]

    history, updated_arrete_files = step_resolution(operations, arrete_files)

    arrete_2020 = next(af for af in updated_arrete_files if af.id == "2020-04-20")
    assert arrete_2020.status is False
    arrete_2021 = next(af for af in updated_arrete_files if af.id == "2021-09-24")
    assert arrete_2021.status is True
