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

import pytest
from bs4 import BeautifulSoup

from ocapi.exceptions import OcapiError
from ocapi.step_rendering.main_content import (
    _is_abrogated,
    _select_initial_ap,
    make_permit_content,
    make_section_version,
)
from ocapi.types import (
    ERROR_CODE_MESSAGES,
    ArreteFile,
    ArticleHistory,
    ArticleVersion,
    ErrorCode,
    FileType,
    NodeId,
    Operation,
    OperationType,
    SubTarget,
    SubTargetType,
    status_codes_reason,
)
from ocapi.utils.testing import make_testing_arrete, make_testing_article_version


class TestIntegrationWithArticleFilter:
    """Verify superfluous sections are excluded from the consolidated HTML."""

    def test_superfluous_articles_excluded_from_permit(self) -> None:
        html = """
<html><body data-arretify_version="0.2.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1" data-title="DISPOSITIONS GÉNÉRALES">
   <h1 data-spec="section_title">ARTICLE 1 DISPOSITIONS GÉNÉRALES</h1>
   <p>Article important</p>
  </section>
  <section data-spec="section" data-number="2" data-title="FRAIS">
   <h1 data-spec="section_title">ARTICLE 2 FRAIS</h1>
   <p>Article superflu</p>
  </section>
  <section data-spec="section" data-number="3" data-title="SANCTIONS">
   <h1 data-spec="section_title">ARTICLE 3 SANCTIONS</h1>
   <p>Autre article superflu</p>
  </section>
 </main>
</body></html>
"""
        arrete = ArreteFile(
            id="2020-01-01",
            aiot="0001",
            filename="ap_initial",
            soup=BeautifulSoup(html, "html.parser"),
            status=True,
        )
        history: ArticleHistory = {}
        result = make_permit_content(history, [arrete], [])

        assert "Article important" in result
        assert "Article superflu" not in result
        assert "Autre article superflu" not in result


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


def test_make_section_version_skips_invalid_article_id() -> None:
    """Non-standard article_id (e.g. containing spaces) is gracefully skipped."""
    section = BeautifulSoup(
        '<section data-spec="section" data-number="bad id!"><p>Content</p></section>',
        "html.parser",
    ).find("section")
    assert section is not None

    make_section_version(
        section=section,
        article_id="bad id!",
        history={},
        ap_initial_id="2020-01-01",
        operation_by_id={},
    )

    assert section["data-spec"] == "section_version"
    assert section["data-is_modified"] == "false"
    assert section["data-date_version"] == "2020-01-01"
    assert "Content" in str(section)


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
    ap_2020_abroge = make_testing_arrete(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_2020_abroge",
        html="""
<html><body data-arretify_version="0.2.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Article 1 ancien</p></section>
 </main>
</body></html>
""",
        status=False,
    )
    ap_2021_refonte = make_testing_arrete(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="ap_2021_refonte",
        html="""
<html><body data-arretify_version="0.2.0">
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


def test_make_permit_content_prefers_last_ap_autorisation_as_initial() -> None:
    """When an old complementary AP comes first, the latest AP_AUTORISATION is used."""
    ap_complement_old = make_testing_arrete(
        arrete_id="2018-01-01",
        aiot="0001",
        filename="ap_complement_old",
        html="""
<html><body data-arretify_version="0.2.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Old complement</p></section>
 </main>
</body></html>
""",
        file_type=FileType.AP_COMPLEMENTAIRE,
    )

    ap_refonte = make_testing_arrete(
        arrete_id="2022-01-01",
        aiot="0001",
        filename="ap_refonte",
        html="""
<html><body data-arretify_version="0.2.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Refonte content</p></section>
 </main>
</body></html>
""",
        file_type=FileType.AP_AUTORISATION,
    )

    history: ArticleHistory = {}
    html = make_permit_content(
        history=history,
        arrete_files=[ap_complement_old, ap_refonte],
        operations=[],
    )

    assert "Refonte content" in html
    assert "Old complement" not in html


def test_make_permit_content_renders_full_main_with_section_versions() -> None:
    """Layout / section_version behaviour; kept for future refonte of permit HTML."""
    ap_initial = make_testing_arrete(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_initial",
        html="""
<html><body data-arretify_version="0.2.0">
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


def test_make_permit_content_inserts_new_article_after_predecessor() -> None:
    """NEW_ARTICLE sections are inserted after the greatest existing article id below them."""
    ap_initial = make_testing_arrete(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_initial",
        html="""
<html><body data-arretify_version="0.2.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Article 1 initial</p></section>
  <section data-spec="section" data-number="3"><p>Article 3 initial</p></section>
 </main>
</body></html>
""",
    )
    new_key = NodeId(arrete_id="2020-01-01", article_id="NEW_ARTICLE:2")
    history = {
        new_key: [
            cast(
                ArticleVersion,
                {
                    "version": 0,
                    "content": (
                        '<section data-spec="section" data-number="2">'
                        "<p>Article 2 inséré</p></section>"
                    ),
                    "operation_id": "op-create-2",
                },
            )
        ]
    }
    op_create = Operation(
        id="op-create-2",
        source_id=NodeId(arrete_id="2021-06-01", article_id="1"),
        target_id=new_key,
        operation_type=OperationType.ADD,
        sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="contenu entier"),
    )
    html = make_permit_content(
        history=history,
        arrete_files=[ap_initial],
        operations=[op_create],
    )
    assert html.index("Article 1 initial") < html.index("Article 2 inséré")
    assert html.index("Article 2 inséré") < html.index("Article 3 initial")


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
        status_code=frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND}),
    )
    history = {
        NodeId(arrete_id="2020-01-01", article_id="1"): [
            cast(
                ArticleVersion,
                {
                    "version": 0,
                    "content": "<p>Article 1 version 0</p>",
                    "operation_id": None,
                    "status_code": frozenset(),
                },
            ),
            cast(
                ArticleVersion,
                {
                    "version": 1,
                    "content": "<p>Article 1 version 0</p>",
                    "operation_id": "op-1",
                    "status_code": frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND}),
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
    assert "(raison :" in rendered
    assert "n'a pas pu être extrait de l'arrêté modificatif" in rendered


# status_codes_reason helper


def test_status_codes_reason_returns_none_for_empty() -> None:
    assert status_codes_reason(frozenset()) is None


def test_status_codes_reason_returns_none_for_none() -> None:
    assert status_codes_reason(None) is None


def test_status_codes_reason_covers_all_error_codes() -> None:
    for code in ErrorCode:
        assert code in ERROR_CODE_MESSAGES, f"Missing message for ErrorCode.{code.name}"


def test_status_codes_reason_returns_message_for_error_extracting_operand() -> None:
    reason = status_codes_reason(frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND}))
    assert reason is not None
    assert "extrait de l'arrêté modificatif" in reason


