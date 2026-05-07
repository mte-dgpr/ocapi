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

import pytest

from ocapi.exceptions import OcapiError
from ocapi.step_rendering.step_rendering import _select_principal_ap, permis_to_html, step_rendering
from ocapi.types import ArreteFile, ArticleHistory, FileType, Operation, Permis
from ocapi.utils.testing import make_testing_arrete


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
    arrete = make_testing_arrete("2020-01-01", file_type=FileType.AP_AUTORISATION)
    arretes = cast(list[ArreteFile], [arrete])

    result = step_rendering(history, operations, arretes)

    mock_content.assert_called_once_with(history, arretes, operations, arrete.id)
    mock_header.assert_called_once_with(arretes)
    mock_other.assert_called_once_with(arretes, operations=operations, history=history)

    assert isinstance(result, Permis)
    assert result.header == "<header/>"
    assert result.contenu == "<content/>"
    assert result.other == "<other/>"


class TestSelectPrincipalAp:
    """Cover the principal AP selection and flag marking."""

    def test_principal_flag_overrides_heuristic(self) -> None:
        older = make_testing_arrete("2018-01-01", file_type=FileType.AP_AUTORISATION)
        refonte = make_testing_arrete("2022-01-01", file_type=FileType.AP_AUTORISATION)
        older.principal = True

        assert _select_principal_ap([older, refonte]) is older

    def test_multiple_principals_raise(self) -> None:
        first = make_testing_arrete("2018-01-01")
        second = make_testing_arrete("2022-01-01")
        first.principal = True
        second.principal = True

        with pytest.raises(OcapiError):
            _select_principal_ap([first, second])

    def test_inferred_principal_is_marked(self) -> None:
        older = make_testing_arrete("2018-01-01", file_type=FileType.AP_AUTORISATION)
        refonte = make_testing_arrete("2022-01-01", file_type=FileType.AP_AUTORISATION)

        chosen = _select_principal_ap([older, refonte])

        assert chosen is refonte
        assert refonte.principal is True
        assert older.principal is False


def test_permis_to_html_replaces_all_template_tokens() -> None:
    permis = Permis(
        header='<header data-spec="header">HEADER</header>',
        contenu='<main data-spec="main">CONTENT</main>',
        other='<section data-spec="permit_complements">OTHER</section>',
    )
    html = permis_to_html(permis)

    assert '<header data-spec="header">HEADER</header>' in html
    assert '<main data-spec="main">CONTENT</main>' in html
    assert '<section data-spec="permit_complements">OTHER</section>' in html
    assert "{{HEADER}}" not in html
    assert "{{CONTENT}}" not in html
    assert "{{OTHER}}" not in html
    assert "{{GENERATED_BY}}" not in html
