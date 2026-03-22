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
from unittest import mock

import networkx as nx
from bs4 import BeautifulSoup

from ocapi.exceptions import ComplexSubtargetError, SubtargetNotFoundError
from ocapi.step_resolution.apply_ops import (
    apply_all_ops,
    apply_subgraph_operations,
    build_next_subgraph,
)
from ocapi.step_resolution.build_op_graph import add_edge, add_node
from ocapi.types import (
    ArreteFile,
    ArticleHistory,
    FileType,
    NodeId,
    Operation,
    OperationType,
    StatusCode,
    SubTarget,
    SubTargetType,
)


def test_build_subgraph() -> None:
    """Verify that build_next_subgraph extracts only the operations from a given arrêté.

    Builds a graph with operations from three different arrêtés and verifies
    that only the sub-graph of the 1981 arrêté is returned (two edges, three nodes).
    """
    G = nx.MultiDiGraph()
    add_node(G, NodeId(arrete_id="1980-01-01", article_id="1"))
    add_node(G, NodeId(arrete_id="1981-01-01", article_id="2"))
    add_node(G, NodeId(arrete_id="1981-01-01", article_id="3"))
    add_node(G, NodeId(arrete_id="1982-01-01", article_id="1"))
    add_edge(
        G,
        Operation(
            id="op1",
            source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
            operand="very new content",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op2",
            source_id=NodeId(arrete_id="1981-01-01", article_id="3"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
            operation_type=OperationType.ADD,
            operand="additional content",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op3",
            source_id=NodeId(arrete_id="1982-01-01", article_id="1"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
            operand="very new content",
        ),
    )
    history: ArticleHistory = {}
    subG = build_next_subgraph(G, history, arrete_id="1981-01-01")

    assert set(subG.nodes) == {
        NodeId(arrete_id="1980-01-01", article_id="1"),
        NodeId(arrete_id="1981-01-01", article_id="2"),
        NodeId(arrete_id="1981-01-01", article_id="3"),
    }
    assert set(subG.edges) == {
        (
            NodeId(arrete_id="1981-01-01", article_id="2"),
            NodeId(arrete_id="1980-01-01", article_id="1"),
            0,
        ),
        (
            NodeId(arrete_id="1981-01-01", article_id="3"),
            NodeId(arrete_id="1980-01-01", article_id="1"),
            0,
        ),
    }


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
@mock.patch("ocapi.step_resolution.apply_ops.apply_remove")
@mock.patch("ocapi.step_resolution.apply_ops.apply_add")
def test_apply_subgraph_operations(
    mock_add: mock.Mock, mock_remove: mock.Mock, mock_replace: mock.Mock
) -> None:
    """Verify that apply_subgraph_operations dispatches each operation to the right function.

    Builds a sub-graph with a REPLACE and an ADD, mocks the application functions,
    and verifies that the history contains the contents returned by the mocks.
    """
    mock_add.return_value = "new content after add"
    mock_remove.return_value = ""
    mock_replace.return_value = "new content after replace"

    G = nx.MultiDiGraph()
    add_node(G, NodeId(arrete_id="1980-01-01", article_id="1"))
    add_node(G, NodeId(arrete_id="1980-01-01", article_id="2"))
    add_node(G, NodeId(arrete_id="1981-01-01", article_id="2"))
    add_node(G, NodeId(arrete_id="1981-01-01", article_id="3"))
    add_edge(
        G,
        Operation(
            id="op1",
            source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
            operand="very new content",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op2",
            source_id=NodeId(arrete_id="1981-01-01", article_id="3"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="2"),
            operation_type=OperationType.ADD,
            operand="additional content",
        ),
    )
    history: ArticleHistory = {
        NodeId(arrete_id="1980-01-01", article_id="1"): [
            {"version": 0, "content": "original content", "operation_id": None}
        ],
        NodeId(arrete_id="1980-01-01", article_id="2"): [
            {"version": 0, "content": "original content 2", "operation_id": None}
        ],
    }
    output_history, _skipped = apply_subgraph_operations(G, history)

    history_content_1 = output_history[NodeId(arrete_id="1980-01-01", article_id="1")][-1][
        "content"
    ]
    assert history_content_1 == mock_replace.return_value
    history_content_2 = output_history[NodeId(arrete_id="1980-01-01", article_id="2")][-1][
        "content"
    ]
    assert history_content_2 == mock_add.return_value


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_complex_subtarget_on_operation_still_applies_replace(mock_replace: mock.Mock) -> None:
    """COMPLEX_SUBTARGET marks LLM consolidation; it must not block application (#371)."""
    mock_replace.return_value = "consolidated"
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1981-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source, "<section>source html</section>")
    add_node(G, target, "<section>target html</section>")
    add_edge(
        G,
        Operation(
            id="op-complex",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="<p>x</p>",
            sub_target=SubTarget(type=SubTargetType.COMPLEX, description="ligne 7 du tableau"),
            status_code=StatusCode.COMPLEX_SUBTARGET,
        ),
    )
    history: ArticleHistory = {
        target: [{"version": 0, "content": "content v0", "operation_id": None}],
    }
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    mock_replace.assert_called_once()
    assert output_history[target][-1]["content"] == "consolidated"
    assert output_history[target][-1].get("status_code") is None


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_unresolved_operation_keeps_previous_content(mock_replace: mock.Mock) -> None:
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1981-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source)
    add_node(G, target)
    add_edge(
        G,
        Operation(
            id="op-unresolved",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand=None,
            status_code=StatusCode.ERROR_EXTRACTING_OPERAND,
        ),
    )

    history: ArticleHistory = {
        target: [
            {
                "version": 0,
                "content": "content v0",
                "operation_id": None,
                "status_code": StatusCode.RESOLVED,
            }
        ]
    }
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    mock_replace.assert_not_called()
    assert output_history[target][-1] == {
        "version": 1,
        "content": "content v0",
        "operation_id": "op-unresolved",
        "status_code": StatusCode.ERROR_EXTRACTING_OPERAND,
    }


