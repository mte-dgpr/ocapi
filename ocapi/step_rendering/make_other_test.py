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
from bs4 import BeautifulSoup, Tag

from ocapi.step_rendering.make_other import has_unresolved_or_zero_ops, make_permit_other
from ocapi.types import ArreteFile, ArticleHistory, NodeId, Operation, OperationType, StatusCode


def _make_arrete(arrete_id: str, html: str, aiot: str = "0001", status: bool = True) -> ArreteFile:
    return ArreteFile(
        id=arrete_id,
        aiot=aiot,
        filename=f"{arrete_id}.html",
        soup=BeautifulSoup(html, "html.parser"),
        status=status,
    )


_EMPTY_AP = '<html><body data-arretify_version="0.1.0"><main data-spec="main"></main></body></html>'


def test_make_permit_other_contains_only_non_consolidated_complements() -> None:
    ap_initial = _make_arrete("2020-01-01", _EMPTY_AP)
    complement_no_ops = _make_arrete(
        "2021-01-01",
        """
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID COMPLEMENT A</div>
 <div data-spec="arrete_title">TITLE COMPLEMENT A</div>
 <main data-spec="main"><p>MAIN A</p></main>
</body></html>
""",
    )
    complement_with_ops = _make_arrete(
        "2022-01-01",
        """
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
    assert "MAIN B" in html


def test_make_permit_other_includes_modifying_arretes_with_operation_messages() -> None:
    """Modifying arrêtés appear with operation result messages in source articles."""
    ap_initial = _make_arrete("2020-01-01", _EMPTY_AP)
    modifying = _make_arrete(
        "2022-01-01",
        """
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID MOD</div>
 <div data-spec="arrete_title">TITLE MOD</div>
 <main data-spec="main">
  <section data-spec="section" data-number="1"><h3>Art 1</h3><p>Source article</p></section>
 </main>
</body></html>
""",
    )
    op = Operation(
        id="op-1",
        source_id=NodeId(arrete_id="2022-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="3"),
        operation_type=OperationType.REPLACE,
    )
    history: ArticleHistory = {
        NodeId(arrete_id="2020-01-01", article_id="3"): [
            {"version": 0, "title": "", "content": "old", "operation_id": None},
            {"version": 1, "title": "", "content": "new", "operation_id": "op-1"},
        ],
    }

    html = make_permit_other([ap_initial, modifying], [op], history=history)

    assert 'data-spec="permit_modifying"' in html
    assert "ID MOD" in html
    assert "TITLE MOD" in html
    assert "Opération de consolidation résolue" in html
    assert "l'article 3 de l'arrêté 2020-01-01" in html
    # Message should appear after the title, not at the end
    soup = BeautifulSoup(html, "html.parser")
    section = soup.find("section", attrs={"data-spec": "section"})
    assert section is not None
    children = [c for c in section.children if isinstance(c, Tag) and c.name]
    assert children[0].name == "h3"
    assert children[1].get("data-spec") == "operation_result"


def test_make_permit_other_shows_unresolved_message_for_failed_operation() -> None:
    """Unresolved operations get a reason in source article messages."""
    ap_initial = _make_arrete("2020-01-01", _EMPTY_AP)
    modifying = _make_arrete(
        "2022-01-01",
        """
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID MOD</div>
 <div data-spec="arrete_title">TITLE MOD</div>
 <main data-spec="main">
  <section data-spec="section" data-number="2"><p>Source</p></section>
 </main>
</body></html>
""",
    )
    op = Operation(
        id="op-err",
        source_id=NodeId(arrete_id="2022-01-01", article_id="2"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="5"),
        operation_type=OperationType.REMOVE,
    )
    history: ArticleHistory = {
        NodeId(arrete_id="2020-01-01", article_id="5"): [
            {"version": 0, "title": "", "content": "old", "operation_id": None},
            {
                "version": 1,
                "title": "",
                "content": "old",
                "operation_id": "op-err",
                "status_code": StatusCode.ERROR_FINDING_SUBTARGET,
            },
        ],
    }

    html = make_permit_other([ap_initial, modifying], [op], history=history)

    assert "Opération de consolidation non résolue" in html
    assert "l'article 5 de l'arrêté 2020-01-01" in html
    assert "sous-cible" in html


def test_make_permit_other_skips_abrogated_modifying_arrete() -> None:
    """Abrogated modifying arrêtés are not displayed."""
    ap_initial = _make_arrete("2020-01-01", _EMPTY_AP)
    abrogated = _make_arrete(
        "2022-01-01",
        """
<html><body data-arretify_version="0.1.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Gone</p></section>
 </main>
</body></html>
""",
        status=False,
    )
    op = Operation(
        id="op-1",
        source_id=NodeId(arrete_id="2022-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
    )

    html = make_permit_other([ap_initial, abrogated], [op], history={})

    assert html == ""


def test_target_all_shows_arrete_only() -> None:
    """Target article_id=ALL displays only the arrêté reference, no article number."""
    ap_initial = _make_arrete("2020-01-01", _EMPTY_AP)
    modifying = _make_arrete(
        "2022-01-01",
        """
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID</div>
 <div data-spec="arrete_title">TITLE</div>
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Source</p></section>
 </main>
</body></html>
""",
    )
    op = Operation(
        id="op-all",
        source_id=NodeId(arrete_id="2022-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="ALL"),
        operation_type=OperationType.REPLACE,
    )
    history: ArticleHistory = {
        NodeId(arrete_id="2020-01-01", article_id="ALL"): [
            {"version": 0, "title": "", "content": "", "operation_id": None},
            {"version": 1, "title": "", "content": "x", "operation_id": "op-all"},
        ],
    }

    html = make_permit_other([ap_initial, modifying], [op], history=history)

    assert "l'arrêté 2020-01-01" in html
    assert "l'article ALL" not in html


def test_target_new_article_strips_prefix() -> None:
    """Target article_id=NEW_ARTICLE:4.1 renders as 'l'article 4.1'."""
    ap_initial = _make_arrete("2020-01-01", _EMPTY_AP)
    modifying = _make_arrete(
        "2022-01-01",
        """
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID</div>
 <div data-spec="arrete_title">TITLE</div>
 <main data-spec="main">
  <section data-spec="section" data-number="1"><p>Source</p></section>
 </main>
</body></html>
""",
    )
    op = Operation(
        id="op-new",
        source_id=NodeId(arrete_id="2022-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-01-01", article_id="NEW_ARTICLE:4.1"),
        operation_type=OperationType.ADD,
    )
    history: ArticleHistory = {
        NodeId(arrete_id="2020-01-01", article_id="NEW_ARTICLE:4.1"): [
            {"version": 0, "title": "", "content": "new", "operation_id": "op-new"},
        ],
    }

    html = make_permit_other([ap_initial, modifying], [op], history=history)

    assert "l'article 4.1" in html
    assert "NEW_ARTICLE" not in html


# ---------------------------------------------------------------------------
# has_unresolved_or_zero_ops
# ---------------------------------------------------------------------------


def test_has_unresolved_or_zero_ops_returns_true_without_operation() -> None:
    arrete_file = _make_arrete(
        "2021-01-01", '<html><body data-arretify_version="0.1.0"></body></html>'
    )
    assert has_unresolved_or_zero_ops(arrete_file, []) is True


def test_has_unresolved_or_zero_ops_returns_true_when_operations_apply_to_other_arrete() -> None:
    arrete_file = _make_arrete(
        "2021-01-01", '<html><body data-arretify_version="0.1.0"></body></html>'
    )
    operations = [
        Operation(
            id="op-1",
            source_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
        )
    ]
    assert has_unresolved_or_zero_ops(arrete_file, operations) is True


def test_returns_true_with_unresolved_outgoing_ops() -> None:
    arrete = _make_arrete("2021-01-01", _EMPTY_AP)
    ops = [
        Operation(
            id="op-1",
            source_id=NodeId(arrete_id="2021-01-01", article_id="2"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
            operation_type=OperationType.ADD,
        ),
    ]
    assert has_unresolved_or_zero_ops(arrete, ops) is True


def test_returns_false_when_all_outgoing_ops_resolved() -> None:
    arrete = _make_arrete("2021-01-01", _EMPTY_AP)
    ops = [
        Operation(
            id="op-1",
            source_id=NodeId(arrete_id="2021-01-01", article_id="2"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
            operation_type=OperationType.REPLACE,
            status_code=StatusCode.RESOLVED,
        ),
        Operation(
            id="op-2",
            source_id=NodeId(arrete_id="2021-01-01", article_id="3"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="3"),
            operation_type=OperationType.REMOVE,
            status_code=StatusCode.RESOLVED,
        ),
    ]
    assert has_unresolved_or_zero_ops(arrete, ops) is False


def test_returns_true_when_some_ops_have_errors() -> None:
    arrete = _make_arrete("2021-01-01", _EMPTY_AP)
    ops = [
        Operation(
            id="op-1",
            source_id=NodeId(arrete_id="2021-01-01", article_id="2"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="2"),
            operation_type=OperationType.REPLACE,
            status_code=StatusCode.RESOLVED,
        ),
        Operation(
            id="op-2",
            source_id=NodeId(arrete_id="2021-01-01", article_id="3"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="3"),
            operation_type=OperationType.ADD,
            status_code=StatusCode.ERROR_EXTRACTING_OPERAND,
        ),
    ]
    assert has_unresolved_or_zero_ops(arrete, ops) is True