def test_status_codes_reason_returns_message_for_error_extracting_target() -> None:
    reason = status_codes_reason(frozenset({ErrorCode.ERROR_EXTRACTING_TARGET}))
    assert reason is not None
    assert "article cible" in reason


def test_status_codes_reason_joins_multiple_messages() -> None:
    reason = status_codes_reason(
        frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND, ErrorCode.PROPAGATED_ERROR})
    )
    assert reason is not None
    assert "extrait de l'arrêté modificatif" in reason
    assert "opération précédente" in reason
    assert " ; " in reason


@pytest.mark.parametrize(
    "status_code",
    [
        frozenset({ErrorCode.ERROR_FINDING_SUBTARGET}),
        frozenset({ErrorCode.COMPLEX_SUBTARGET}),
    ],
)
def test_make_section_version_displays_unresolved_message_for_subtarget_errors(
    status_code: frozenset[ErrorCode],
) -> None:
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
                {
                    "version": 0,
                    "content": "<p>Article 1 version 0</p>",
                    "operation_id": None,
                    "status_code": frozenset(),
                },
            ),
            cast(
                ArticleVersion,
                {
                    "version": 1,
                    "content": "<p>Article 1 version 0</p>",
                    "operation_id": "op-1",
                    "status_code": status_code,
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


def test_make_section_version_displays_error_extracting_target_reason() -> None:
    section = BeautifulSoup(
        '<section data-spec="section" data-number="1"><p>Initial</p></section>',
        "html.parser",
    ).find("section")
    assert section is not None

    operation = Operation(
        id="op-target",
        source_id=NodeId(arrete_id="2021-01-01", article_id="3"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
        status_code=frozenset({ErrorCode.ERROR_EXTRACTING_TARGET}),
    )
    history = {
        NodeId(arrete_id="2020-01-01", article_id="1"): [
            cast(
                ArticleVersion,
                {"version": 0, "content": "", "operation_id": None},
            ),
            cast(
                ArticleVersion,
                {
                    "version": 1,
                    "content": "",
                    "operation_id": "op-target",
                    "status_code": frozenset({ErrorCode.ERROR_EXTRACTING_TARGET}),
                },
            ),
        ]
    }
    make_section_version(
        section=section,
        article_id="1",
        history=history,
        ap_initial_id="2020-01-01",
        operation_by_id={"op-target": operation},
    )
    rendered = str(section)
    assert "Opération non résolue" in rendered
    assert "(raison :" in rendered
    assert "article cible" in rendered


class TestIsAbrogated:
    """Direct unit tests for _is_abrogated edge cases."""

    def test_no_operation_id_returns_false(self) -> None:
        assert _is_abrogated(make_testing_article_version(None), {}) is False

    def test_unknown_operation_id_returns_false(self) -> None:
        assert _is_abrogated(make_testing_article_version("unknown"), {}) is False

    def test_replace_operation_returns_false(self) -> None:
        op = Operation(
            id="op-r",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
        )
        assert _is_abrogated(make_testing_article_version("op-r"), {"op-r": op}) is False

    def test_add_operation_returns_false(self) -> None:
        op = Operation(
            id="op-a",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.ADD,
        )
        assert _is_abrogated(make_testing_article_version("op-a"), {"op-a": op}) is False

    def test_remove_no_sub_target_returns_true(self) -> None:
        op = Operation(
            id="op-rm",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
        )
        assert _is_abrogated(make_testing_article_version("op-rm"), {"op-rm": op}) is True

    def test_remove_full_section_all_returns_true(self) -> None:
        op = Operation(
            id="op-fs",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="ALL"),
        )
        assert _is_abrogated(make_testing_article_version("op-fs"), {"op-fs": op}) is True

    def test_remove_full_section_contenu_entier_returns_true(self) -> None:
        op = Operation(
            id="op-ce",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="contenu entier"),
        )
        assert _is_abrogated(make_testing_article_version("op-ce"), {"op-ce": op}) is True

    def test_remove_tableau_returns_false(self) -> None:
        op = Operation(
            id="op-tab",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.TABLEAU, description="tableau X"),
        )
        assert _is_abrogated(make_testing_article_version("op-tab"), {"op-tab": op}) is False

    def test_remove_alinea_returns_false(self) -> None:
        op = Operation(
            id="op-al",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.ALINEA, description="premier alinéa"),
        )
        assert _is_abrogated(make_testing_article_version("op-al"), {"op-al": op}) is False

    def test_remove_phrase_returns_false(self) -> None:
        op = Operation(
            id="op-ph",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.PHRASE, description="phrase Y"),
        )
        assert _is_abrogated(make_testing_article_version("op-ph"), {"op-ph": op}) is False

    def test_remove_complex_returns_false(self) -> None:
        op = Operation(
            id="op-cx",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.COMPLEX, description="desc"),
        )
        assert _is_abrogated(make_testing_article_version("op-cx"), {"op-cx": op}) is False

    def test_remove_full_section_other_description_returns_false(self) -> None:
        op = Operation(
            id="op-other",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="titre uniquement"),
        )
        assert _is_abrogated(make_testing_article_version("op-other"), {"op-other": op}) is False


