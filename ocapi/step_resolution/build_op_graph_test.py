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
from bs4 import BeautifulSoup

from ocapi.types import (
    ArreteFile,
    ErrorCode,
    FileType,
    NodeId,
    Operation,
    OperationType,
    SubTarget,
    SubTargetType,
)

from .build_op_graph import _is_full_removal_op, add_node, build_graph, update_node


def test_update_node_sets_content_and_title() -> None:
    import networkx as nx

    G = nx.MultiDiGraph()
    node = NodeId(arrete_id="2020-01-01", article_id="1")
    add_node(G, node, node_content="<p>old</p>", node_title="<h2>Title</h2>")

    update_node(G, node, node_content="<p>new</p>")
    assert G.nodes[node]["content"] == "<p>new</p>"
    assert G.nodes[node]["title"] == "<h2>Title</h2>"

    update_node(G, node, node_title="<h2>New Title</h2>")
    assert G.nodes[node]["content"] == "<p>new</p>"
    assert G.nodes[node]["title"] == "<h2>New Title</h2>"


def test_build_graph() -> None:
    """Verify that build_graph correctly builds the operations graph.

    Creates two arrêtés and two operations (REPLACE and REMOVE), builds the
    graph, and verifies the node count, edge count, and edge data.
    """
    html_1980 = """
    <section data-spec="section" data-number="2">Article 2 content</section>
    <section data-spec="section" data-number="3">Article 3 content</section>
    """
    html_1981 = """
    <section data-spec="section" data-number="1">Article 1 content</section>
    <section data-spec="section" data-number="2">Article 2 content</section>
    """

    arrete_files = [
        ArreteFile(
            id="1980-01-01",
            aiot="aiot1",
            filename="1980-01-01.html",
            soup=BeautifulSoup(html_1980, "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="1981-01-01",
            aiot="aiot2",
            filename="1981-01-01.html",
            soup=BeautifulSoup(html_1981, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]

    operations = [
        Operation(
            id="1",
            source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="2"),
            operation_type=OperationType.REPLACE,
            operand="article",
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
        ),
        Operation(
            id="2",
            source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="3"),
            operation_type=OperationType.REMOVE,
        ),
    ]
    G, updated_arrete_files, skipped_ops, _updated_ops = build_graph(operations, arrete_files)

    assert len(G.nodes) == 4
    assert len(G.edges) == 2
    assert len(skipped_ops) == 0

    node1 = NodeId(arrete_id="1980-01-01", article_id="2")
    node2 = NodeId(arrete_id="1980-01-01", article_id="3")
    node3 = NodeId(arrete_id="1981-01-01", article_id="1")
    node4 = NodeId(arrete_id="1981-01-01", article_id="2")

    assert G.has_edge(node3, node1) is True
    assert G.has_edge(node4, node2) is True
    assert "content" in G.nodes[node1]
    assert "content" in G.nodes[node2]
    assert "content" in G.nodes[node3]
    assert "content" in G.nodes[node4]

    target_node_1_soup = BeautifulSoup(G.nodes[node1]["content"], "html.parser")
    target_node_2_soup = BeautifulSoup(G.nodes[node2]["content"], "html.parser")
    assert target_node_1_soup.get_text(strip=True) == "Article 2 content"
    assert target_node_2_soup.get_text(strip=True) == "Article 3 content"

    source_node_3_soup = BeautifulSoup(G.nodes[node3]["content"], "html.parser")
    source_node_4_soup = BeautifulSoup(G.nodes[node4]["content"], "html.parser")
    assert source_node_3_soup.get_text(strip=True) == "Article 1 content"
    assert source_node_4_soup.get_text(strip=True) == "Article 2 content"

    assert G.get_edge_data(node3, node1, 0) == {
        "id": "1",
        "operation_type": "REPLACE",
        "operand": "article",
        "sub_target": {"type": "FULL_SECTION"},
    }
    assert G.get_edge_data(node4, node2, 0) == {"id": "2", "operation_type": "REMOVE"}


def test_build_graph_replace_all_marks_arrete_abrogated() -> None:
    """REPLACE with target_article ALL (arrêté refonte) must mark the target arrêté as abrogated.

    The operation is not added to the graph (no article-level resolution needed).
    """
    html_2020 = """
    <section data-spec="section" data-number="1">Article 1</section>
    <section data-spec="section" data-number="2">Article 2</section>
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

    replace_all_op = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
        operation_type=OperationType.REPLACE,
        operand="<section>refonte body</section>",
    )

    G, updated_arrete_files, skipped_ops, updated_ops = build_graph([replace_all_op], arrete_files)

    assert len(G.nodes) == 0
    assert len(G.edges) == 0
    assert len(skipped_ops) == 0

    arrete_2020 = next(af for af in updated_arrete_files if af.id == "2020-04-20")
    assert arrete_2020.status is False
    arrete_2021 = next(af for af in updated_arrete_files if af.id == "2021-09-24")
    assert arrete_2021.status is True

    assert not updated_ops[0].error_codes


def test_is_full_removal_op_replace_all() -> None:
    """_is_full_removal_op returns True for REPLACE with target ALL (refonte)."""
    op_replace_all = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
        operation_type=OperationType.REPLACE,
        operand="<section>refonte body</section>",
    )
    assert _is_full_removal_op(op_replace_all) is True


def test_is_full_removal_op_remove_all() -> None:
    """_is_full_removal_op returns True for REMOVE with target ALL."""
    op_remove_all = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
        operation_type=OperationType.REMOVE,
    )
    assert _is_full_removal_op(op_remove_all) is True


def test_is_full_removal_op_replace_single_article() -> None:
    """_is_full_removal_op returns False for REPLACE with single article target."""
    op_replace = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="1.2.1"),
        operation_type=OperationType.REPLACE,
    )
    assert _is_full_removal_op(op_replace) is False


def test_is_full_removal_op_remove_all_with_complex_subtarget() -> None:
    """REMOVE ALL with a narrower sub_target (e.g. annexe 1) is ill-defined, not an abrogation."""
    op = Operation(
        id="13",
        source_id=NodeId(arrete_id="2025-02-10", article_id="5"),
        target_id=NodeId(arrete_id="2006-12-14", article_id="ALL"),
        operation_type=OperationType.REMOVE,
        sub_target=SubTarget(type=SubTargetType.COMPLEX, description="annexe 1"),
        error_codes=frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND}),
    )
    assert _is_full_removal_op(op) is False


def test_is_full_removal_op_remove_all_with_error_status() -> None:
    """REMOVE ALL with a non-RESOLVED error_codes is not a valid abrogation."""
    op = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
        operation_type=OperationType.REMOVE,
        error_codes=frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND}),
    )
    assert _is_full_removal_op(op) is False


def test_is_full_removal_op_remove_all_full_section_subtarget() -> None:
    """REMOVE ALL with FULL_SECTION sub_target is a valid abrogation."""
    op = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
        operation_type=OperationType.REMOVE,
        sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
    )
    assert _is_full_removal_op(op) is True


def test_build_graph_ill_defined_remove_all_does_not_abrogate() -> None:
    """An ill-defined REMOVE ALL (narrow sub_target + error) must not abrogate the arrêté."""
    html_2006 = """
    <section data-spec="section" data-number="1">Article 1</section>
    """
    arrete_files = [
        ArreteFile(
            id="2006-12-14",
            aiot="aiot1",
            filename="2006-12-14.html",
            soup=BeautifulSoup(html_2006, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]

    ill_defined_op = Operation(
        id="13",
        source_id=NodeId(arrete_id="2025-02-10", article_id="5"),
        target_id=NodeId(arrete_id="2006-12-14", article_id="ALL"),
        operation_type=OperationType.REMOVE,
        sub_target=SubTarget(type=SubTargetType.COMPLEX, description="annexe 1"),
        error_codes=frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND}),
    )

    _, updated_arrete_files, _, _ = build_graph([ill_defined_op], arrete_files)

    arrete_2006 = updated_arrete_files[0]
    assert arrete_2006.status is True


def test_build_graph_full_removal_on_principal_is_not_resolved() -> None:
    """Full removal targeting the principal arrêté is blocked and marked as an error."""
    html_2020 = """
    <section data-spec="section" data-number="1">Article 1</section>
    """
    principal = ArreteFile(
        id="2020-04-20",
        aiot="aiot1",
        filename="2020-04-20.html",
        soup=BeautifulSoup(html_2020, "html.parser"),
        file_type=FileType.AUTRE,
        principal=True,
    )
    later = ArreteFile(
        id="2021-01-01",
        aiot="aiot1",
        filename="2021-01-01.html",
        soup=BeautifulSoup(
            '<section data-spec="section" data-number="1">x</section>', "html.parser"
        ),
        file_type=FileType.AUTRE,
    )

    ops = [
        Operation(
            id="1",
            source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
            operation_type=OperationType.REMOVE,
        )
    ]

    G, updated_arrete_files, _, updated_ops = build_graph(ops, [principal, later])

    assert len(G.nodes) == 0
    assert len(G.edges) == 0
    assert next(af for af in updated_arrete_files if af.id == "2020-04-20").status is True
    assert ErrorCode.ERROR_EXTRACTING_TARGET in updated_ops[0].error_codes


def test_build_graph_full_removal_with_narrower_ops_marks_less_important() -> None:
    """Full removal is dropped when narrower ops from the same source already
    touch parts of the same target arrêté."""
    html_2010 = """
    <section data-spec="section" data-number="1">Article 1</section>
    <section data-spec="section" data-number="2">Article 2</section>
    """
    html_2025 = """
    <section data-spec="section" data-number="1">Source 1</section>
    <section data-spec="section" data-number="30">Source 30</section>
    """
    arrete_files = [
        ArreteFile(
            id="2010-01-01",
            aiot="aiot1",
            filename="2010-01-01.html",
            soup=BeautifulSoup(html_2010, "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="2025-01-01",
            aiot="aiot1",
            filename="2025-01-01.html",
            soup=BeautifulSoup(html_2025, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]
    full_removal = Operation(
        id="op-remove-all",
        source_id=NodeId(arrete_id="2025-01-01", article_id="30"),
        target_id=NodeId(arrete_id="2010-01-01", article_id="ALL"),
        operation_type=OperationType.REMOVE,
    )
    narrower = Operation(
        id="op-replace-1",
        source_id=NodeId(arrete_id="2025-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2010-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
        operand="new",
        sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
    )

    G, updated_arrete_files, _, updated_ops = build_graph([full_removal, narrower], arrete_files)

    assert next(af for af in updated_arrete_files if af.id == "2010-01-01").status is True
    full_removal_updated = next(o for o in updated_ops if o.id == "op-remove-all")
    assert ErrorCode.LESS_IMPORTANT in full_removal_updated.error_codes
    # The full removal must not be added to the graph.
    assert not G.has_edge(
        NodeId(arrete_id="2025-01-01", article_id="30"),
        NodeId(arrete_id="2010-01-01", article_id="ALL"),
    )
    # The narrower operation is still applied normally.
    narrower_updated = next(o for o in updated_ops if o.id == "op-replace-1")
    assert not narrower_updated.error_codes


def test_build_graph_full_removal_ignores_other_full_removals_for_pair() -> None:
    """Two full removals from the same source on the same target don't make each other
    LESS_IMPORTANT — the new check only triggers on truly narrower ops."""
    html_2010 = """
    <section data-spec="section" data-number="1">Article 1</section>
    """
    arrete_files = [
        ArreteFile(
            id="2010-01-01",
            aiot="aiot1",
            filename="2010-01-01.html",
            soup=BeautifulSoup(html_2010, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]
    op_a = Operation(
        id="a",
        source_id=NodeId(arrete_id="2025-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2010-01-01", article_id="ALL"),
        operation_type=OperationType.REMOVE,
    )
    op_b = Operation(
        id="b",
        source_id=NodeId(arrete_id="2025-01-01", article_id="2"),
        target_id=NodeId(arrete_id="2010-01-01", article_id="ALL"),
        operation_type=OperationType.REMOVE,
    )

    _, updated_arrete_files, _, updated_ops = build_graph([op_a, op_b], arrete_files)

    assert updated_arrete_files[0].status is False
    for op in updated_ops:
        assert ErrorCode.LESS_IMPORTANT not in op.error_codes


def test_build_graph_full_removal_with_narrower_ops_from_other_source_still_abrogates() -> None:
    """The narrower ops must come from the same source arrêté to invalidate the abrogation."""
    html_2010 = """
    <section data-spec="section" data-number="1">Article 1</section>
    """
    arrete_files = [
        ArreteFile(
            id="2010-01-01",
            aiot="aiot1",
            filename="2010-01-01.html",
            soup=BeautifulSoup(html_2010, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]
    full_removal = Operation(
        id="op-remove-all",
        source_id=NodeId(arrete_id="2025-01-01", article_id="30"),
        target_id=NodeId(arrete_id="2010-01-01", article_id="ALL"),
        operation_type=OperationType.REMOVE,
    )
    other_source = Operation(
        id="op-other",
        source_id=NodeId(arrete_id="2024-06-01", article_id="1"),
        target_id=NodeId(arrete_id="2010-01-01", article_id="1"),
        operation_type=OperationType.REPLACE,
        operand="new",
        sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
    )

    _, updated_arrete_files, _, updated_ops = build_graph(
        [full_removal, other_source], arrete_files
    )

    assert updated_arrete_files[0].status is False
    full_removal_updated = next(o for o in updated_ops if o.id == "op-remove-all")
    assert not full_removal_updated.error_codes


def test_build_graph_remove_all_marks_arrete_abrogated() -> None:
    """REMOVE with target_article ALL must mark the target arrêté as abrogated."""
    html_2020 = """
    <section data-spec="section" data-number="1">Article 1</section>
    """
    arrete_files = [
        ArreteFile(
            id="2020-04-20",
            aiot="aiot1",
            filename="2020-04-20.html",
            soup=BeautifulSoup(html_2020, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]

    remove_all_op = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-01-01", article_id="1"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
        operation_type=OperationType.REMOVE,
    )

    G, updated_arrete_files, _, updated_ops = build_graph([remove_all_op], arrete_files)

    assert len(G.nodes) == 0
    assert len(G.edges) == 0
    arrete_2020 = updated_arrete_files[0]
    assert arrete_2020.status is False
    assert not updated_ops[0].error_codes


def test_build_graph_keeps_target_content_with_multiple_ops_same_target() -> None:
    html_1980 = """
    <section data-spec="section" data-number="2">Article 2 content</section>
    """
    html_1981 = """
    <section data-spec="section" data-number="1">Article 1 content</section>
    <section data-spec="section" data-number="2">Article 2 content</section>
    """

    arrete_files = [
        ArreteFile(
            id="1980-01-01",
            aiot="aiot1",
            filename="1980-01-01.html",
            soup=BeautifulSoup(html_1980, "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="1981-01-01",
            aiot="aiot2",
            filename="1981-01-01.html",
            soup=BeautifulSoup(html_1981, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]

    target = NodeId(arrete_id="1980-01-01", article_id="2")
    operations = [
        Operation(
            id="1",
            source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="article",
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
        ),
        Operation(
            id="2",
            source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
            target_id=target,
            operation_type=OperationType.REMOVE,
        ),
    ]

    G, _updated_arrete_files, skipped_ops, _ = build_graph(operations, arrete_files)

    assert len(skipped_ops) == 0
    assert G.in_degree(target) == 2
    assert "content" in G.nodes[target]
    target_soup = BeautifulSoup(G.nodes[target]["content"], "html.parser")
    assert target_soup.get_text(strip=True) == "Article 2 content"


def test_build_graph_missing_target_section_creates_empty_node_with_error() -> None:
    """When the target section is not found in the HTML, the node is created with empty
    content and the operation carries ERROR_EXTRACTING_TARGET."""
    html_1980 = """
    <section data-spec="section" data-number="1">Article 1</section>
    """
    html_1981 = """
    <section data-spec="section" data-number="1">Article 1 source</section>
    """
    arrete_files = [
        ArreteFile(
            id="1980-01-01",
            aiot="aiot1",
            filename="1980-01-01.html",
            soup=BeautifulSoup(html_1980, "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="1981-01-01",
            aiot="aiot1",
            filename="1981-01-01.html",
            soup=BeautifulSoup(html_1981, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]
    operations = [
        Operation(
            id="op-missing-target",
            source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="99"),
            operation_type=OperationType.REPLACE,
            operand="new",
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
        ),
    ]
    G, _, skipped_ops, _ = build_graph(operations, arrete_files)

    assert len(skipped_ops) == 0
    target = NodeId(arrete_id="1980-01-01", article_id="99")
    assert G.has_node(target)
    assert G.nodes[target].get("content") == ""
    edge_data = G.get_edge_data(NodeId(arrete_id="1981-01-01", article_id="1"), target, 0)
    assert edge_data is not None
    assert edge_data["error_codes"] == [ErrorCode.ERROR_EXTRACTING_TARGET.value]


def test_build_graph_missing_source_section_creates_empty_node_with_error() -> None:
    """When the source section is not found, the node is created with empty content
    and the operation carries ERROR_EXTRACTING_SOURCE."""
    html_1980 = """
    <section data-spec="section" data-number="2">Article 2 content</section>
    """
    html_1981 = """
    <section data-spec="section" data-number="1">Article 1 source</section>
    """
    arrete_files = [
        ArreteFile(
            id="1980-01-01",
            aiot="aiot1",
            filename="1980-01-01.html",
            soup=BeautifulSoup(html_1980, "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="1981-01-01",
            aiot="aiot1",
            filename="1981-01-01.html",
            soup=BeautifulSoup(html_1981, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]
    source = NodeId(arrete_id="1981-01-01", article_id="42")
    target = NodeId(arrete_id="1980-01-01", article_id="2")
    operations = [
        Operation(
            id="op-missing-source",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="new",
            sub_target=SubTarget(type=SubTargetType.COMPLEX, description="ligne 3"),
        ),
    ]
    G, _, skipped_ops, _ = build_graph(operations, arrete_files)

    assert len(skipped_ops) == 0
    assert G.has_node(source)
    assert G.nodes[source].get("content") == ""
    edge_data = G.get_edge_data(source, target, 0)
    assert edge_data is not None
    assert edge_data["error_codes"] == [ErrorCode.ERROR_EXTRACTING_SOURCE.value]


def test_build_graph_preserves_not_an_operation_status_when_target_missing() -> None:
    """A NOT_AN_OPERATION error code set at detection must survive the target lookup
    failure caused by ``article_id=ALL``."""
    html_1980 = """
    <section data-spec="section" data-number="1">Article 1</section>
    """
    html_1981 = """
    <section data-spec="section" data-number="1">cet arrêté complète l'arrêté 1980-01-01</section>
    """
    arrete_files = [
        ArreteFile(
            id="1980-01-01",
            aiot="aiot1",
            filename="1980-01-01.html",
            soup=BeautifulSoup(html_1980, "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="1981-01-01",
            aiot="aiot1",
            filename="1981-01-01.html",
            soup=BeautifulSoup(html_1981, "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]
    operations = [
        Operation(
            id="op-complement",
            source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="ALL"),
            operation_type=OperationType.ADD,
            error_codes=frozenset({ErrorCode.NOT_AN_OPERATION}),
        ),
    ]
    G, _, skipped_ops, _ = build_graph(operations, arrete_files)

    assert len(skipped_ops) == 0
    target = NodeId(arrete_id="1980-01-01", article_id="ALL")
    assert G.has_node(target)
    edge_data = G.get_edge_data(NodeId(arrete_id="1981-01-01", article_id="1"), target, 0)
    assert edge_data is not None
    assert ErrorCode.NOT_AN_OPERATION.value in edge_data["error_codes"]
