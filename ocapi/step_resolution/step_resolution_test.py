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

from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import ArreteFile, ArticleHistory, NodeId


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