@mock.patch(
    "ocapi.step_resolution.apply_ops.apply_replace",
    side_effect=SubtargetNotFoundError("subtarget not found"),
)
def test_subtarget_not_found_sets_error_finding_subtarget(mock_replace: mock.Mock) -> None:
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1981-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source)
    add_node(G, target)
    add_edge(
        G,
        Operation(
            id="op-subtarget-missing",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="new content",
        ),
    )

    history: ArticleHistory = {
        target: [{"version": 0, "content": "content v0", "operation_id": None}]
    }
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    assert output_history[target][-1] == {
        "version": 1,
        "content": "content v0",
        "operation_id": "op-subtarget-missing",
        "status_code": StatusCode.ERROR_FINDING_SUBTARGET,
    }


@mock.patch(
    "ocapi.step_resolution.apply_ops.apply_replace",
    side_effect=ComplexSubtargetError("complex subtarget"),
)
def test_complex_subtarget_sets_complex_subtarget_status(mock_replace: mock.Mock) -> None:
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1981-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source)
    add_node(G, target)
    add_edge(
        G,
        Operation(
            id="op-complex-subtarget",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="new content",
        ),
    )

    history: ArticleHistory = {
        target: [{"version": 0, "content": "content v0", "operation_id": None}]
    }
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    assert output_history[target][-1] == {
        "version": 1,
        "content": "content v0",
        "operation_id": "op-complex-subtarget",
        "status_code": StatusCode.COMPLEX_SUBTARGET,
    }


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_initialize_history_from_graph_node_content(mock_replace: mock.Mock) -> None:
    mock_replace.return_value = "updated content"
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1981-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    initial_content = '<section data-spec="section" data-number="1">Original content</section>'
    add_node(G, source)
    add_node(G, target, initial_content)
    add_edge(
        G,
        Operation(
            id="op-initial-content",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="new content",
        ),
    )

    history: ArticleHistory = {}
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    assert output_history[target][0] == {
        "version": 0,
        "content": initial_content,
        "operation_id": None,
    }
    assert output_history[target][-1]["content"] == "updated content"


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_multiple_operations_same_target_preserve_single_initial_version(
    mock_replace: mock.Mock,
) -> None:
    mock_replace.side_effect = ["updated once", "updated twice"]
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1981-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    initial_content = '<section data-spec="section" data-number="1">Original content</section>'

    add_node(G, source)
    add_node(G, target, initial_content)
    add_edge(
        G,
        Operation(
            id="op-1",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="new content 1",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op-2",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="new content 2",
        ),
    )

    history: ArticleHistory = {}
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    assert len(output_history[target]) == 3
    assert output_history[target][0] == {
        "version": 0,
        "content": initial_content,
        "operation_id": None,
    }
    assert output_history[target][1] == {
        "version": 1,
        "content": "updated once",
        "operation_id": "op-1",
    }
    assert output_history[target][2] == {
        "version": 2,
        "content": "updated twice",
        "operation_id": "op-2",
    }


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
@mock.patch("ocapi.step_resolution.apply_ops.apply_remove")
@mock.patch("ocapi.step_resolution.apply_ops.apply_add")
def test_apply_all_operations(
    mock_add: mock.Mock, mock_remove: mock.Mock, mock_replace: mock.Mock
) -> None:
    """Verify that apply_all_ops processes arrêtés chronologically and accumulates versions.

    Builds a complete graph with 4 operations across 3 arrêtés and verifies
    that the final history contains multiple versions for each target article.
    """
    mock_add.return_value = "new content after add"
    mock_remove.return_value = ""
    mock_replace.return_value = "new content after replace"

    G = nx.MultiDiGraph()
    add_node(G, NodeId(arrete_id="1980-01-01", article_id="1"))
    add_node(G, NodeId(arrete_id="1980-01-01", article_id="2"))
    add_node(G, NodeId(arrete_id="1981-01-01", article_id="2"))
    add_node(G, NodeId(arrete_id="1981-01-01", article_id="3"))
    add_node(G, NodeId(arrete_id="1982-01-01", article_id="1"))
    add_edge(
        G,
        Operation(
            id="op1",
            source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
            operand="very new content",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op2",
            source_id=NodeId(arrete_id="1981-01-01", article_id="3"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="2"),
            operation_type=OperationType.ADD,
            operand="additional content",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op3",
            source_id=NodeId(arrete_id="1982-01-01", article_id="1"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
            operation_type=OperationType.ADD,
            operand="new content",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op4",
            source_id=NodeId(arrete_id="1982-01-01", article_id="1"),
            target_id=NodeId(arrete_id="1980-01-01", article_id="2"),
            operation_type=OperationType.REMOVE,
        ),
    )
    arrete_list = [
        ArreteFile(
            id="1980-01-01",
            aiot="aiotA",
            filename="a.html",
            soup=BeautifulSoup("<section/>", "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="1981-01-01",
            aiot="aiotB",
            filename="b.html",
            soup=BeautifulSoup("<section/>", "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="1982-01-01",
            aiot="aiotC",
            filename="c.html",
            soup=BeautifulSoup("<section/>", "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]
    history, _skipped = apply_all_ops(G, arrete_list)

    assert NodeId(arrete_id="1980-01-01", article_id="1") in history
    assert NodeId(arrete_id="1980-01-01", article_id="2") in history
    assert len(history[NodeId(arrete_id="1980-01-01", article_id="1")]) > 1
    assert len(history[NodeId(arrete_id="1980-01-01", article_id="2")]) > 1


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_error_extracting_target_keeps_content_and_stores_status(
    mock_replace: mock.Mock,
) -> None:
    """ERROR_EXTRACTING_TARGET must not call apply_* and must store the status code."""
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1981-01-01", article_id="1")
    target = NodeId(arrete_id="1980-01-01", article_id="99")
    add_node(G, source)
    add_node(G, target, "")
    add_edge(
        G,
        Operation(
            id="op-missing-target",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="new",
            status_code=StatusCode.ERROR_EXTRACTING_TARGET,
        ),
    )
    history: ArticleHistory = {
        target: [{"version": 0, "content": "", "operation_id": None}],
    }
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    mock_replace.assert_not_called()
    last = output_history[target][-1]
    assert last["content"] == ""
    assert last["status_code"] == StatusCode.ERROR_EXTRACTING_TARGET
    assert last["operation_id"] == "op-missing-target"
