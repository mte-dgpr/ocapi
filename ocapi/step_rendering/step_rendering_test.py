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

import pytest
from bs4 import BeautifulSoup

from ocapi.step_rendering.make_header import (
    make_permit_header,
    make_permit_motif,
    make_permit_sources,
    make_permit_visa,
)
from ocapi.step_rendering.make_main_content import (
    _is_abrogated,
    make_permit_content,
    make_section_version,
)
from ocapi.step_rendering.make_other import has_not_out_ops, make_permit_other
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.types import (
    ArreteFile,
    ArticleHistory,
    ArticleVersion,
    NodeId,
    Operation,
    OperationType,
    Permis,
    SubTarget,
    SubTargetType,
)


def _make_testing_arrete_file(
    arrete_id: str,
    aiot: str,
    filename: str,
    html: str,
    status: bool = True,
) -> ArreteFile:
    return ArreteFile(
        id=arrete_id,
        aiot=aiot,
        filename=filename,
        soup=BeautifulSoup(html, "html.parser"),
        status=status,
    )


def test_make_permit_header_contains_permit_specs_and_ordering() -> None:
    arrete_2021 = _make_testing_arrete_file(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="arrete_2021",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>Titre 2021</h1></div>
 <div data-spec="visa">VISA UNIQUE 1</div>
 <div data-spec="visa">VISA UNIQUE 2</div>
 <div data-spec="motifs">MOTIF 2021</div>
</body></html>
""",
    )
    arrete_2020 = _make_testing_arrete_file(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="arrete_2020",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>Titre 2020</h1></div>
 <div data-spec="visa">VISA UNIQUE 1</div>
 <div data-spec="motifs">MOTIF 2020</div>
</body></html>
""",
    )

    html = make_permit_header([arrete_2021, arrete_2020])
    rendered_soup = BeautifulSoup(html, "html.parser")
    permit_visa = rendered_soup.select_one('[data-spec="permit_visa"]')
    permit_title = rendered_soup.select_one('[data-spec="permit_title"]')

    assert 'data-spec="permit_title"' in html
    assert 'data-spec="permit_sources"' in html
    assert 'data-spec="permit_visa"' in html
    assert 'data-spec="permit_motif"' in html
    assert permit_visa is not None
    assert permit_title is not None
    assert permit_visa.get_text(" ", strip=True).count("VISA UNIQUE 1") == 1
    assert permit_title.get_text(" ", strip=True).count("0001") == 1
    assert html.index('data-date="2020-01-01"') < html.index('data-date="2021-01-01"')


def test_make_permit_sources_marks_abrogated_arretes() -> None:
    """Abrogated arrêtés must carry the (ABROGE) mention."""
    active = _make_testing_arrete_file(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_initial",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>AP Initial</h1></div>
</body></html>
""",
        status=True,
    )
    abroge = _make_testing_arrete_file(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="ap_abroge",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>AP Abrogé</h1></div>
</body></html>
""",
        status=False,
    )

    html = make_permit_sources([active, abroge])
    soup = BeautifulSoup(html, "html.parser")

    sources = soup.find_all("li", attrs={"data-spec": "permit_source"})
    assert len(sources) == 2

    active_source = soup.find("li", attrs={"data-status": "active"})
    abroge_source = soup.find("li", attrs={"data-status": "abroge"})
    assert active_source is not None
    assert abroge_source is not None
    assert "(ABROGE)" not in active_source.get_text()
    assert "(ABROGE)" in abroge_source.get_text()


def test_make_permit_header_includes_abrogated_arrete_with_visas_and_motifs() -> None:
    """Abrogated arrêté (refonte) must appear in header with ABROGE, its visas and motifs."""
    ap_2020_abroge = _make_testing_arrete_file(
        arrete_id="2020-04-20",
        aiot="0001",
        filename="ap_2020",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>AP 2020</h1></div>
 <div data-spec="visa">VISA ARRETE 2020</div>
 <div data-spec="motifs">CONSIDERANT ARRETE 2020</div>
</body></html>
""",
        status=False,
    )
    ap_2021_refonte = _make_testing_arrete_file(
        arrete_id="2021-09-24",
        aiot="0001",
        filename="ap_2021",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>AP 2021 Refonte</h1></div>
 <div data-spec="visa">VISA ARRETE 2021</div>
 <div data-spec="motifs">CONSIDERANT ARRETE 2021</div>
</body></html>
""",
        status=True,
    )

    html = make_permit_header([ap_2020_abroge, ap_2021_refonte])
    soup = BeautifulSoup(html, "html.parser")

    sources = soup.find_all("li", attrs={"data-spec": "permit_source"})
    assert len(sources) == 2
    abroge_source = soup.find("li", attrs={"data-status": "abroge"})
    assert abroge_source is not None
    assert "(ABROGE)" in abroge_source.get_text()
    assert "2020-04-20" in abroge_source.get_text()

    assert "VISA ARRETE 2020" in html
    assert "VISA ARRETE 2021" in html
    assert "CONSIDERANT ARRETE 2020" in html
    assert "CONSIDERANT ARRETE 2021" in html


