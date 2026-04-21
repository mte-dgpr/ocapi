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

from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.types import ArreteFile, ArticleHistory, Operation, Permis


@patch("ocapi.step_rendering.step_rendering.make_permit_content", return_value="<content/>")
@patch("ocapi.step_rendering.step_rendering.make_permit_header", return_value="<header/>")
@patch("ocapi.step_rendering.step_rendering.make_permit_other", return_value="<other/>")
def test_step_rendering_returns_permis(
    mock_other: MagicMock,
    mock_header: MagicMock,
    mock_content: MagicMock,
) -> None:
    """Verify that step_rendering assembles the 3 permit components and returns a valid Permis."""
    history = cast(ArticleHistory, {})
    operations = cast(list[Operation], [])
    arretes = cast(list[ArreteFile], [MagicMock()])

    result = step_rendering(history, operations, arretes)

    mock_content.assert_called_once_with(history, arretes, operations)
    mock_header.assert_called_once_with(arretes)
    mock_other.assert_called_once_with(arretes, operations=operations, history=history)

    assert isinstance(result, Permis)
    assert result.header == "<header/>"
    assert result.contenu == "<content/>"
    assert result.other == "<other/>"
