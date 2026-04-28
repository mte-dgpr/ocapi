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

import pytest
from bs4 import BeautifulSoup, Tag

from ocapi.step_rendering.article_filter import filter_superfluous_sections, is_superfluous_section
from ocapi.utils.utils import normalize_section_title


def _section(title: str, number: str = "1") -> Tag:
    html = (
        f'<section data-spec="section" data-number="{number}" data-title="{title}">'
        f'<h1 data-spec="section_title">ARTICLE {number} {title}</h1>'
        f"<p>Contenu</p></section>"
    )
    tag = BeautifulSoup(html, "html.parser").find("section")
    assert tag is not None
    return tag


class TestNormalizeSectionTitle:
    def test_strips_accents(self) -> None:
        assert normalize_section_title("DÉLAIS ET VOIES DE RECOURS") == "delais et voies de recours"

    def test_collapses_whitespace(self) -> None:
        assert normalize_section_title("  FRAIS  ") == "frais"

    def test_lowercases(self) -> None:
        assert normalize_section_title("Sanctions") == "sanctions"


class TestIsSuperfluous:
    @pytest.mark.parametrize(
        "title",
        [
            "FRAIS",
            "Frais",
            "frais",
            "SANCTIONS",
            "DIFFUSION",
            "EXÉCUTION",
            "Execution",
            "MODALITÉS D'EXÉCUTION",
            "MODALITES D'EXECUTION",
            "TRANSMISSION À L'EXPLOITANT",
            "TRANSMISSION A L'EXPLOITANT",
            "DÉLAIS ET VOIES DE RECOURS",
            "DELAIS ET VOIES DE RECOURS",
            "MODIFICATIONS ET COMPLÉMENTS APPORTÉS AUX PRESCRIPTIONS DES ACTES ANTÉRIEURS",
            "PUBLICATION",
            "PUBLICATION ET AMPLIATION",
            "AMPLIATION",
        ],
    )
    def test_superfluous_titles_detected(self, title: str) -> None:
        assert is_superfluous_section(_section(title)) is True

    def test_regular_article_not_filtered(self) -> None:
        assert is_superfluous_section(_section("DISPOSITIONS GÉNÉRALES")) is False

    def test_section_without_data_title_not_filtered(self) -> None:
        html = (
            '<section data-spec="section" data-number="1">'
            '<h1 data-spec="section_title">FRAIS</h1>'
            "<p>Contenu</p></section>"
        )
        tag = BeautifulSoup(html, "html.parser").find("section")
        assert tag is not None
        assert is_superfluous_section(tag) is False


class TestFilterSuperfluousSections:
    def test_removes_superfluous_and_keeps_others(self) -> None:
        soup = BeautifulSoup(
            '<main data-spec="main">'
            '<section data-spec="section" data-number="1" data-title="DISPOSITIONS GÉNÉRALES">'
            '<h1 data-spec="section_title">ARTICLE 1 DISPOSITIONS GÉNÉRALES</h1><p>A</p></section>'
            '<section data-spec="section" data-number="2" data-title="FRAIS">'
            '<h1 data-spec="section_title">ARTICLE 2 FRAIS</h1><p>B</p></section>'
            '<section data-spec="section" data-number="3" data-title="SANCTIONS">'
            '<h1 data-spec="section_title">ARTICLE 3 SANCTIONS</h1><p>C</p></section>'
            "</main>",
            "html.parser",
        )
        sections = soup.find_all("section", attrs={"data-spec": "section"})
        removed = filter_superfluous_sections(sections)

        assert len(removed) == 2
        remaining = soup.find_all("section", attrs={"data-spec": "section"})
        assert len(remaining) == 1
        assert "DISPOSITIONS" in remaining[0].get_text()

    def test_returns_empty_when_no_superfluous(self) -> None:
        soup = BeautifulSoup(
            '<main><section data-spec="section" data-number="1" data-title="DISPOSITIONS">'
            '<h1 data-spec="section_title">ARTICLE 1 DISPOSITIONS</h1></section></main>',
            "html.parser",
        )
        sections = soup.find_all("section", attrs={"data-spec": "section"})
        removed = filter_superfluous_sections(sections)
        assert removed == []
