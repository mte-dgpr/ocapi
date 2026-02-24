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

import pytest
from bs4 import BeautifulSoup

from ocapi.step_rendering.make_header import make_permit_header
from ocapi.step_rendering.make_main_content import make_permit_content, make_section_version
from ocapi.step_rendering.make_other import has_not_out_ops, make_permit_other
from ocapi.types import ArreteFile, ArticleVersion, NodeId, Operation, OperationType


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
    assert len(details) >= 2
    assert history_section is not None
    details_text = details[1].get_text(" ", strip=True)
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