def test_make_permit_visa_is_collapsible() -> None:
    """Consolidated visas must be inside a <details> element."""
    arrete = _make_testing_arrete_file(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="arrete",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="visa">VISA 1</div>
</body></html>
""",
    )

    html = make_permit_visa([arrete])
    soup = BeautifulSoup(html, "html.parser")
    details = soup.find("details")
    assert details is not None
    assert "Visas consolidés" in details.get_text()
    assert "VISA 1" in details.get_text()


def test_make_permit_motif_is_collapsible() -> None:
    """Consolidated motifs must be inside a <details> element."""
    arrete = _make_testing_arrete_file(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="arrete",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>Titre</h1></div>
 <div data-spec="motifs">MOTIF 1</div>
</body></html>
""",
    )

    html = make_permit_motif([arrete])
    soup = BeautifulSoup(html, "html.parser")
    details = soup.find("details")
    assert details is not None
    assert "Considérants" in details.get_text()
    assert "MOTIF 1" in details.get_text()


def test_make_permit_header_raises_when_multiple_aiot_detected() -> None:
    arrete_1 = _make_testing_arrete_file(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="arrete_1",
        html='<html><body data-arretify_version="0.1.0"></body></html>',
    )
    arrete_2 = _make_testing_arrete_file(
        arrete_id="2022-01-01",
        aiot="0002",
        filename="arrete_2",
        html='<html><body data-arretify_version="0.1.0"></body></html>',
    )

    with pytest.raises(ValueError, match="multiple AIOT"):
        make_permit_header([arrete_1, arrete_2])


