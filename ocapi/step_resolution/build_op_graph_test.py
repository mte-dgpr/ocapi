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
from bs4 import BeautifulSoup

from ocapi.types import (
    ArreteFile,
    FileType,
    NodeId,
    Operation,
    OperationType,
    SubTarget,
    SubTargetType,
)

from .build_op_graph import _is_abrogation_arrete, build_graph


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
    G, updated_arrete_files, skipped_ops = build_graph(operations, arrete_files)

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
    assert "content" not in G.nodes[node3]
    assert "content" not in G.nodes[node4]

    target_node_1_soup = BeautifulSoup(G.nodes[node1]["content"], "html.parser")
    target_node_2_soup = BeautifulSoup(G.nodes[node2]["content"], "html.parser")
    assert target_node_1_soup.get_text(strip=True) == "Article 2 content"
    assert target_node_2_soup.get_text(strip=True) == "Article 3 content"

    assert G.get_edge_data(node3, node1, 0) == {
        "id": "1",
        "operation_type": "REPLACE",
        "operand": "article",
        "sub_target": {"type": "FULL_SECTION"},
    }
    assert G.get_edge_data(node4, node2, 0) == {"id": "2", "operation_type": "REMOVE"}


def test_build_graph_replace_all_marks_arrete_abrogated() -> None:
    """REPLACE with target ALL (arrêté refonte) must mark the target arrêté as abrogated."""
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

    operations = [
        Operation(
            id="1",
            source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
            target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
            operation_type=OperationType.REPLACE,
        ),
    ]

    G, updated_arrete_files, skipped_ops = build_graph(operations, arrete_files)

    assert len(skipped_ops) == 0
    arrete_2020 = next(af for af in updated_arrete_files if af.id == "2020-04-20")
    assert arrete_2020.status is False
    arrete_2021 = next(af for af in updated_arrete_files if af.id == "2021-09-24")
    assert arrete_2021.status is True


def test_is_abrogation_arrete_replace_all() -> None:
    """_is_abrogation_arrete returns True for REPLACE with target ALL (refonte)."""
    op_replace_all = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
        operation_type=OperationType.REPLACE,
    )
    assert _is_abrogation_arrete(op_replace_all) is True


def test_is_abrogation_arrete_remove_all() -> None:
    """_is_abrogation_arrete returns True for REMOVE with target ALL."""
    op_remove_all = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="ALL"),
        operation_type=OperationType.REMOVE,
    )
    assert _is_abrogation_arrete(op_remove_all) is True


def test_is_abrogation_arrete_replace_single_article() -> None:
    """_is_abrogation_arrete returns False for REPLACE with single article target."""
    op_replace = Operation(
        id="1",
        source_id=NodeId(arrete_id="2021-09-24", article_id="1.1.2"),
        target_id=NodeId(arrete_id="2020-04-20", article_id="1.2.1"),
        operation_type=OperationType.REPLACE,
    )
    assert _is_abrogation_arrete(op_replace) is False


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

    G, _updated_arrete_files, skipped_ops = build_graph(operations, arrete_files)

    assert len(skipped_ops) == 0
    assert G.in_degree(target) == 2
    assert "content" in G.nodes[target]
    target_soup = BeautifulSoup(G.nodes[target]["content"], "html.parser")
    assert target_soup.get_text(strip=True) == "Article 2 content"