class TestSelectInitialAp:
    """Cover the user-provided principal flag in _select_initial_ap."""

    def test_principal_flag_overrides_heuristic(self) -> None:
        older = make_testing_arrete("2018-01-01", file_type=FileType.AP_AUTORISATION)
        refonte = make_testing_arrete("2022-01-01", file_type=FileType.AP_AUTORISATION)
        older.principal = True

        assert _select_initial_ap([older, refonte]) is older

    def test_multiple_principals_raise(self) -> None:
        first = make_testing_arrete("2018-01-01")
        second = make_testing_arrete("2022-01-01")
        first.principal = True
        second.principal = True

        with pytest.raises(OcapiError):
            _select_initial_ap([first, second])

    def test_no_principal_keeps_existing_heuristic(self) -> None:
        older = make_testing_arrete("2018-01-01", file_type=FileType.AP_AUTORISATION)
        refonte = make_testing_arrete("2022-01-01", file_type=FileType.AP_AUTORISATION)

        assert _select_initial_ap([older, refonte]) is refonte


def test_make_permit_content_marks_main_ap_source_articles() -> None:
    """Operations sourced from the main AP get a result message in their source article."""
    html = """
<html><body data-arretify_version="0.2.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><h3>Art 1</h3><p>Source article</p></section>
  <section data-spec="section" data-number="2"><h3>Art 2</h3><p>Other</p></section>
 </main>
</body></html>
"""
    arrete = make_testing_arrete("2021-01-01", html)
    op_ok = Operation(
        id="op-1",
        source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="3"),
        operation_type=OperationType.REPLACE,
    )
    op_err = Operation(
        id="op-2",
        source_id=NodeId(arrete_id="2021-01-01", article_id="2"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="4"),
        operation_type=OperationType.REMOVE,
    )
    history: ArticleHistory = {
        NodeId(arrete_id="2020-01-01", article_id="3"): [
            cast(ArticleVersion, {"version": 0, "content": "old", "operation_id": None}),
            cast(ArticleVersion, {"version": 1, "content": "new", "operation_id": "op-1"}),
        ],
        NodeId(arrete_id="2020-01-01", article_id="4"): [
            cast(ArticleVersion, {"version": 0, "content": "old", "operation_id": None}),
            cast(
                ArticleVersion,
                {
                    "version": 1,
                    "content": "old",
                    "operation_id": "op-2",
                    "status_code": StatusCode.ERROR_FINDING_SUBTARGET,
                },
            ),
        ],
    }

    result = make_permit_content(history, [arrete], [op_ok, op_err])

    soup = BeautifulSoup(result, "html.parser")
    section_1 = soup.find("section", attrs={"data-number": "1"})
    section_2 = soup.find("section", attrs={"data-number": "2"})
    assert section_1 is not None and section_2 is not None
    msg_1 = section_1.find("div", attrs={"data-spec": "operation_result"})
    msg_2 = section_2.find("div", attrs={"data-spec": "operation_result"})
    assert msg_1 is not None
    assert "Opération de consolidation résolue" in msg_1.get_text()
    assert "l'article 3 de l'arrêté 2020-01-01" in msg_1.get_text()
    assert msg_2 is not None
    assert "Opération de consolidation non résolue" in msg_2.get_text()
    assert "sous-cible" in msg_2.get_text()