def test_make_permit_other_contains_only_non_consolidated_complements() -> None:
    ap_initial = _make_testing_arrete_file(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_initial",
        html=(
            '<html><body data-arretify_version="0.1.0"><main data-spec="main">'
            "</main></body></html>"
        ),
    )
    complement_no_ops = _make_testing_arrete_file(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="complement_no_ops",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID COMPLEMENT A</div>
 <div data-spec="arrete_title">TITLE COMPLEMENT A</div>
 <main data-spec="main"><p>MAIN A</p></main>
</body></html>
""",
    )
    complement_with_ops = _make_testing_arrete_file(
        arrete_id="2022-01-01",
        aiot="0001",
        filename="complement_with_ops",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID COMPLEMENT B</div>
 <div data-spec="arrete_title">TITLE COMPLEMENT B</div>
 <main data-spec="main"><p>MAIN B</p></main>
</body></html>
""",
    )
    operations = [
        Operation(
            id="op-1",
            source_id=NodeId(arrete_id="2022-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
        )
    ]

    html = make_permit_other([ap_initial, complement_no_ops, complement_with_ops], operations)

    assert 'data-spec="permit_complements"' in html
    assert 'data-spec="permit_complement"' in html
    assert "ID COMPLEMENT A" in html
    assert "TITLE COMPLEMENT A" in html
    assert "MAIN A" in html
    assert "MAIN B" not in html


def test_make_section_version_sets_default_attrs_when_article_not_in_history() -> None:
    section = BeautifulSoup(
        '<section data-spec="section" data-number="1"><p>Texte initial</p></section>',
        "html.parser",
    ).find("section")
    assert section is not None

    make_section_version(
        section=section,
        article_id="1",
        history={},
        ap_initial_id="2020-01-01",
        operation_by_id={},
    )

    assert section["data-spec"] == "section_version"
    assert section["data-is_modified"] == "false"
    assert section["data-date_version"] == "2020-01-01"
    assert "Texte initial" in str(section)


def test_make_section_version_marks_removed_article() -> None:
    section = BeautifulSoup(
        '<section data-spec="section" data-number="1"><p>Texte initial</p></section>',
        "html.parser",
    ).find("section")
    assert section is not None

    operation = Operation(
        id="op-remove",
        source_id=NodeId(arrete_id="2021-01-01", article_id="3"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REMOVE,
    )

    history = {
        NodeId(arrete_id="2020-01-01", article_id="1"): [
            cast(
                ArticleVersion,
                {"version": 0, "content": "<p>Texte initial</p>", "operation_id": None},
            ),
            cast(ArticleVersion, {"version": 1, "content": "", "operation_id": "op-remove"}),
        ]
    }

    make_section_version(
        section=section,
        article_id="1",
        history=history,
        ap_initial_id="2020-01-01",
        operation_by_id={"op-remove": operation},
    )

    assert section["data-spec"] == "section_version"
    assert section["data-is_modified"] == "true"
    assert section["data-date_version"] == "2021-01-01"
    assert "Article abrogé" in str(section)


def test_make_section_version_partial_remove_does_not_mark_abrogated() -> None:
    """A REMOVE with a partial sub_target must not mark the article as abrogated."""
    section = BeautifulSoup(
        '<section data-spec="section" data-number="1"><p>Texte initial</p></section>',
        "html.parser",
    ).find("section")
    assert section is not None

    operation = Operation(
        id="op-partial-remove",
        source_id=NodeId(arrete_id="2024-09-27", article_id="APPENDIX:3.1"),
        target_id=NodeId(arrete_id="2009-12-08", article_id="1"),
        operation_type=OperationType.REMOVE,
        sub_target=SubTarget(
            type=SubTargetType.TABLEAU,
            description="premier alinéa après le tableau",
        ),
    )

    history = {
        NodeId(arrete_id="2009-12-08", article_id="1"): [
            cast(
                ArticleVersion,
                {"version": 0, "content": "<p>Texte initial</p>", "operation_id": None},
            ),
            cast(
                ArticleVersion,
                {
                    "version": 1,
                    "content": "<p>Texte après suppression partielle</p>",
                    "operation_id": "op-partial-remove",
                },
            ),
        ]
    }

    make_section_version(
        section=section,
        article_id="1",
        history=history,
        ap_initial_id="2009-12-08",
        operation_by_id={"op-partial-remove": operation},
    )

    assert section["data-is_modified"] == "true"
    assert "Article abrogé" not in str(section)
    assert "Texte après suppression partielle" in str(section)


def test_make_section_version_full_remove_marks_abrogated() -> None:
    """A REMOVE with sub_target FULL_SECTION/ALL must mark the article as abrogated."""
    section = BeautifulSoup(
        '<section data-spec="section" data-number="1"><p>Texte initial</p></section>',
        "html.parser",
    ).find("section")
    assert section is not None

    operation = Operation(
        id="op-full-remove",
        source_id=NodeId(arrete_id="2024-09-27", article_id="APPENDIX:3.1"),
        target_id=NodeId(arrete_id="2009-12-08", article_id="1"),
        operation_type=OperationType.REMOVE,
        sub_target=SubTarget(
            type=SubTargetType.FULL_SECTION,
            description="ALL",
        ),
    )

    history = {
        NodeId(arrete_id="2009-12-08", article_id="1"): [
            cast(
                ArticleVersion,
                {"version": 0, "content": "<p>Texte initial</p>", "operation_id": None},
            ),
            cast(
                ArticleVersion,
                {"version": 1, "content": "", "operation_id": "op-full-remove"},
            ),
        ]
    }

    make_section_version(
        section=section,
        article_id="1",
        history=history,
        ap_initial_id="2009-12-08",
        operation_by_id={"op-full-remove": operation},
    )

    assert section["data-is_modified"] == "true"
    assert "Article abrogé" in str(section)


def test_make_permit_content_starts_from_first_non_abrogated_arrete() -> None:
    """When the initial arrêté is abrogated (refonte), content starts from the next one."""
    ap_2020_abroge = _make_testing_arrete_file(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_2020_abroge",
        html="""
<html><body data-arretify_version="0.1.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Article 1 ancien</p></section>
 </main>
</body></html>
""",
        status=False,
    )
    ap_2021_refonte = _make_testing_arrete_file(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="ap_2021_refonte",
        html="""
<html><body data-arretify_version="0.1.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Article 1 refonte</p></section>
  <section data-spec="section" data-number="2"><p>Article 2 refonte</p></section>
 </main>
</body></html>
""",
        status=True,
    )

    history: ArticleHistory = {}
    html = make_permit_content(
        history=history,
        arrete_files=[ap_2020_abroge, ap_2021_refonte],
        operations=[],
    )

    assert "Article 1 refonte" in html
    assert "Article 2 refonte" in html
    assert "Article 1 ancien" not in html


def test_make_permit_content_renders_full_main_with_section_versions() -> None:
    ap_initial = _make_testing_arrete_file(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_initial",
        html="""
<html><body data-arretify_version="0.1.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Article 1 initial</p></section>
  <section data-spec="section" data-number="2"><p>Article 2 initial</p></section>
 </main>
</body></html>
""",
    )

    op_replace = Operation(
        id="op-replace-1",
        source_id=NodeId(arrete_id="2021-06-01", article_id="5"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
    )

    history = {
        NodeId(arrete_id="2020-01-01", article_id="1"): [
            cast(
                ArticleVersion,
                {"version": 0, "content": "<p>Article 1 initial</p>", "operation_id": None},
            ),
            cast(
                ArticleVersion,
                {
                    "version": 1,
                    "content": "<p>Article 1 modifié</p>",
                    "operation_id": "op-replace-1",
                },
            ),
        ]
    }

    html = make_permit_content(
        history=history,
        arrete_files=[ap_initial],
        operations=[op_replace],
    )

    assert 'data-spec="main"' in html
    assert html.count('data-spec="section_version"') == 2
    assert "Article 1 modifié" in html
    assert "Article 2 initial" in html
    assert 'data-date_version="2021-06-01"' in html
    assert 'data-date_version="2020-01-01"' in html


@patch("ocapi.step_rendering.step_rendering.make_permit_other", return_value="<other/>")
@patch("ocapi.step_rendering.step_rendering.make_permit_header", return_value="<header/>")
@patch("ocapi.step_rendering.step_rendering.make_permit_content", return_value="<content/>")
def test_step_rendering_returns_permis(
    mock_content: MagicMock,
    mock_header: MagicMock,
    mock_other: MagicMock,
) -> None:
    """Verify that step_rendering assembles the 3 permit components and returns a valid Permis."""
    history = cast(ArticleHistory, {})
    operations = cast(list[Operation], [])
    arretes = cast(list[ArreteFile], [MagicMock()])

    result = step_rendering(history, operations, arretes)

    mock_content.assert_called_once_with(history, arretes, operations)
    mock_header.assert_called_once_with(arretes)
    mock_other.assert_called_once_with(arretes, operations=operations)

    assert isinstance(result, Permis)
    assert result.header == "<header/>"
    assert result.contenu == "<content/>"
    assert result.other == "<other/>"


def test_has_not_out_ops_returns_true_without_operation() -> None:
    arrete_file = _make_testing_arrete_file(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="without_ops",
        html='<html><body data-arretify_version="0.1.0"></body></html>',
    )

    assert has_not_out_ops(arrete_file, []) is True


def test_has_not_out_ops_returns_true_when_operations_apply_to_other_arrete() -> None:
    arrete_file = _make_testing_arrete_file(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="with_unrelated_ops",
        html='<html><body data-arretify_version="0.1.0"></body></html>',
    )
    operations = [
        Operation(
            id="op-1",
            source_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
        )
    ]

    assert has_not_out_ops(arrete_file, operations) is True


def test_has_not_out_ops_returns_false_with_multiple_operations() -> None:
    arrete_file = _make_testing_arrete_file(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="with_ops",
        html='<html><body data-arretify_version="0.1.0"></body></html>',
    )
    operations = [
        Operation(
            id="op-1",
            source_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2019-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
        ),
        Operation(
            id="op-2",
            source_id=NodeId(arrete_id="2021-01-01", article_id="2"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
            operation_type=OperationType.ADD,
        ),
        Operation(
            id="op-3",
            source_id=NodeId(arrete_id="2021-01-01", article_id="3"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="3"),
            operation_type=OperationType.REMOVE,
        ),
    ]

    assert has_not_out_ops(arrete_file, operations) is False


class TestIsAbrogated:
    """Direct unit tests for _is_abrogated edge cases."""

    @staticmethod
    def _make_version(operation_id: str | None) -> ArticleVersion:
        return cast(
            ArticleVersion,
            {"version": 1, "content": "", "operation_id": operation_id},
        )

    def test_no_operation_id_returns_false(self) -> None:
        assert _is_abrogated(self._make_version(None), {}) is False

    def test_unknown_operation_id_returns_false(self) -> None:
        assert _is_abrogated(self._make_version("unknown"), {}) is False

    def test_replace_operation_returns_false(self) -> None:
        op = Operation(
            id="op-r",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
        )
        assert _is_abrogated(self._make_version("op-r"), {"op-r": op}) is False

    def test_add_operation_returns_false(self) -> None:
        op = Operation(
            id="op-a",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.ADD,
        )
        assert _is_abrogated(self._make_version("op-a"), {"op-a": op}) is False

    def test_remove_no_sub_target_returns_true(self) -> None:
        op = Operation(
            id="op-rm",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
        )
        assert _is_abrogated(self._make_version("op-rm"), {"op-rm": op}) is True

    def test_remove_full_section_all_returns_true(self) -> None:
        op = Operation(
            id="op-fs",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="ALL"),
        )
        assert _is_abrogated(self._make_version("op-fs"), {"op-fs": op}) is True

    def test_remove_full_section_contenu_entier_returns_true(self) -> None:
        op = Operation(
            id="op-ce",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="contenu entier"),
        )
        assert _is_abrogated(self._make_version("op-ce"), {"op-ce": op}) is True

    def test_remove_tableau_returns_false(self) -> None:
        op = Operation(
            id="op-tab",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.TABLEAU, description="tableau X"),
        )
        assert _is_abrogated(self._make_version("op-tab"), {"op-tab": op}) is False

    def test_remove_alinea_returns_false(self) -> None:
        op = Operation(
            id="op-al",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.ALINEA, description="premier alinéa"),
        )
        assert _is_abrogated(self._make_version("op-al"), {"op-al": op}) is False

    def test_remove_phrase_returns_false(self) -> None:
        op = Operation(
            id="op-ph",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.PHRASE, description="phrase Y"),
        )
        assert _is_abrogated(self._make_version("op-ph"), {"op-ph": op}) is False

    def test_remove_complex_returns_false(self) -> None:
        op = Operation(
            id="op-cx",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.COMPLEX, description="desc"),
        )
        assert _is_abrogated(self._make_version("op-cx"), {"op-cx": op}) is False

    def test_remove_full_section_other_description_returns_false(self) -> None:
        op = Operation(
            id="op-other",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="titre uniquement"),
        )
        assert _is_abrogated(self._make_version("op-other"), {"op-other": op}) is False


def test_make_section_version_places_previous_version_in_details_only() -> None:
    section = BeautifulSoup(
        '<section data-spec="section" data-number="1"><p>Article 1 initial</p></section>',
        "html.parser",
    ).find("section")
    assert section is not None

    operation = Operation(
        id="op-1",
        source_id=NodeId(arrete_id="2021-01-01", article_id="2"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
    )
    history = {
        NodeId(arrete_id="2020-01-01", article_id="1"): [
            cast(
                ArticleVersion,
                {"version": 0, "content": "<p>Article 1 version 0</p>", "operation_id": None},
            ),
            cast(
                ArticleVersion,
                {"version": 1, "content": "<p>Article 1 modifié</p>", "operation_id": "op-1"},
            ),
        ]
    }

    make_section_version(
        section=section,
        article_id="1",
        history=history,
        ap_initial_id="2020-01-01",
        operation_by_id={"op-1": operation},
    )
    rendered_soup = BeautifulSoup(str(section), "html.parser")
    history_section = rendered_soup.select_one('[data-spec="section_version_history"]')

    details = rendered_soup.find_all("details")
    assert len(details) == 1
    assert history_section is not None
    details_text = details[0].get_text(" ", strip=True)
    assert "Article 1 version 0" in details_text
    assert "Article 1 modifié" not in details_text

    assert (
        history_section.find(
            string=lambda text: isinstance(text, str) and "Article 1 modifié" in text
        )
        is None
    )
    assert rendered_soup.find(
        string=lambda text: isinstance(text, str) and "Article 1 modifié" in text
    )


def test_make_section_version_displays_unresolved_operation_message() -> None:
    section = BeautifulSoup(
        '<section data-spec="section" data-number="1"><p>Article 1 initial</p></section>',
        "html.parser",
    ).find("section")
    assert section is not None

    operation = Operation(
        id="op-1",
        source_id=NodeId(arrete_id="2021-01-01", article_id="2"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
        extractable_content=False,
    )
    history = {
        NodeId(arrete_id="2020-01-01", article_id="1"): [
            cast(
                ArticleVersion,
                {
                    "version": 0,
                    "content": "<p>Article 1 version 0</p>",
                    "operation_id": None,
                    "status_code": "RESOLVED",
                },
            ),
            cast(
                ArticleVersion,
                {
                    "version": 1,
                    "content": "<p>Article 1 version 0</p>",
                    "operation_id": "op-1",
                    "status_code": "ERROR_EXTRACTING_CONTENT",
                },
            ),
        ]
    }

    make_section_version(
        section=section,
        article_id="1",
        history=history,
        ap_initial_id="2020-01-01",
        operation_by_id={"op-1": operation},
    )

    rendered = str(section)
    assert "Opération non résolue modification de l'article 2 de l'arrêté 2021-01-01" in rendered
