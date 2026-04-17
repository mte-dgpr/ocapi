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

from ocapi.exceptions import SubtargetNotFoundError
from ocapi.step_resolution.apply_ops import (
    _is_unambiguous_all_operation,
    _strip_duplicate_section_title,
    apply_add,
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
    mock_add.return_value = (StatusCode.RESOLVED, "new content after add")
    mock_remove.return_value = (StatusCode.RESOLVED, "")
    mock_replace.return_value = (StatusCode.RESOLVED, "new content after replace")

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
            {"version": 0, "title": "", "content": "original content", "operation_id": None}
        ],
        NodeId(arrete_id="1980-01-01", article_id="2"): [
            {"version": 0, "title": "", "content": "original content 2", "operation_id": None}
        ],
    }
    output_history, _skipped = apply_subgraph_operations(G, history)

    history_content_1 = output_history[NodeId(arrete_id="1980-01-01", article_id="1")][-1][
        "content"
    ]
    assert history_content_1 == mock_replace.return_value[1]
    history_content_2 = output_history[NodeId(arrete_id="1980-01-01", article_id="2")][-1][
        "content"
    ]
    assert history_content_2 == mock_add.return_value[1]


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_complex_subtarget_on_operation_still_applies_replace(mock_replace: mock.Mock) -> None:
    """COMPLEX_SUBTARGET marks LLM consolidation; it must not block application."""
    mock_replace.return_value = (StatusCode.RESOLVED, "consolidated")
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
        target: [{"version": 0, "title": "", "content": "content v0", "operation_id": None}],
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
                "title": "",
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
        "title": "",
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
        target: [{"version": 0, "title": "", "content": "content v0", "operation_id": None}]
    }
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    assert output_history[target][-1] == {
        "version": 1,
        "title": "",
        "content": "content v0",
        "operation_id": "op-subtarget-missing",
        "status_code": StatusCode.ERROR_FINDING_SUBTARGET,
    }


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_initialize_history_from_graph_node_content(mock_replace: mock.Mock) -> None:
    mock_replace.return_value = (StatusCode.RESOLVED, "updated content")
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
        "title": "",
        "content": initial_content,
        "operation_id": None,
    }
    assert output_history[target][-1]["content"] == "updated content"


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_multiple_operations_same_target_preserve_single_initial_version(
    mock_replace: mock.Mock,
) -> None:
    mock_replace.side_effect = [
        (StatusCode.RESOLVED, "updated once"),
        (StatusCode.RESOLVED, "updated twice"),
    ]
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
        "title": "",
        "content": initial_content,
        "operation_id": None,
    }
    assert output_history[target][1] == {
        "version": 1,
        "title": "",
        "content": "updated once",
        "operation_id": "op-1",
    }
    assert output_history[target][2] == {
        "version": 2,
        "title": "",
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
    mock_add.return_value = (StatusCode.RESOLVED, "new content after add")
    mock_remove.return_value = (StatusCode.RESOLVED, "")
    mock_replace.return_value = (StatusCode.RESOLVED, "new content after replace")

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
        target: [{"version": 0, "title": "", "content": "", "operation_id": None}],
    }
    output_history, skipped_ops = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    mock_replace.assert_not_called()
    last = output_history[target][-1]
    assert last["content"] == ""
    assert last["status_code"] == StatusCode.ERROR_EXTRACTING_TARGET
    assert last["operation_id"] == "op-missing-target"


# ---------------------------------------------------------------------------
# _is_unambiguous_all_operation
# ---------------------------------------------------------------------------


def _op(op_type: OperationType, sub_target: SubTarget | None = None) -> Operation:
    return Operation(
        id="x",
        source_id=NodeId(arrete_id="1981-01-01", article_id="2"),
        target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
        operation_type=op_type,
        operand="content",
        sub_target=sub_target,
    )


def test_is_unambiguous_all_replace_full_section() -> None:
    op = _op(OperationType.REPLACE, SubTarget(type=SubTargetType.FULL_SECTION))
    assert _is_unambiguous_all_operation(op) is True


def test_is_unambiguous_all_remove_full_section() -> None:
    op = _op(OperationType.REMOVE, SubTarget(type=SubTargetType.FULL_SECTION))
    assert _is_unambiguous_all_operation(op) is True


def test_is_unambiguous_all_replace_partial() -> None:
    op = _op(OperationType.REPLACE, SubTarget(type=SubTargetType.PHRASE, position=1))
    assert _is_unambiguous_all_operation(op) is False


def test_is_unambiguous_all_add_returns_false() -> None:
    op = _op(OperationType.ADD, SubTarget(type=SubTargetType.FULL_SECTION))
    assert _is_unambiguous_all_operation(op) is False


def test_is_unambiguous_all_replace_no_subtarget() -> None:
    op = _op(OperationType.REPLACE, sub_target=None)
    assert _is_unambiguous_all_operation(op) is False


def test_is_unambiguous_all_remove_no_subtarget() -> None:
    op = _op(OperationType.REMOVE, sub_target=None)
    assert _is_unambiguous_all_operation(op) is False


# ---------------------------------------------------------------------------
# propagated_error propagation
# ---------------------------------------------------------------------------


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_propagated_error_when_previous_version_has_error(mock_replace: mock.Mock) -> None:
    """A new operation on an article with a previous error gets PROPAGATED_ERROR."""
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1982-01-01", article_id="3")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source)
    add_node(G, target)
    add_edge(
        G,
        Operation(
            id="op-next",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="new content",
            sub_target=SubTarget(type=SubTargetType.PHRASE, position=1),
        ),
    )

    history: ArticleHistory = {
        target: [
            {"version": 0, "title": "", "content": "v0", "operation_id": None},
            {
                "version": 1,
                "title": "",
                "content": "v0",
                "operation_id": "op-prev",
                "status_code": StatusCode.ERROR_EXTRACTING_OPERAND,
            },
        ]
    }
    output_history, skipped = apply_subgraph_operations(G, history)

    assert skipped == []
    mock_replace.assert_not_called()
    last = output_history[target][-1]
    assert last["status_code"] == StatusCode.PROPAGATED_ERROR
    assert last["content"] == "v0"
    assert last["operation_id"] == "op-next"


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_propagated_error_chains_from_previous_propagated_error(mock_replace: mock.Mock) -> None:
    """PROPAGATED_ERROR itself triggers further propagation on subsequent operations."""
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1983-01-01", article_id="1")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source)
    add_node(G, target)
    add_edge(
        G,
        Operation(
            id="op-chain",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="content",
            sub_target=SubTarget(type=SubTargetType.TABLEAU),
        ),
    )

    history: ArticleHistory = {
        target: [
            {"version": 0, "title": "", "content": "v0", "operation_id": None},
            {
                "version": 1,
                "title": "",
                "content": "v0",
                "operation_id": "op-prev",
                "status_code": StatusCode.PROPAGATED_ERROR,
            },
        ]
    }
    output_history, skipped = apply_subgraph_operations(G, history)

    assert skipped == []
    mock_replace.assert_not_called()
    assert output_history[target][-1]["status_code"] == StatusCode.PROPAGATED_ERROR


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_replace_all_bypasses_propagation(mock_replace: mock.Mock) -> None:
    """REPLACE FULL_SECTION is applied even when the previous version had an error."""
    mock_replace.return_value = (StatusCode.RESOLVED, "replaced all content")
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1982-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source)
    add_node(G, target)
    add_edge(
        G,
        Operation(
            id="op-replace-all",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="brand new content",
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
        ),
    )

    history: ArticleHistory = {
        target: [
            {"version": 0, "title": "", "content": "v0", "operation_id": None},
            {
                "version": 1,
                "title": "",
                "content": "v0",
                "operation_id": "op-prev",
                "status_code": StatusCode.ERROR_EXTRACTING_OPERAND,
            },
        ]
    }
    output_history, skipped = apply_subgraph_operations(G, history)

    assert skipped == []
    mock_replace.assert_called_once()
    last = output_history[target][-1]
    assert last["content"] == "replaced all content"
    assert last.get("status_code") is None  # RESOLVED is not stored explicitly


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_replace_all_with_extraction_error_records_own_error_not_propagated(
    mock_replace: mock.Mock,
) -> None:
    """REPLACE FULL_SECTION with a missing operand records ERROR_EXTRACTING_OPERAND.

    The "all" bypass lets the operation skip propagation, but the operation
    itself is broken (no operand) so it should record its own error — not the
    previous PROPAGATED_ERROR.
    """
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1982-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source)
    add_node(G, target)
    add_edge(
        G,
        Operation(
            id="op-replace-all-broken",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand=None,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
            status_code=StatusCode.ERROR_EXTRACTING_OPERAND,
        ),
    )

    history: ArticleHistory = {
        target: [
            {"version": 0, "title": "", "content": "v0", "operation_id": None},
            {
                "version": 1,
                "title": "",
                "content": "v0",
                "operation_id": "op-prev",
                "status_code": StatusCode.ERROR_EXTRACTING_OPERAND,
            },
        ]
    }
    output_history, skipped = apply_subgraph_operations(G, history)

    assert skipped == []
    mock_replace.assert_not_called()
    last = output_history[target][-1]
    assert last["status_code"] == StatusCode.ERROR_EXTRACTING_OPERAND


@mock.patch("ocapi.step_resolution.apply_ops.apply_remove")
def test_remove_all_bypasses_propagation(mock_remove: mock.Mock) -> None:
    """REMOVE FULL_SECTION is applied even when the previous version had an error."""
    mock_remove.return_value = (StatusCode.RESOLVED, "")
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1982-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source)
    add_node(G, target)
    add_edge(
        G,
        Operation(
            id="op-remove-all",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REMOVE,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
        ),
    )

    history: ArticleHistory = {
        target: [
            {"version": 0, "title": "", "content": "v0", "operation_id": None},
            {
                "version": 1,
                "title": "",
                "content": "v0",
                "operation_id": "op-prev",
                "status_code": StatusCode.ERROR_EXTRACTING_OPERAND,
            },
        ]
    }
    output_history, skipped = apply_subgraph_operations(G, history)

    assert skipped == []
    mock_remove.assert_called_once()
    last = output_history[target][-1]
    assert last["content"] == ""
    assert last.get("status_code") is None  # RESOLVED


def test_apply_add_full_section_new_article_wraps_operand() -> None:
    op = Operation(
        id="add-new",
        source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
        target_id=NodeId(arrete_id="1980-01-01", article_id="NEW_ARTICLE:4.1"),
        operation_type=OperationType.ADD,
        operand="<p>Corps neuf</p>",
        sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="contenu entier"),
    )
    status, out = apply_add(op, BeautifulSoup("", "html.parser"))
    assert status == StatusCode.RESOLVED
    assert 'data-number="4.1"' in out
    assert "Corps neuf" in out
    assert 'data-spec="section"' in out


def test_apply_add_simple_inserts_after_table() -> None:
    html = """
    <section data-spec="section" data-number="1">
      <table><tr><td>a</td></tr></table>
    </section>
    """
    op = Operation(
        id="add-after-tab",
        source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
        target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
        operation_type=OperationType.ADD,
        operand="<p>Suite</p>",
        sub_target=SubTarget(type=SubTargetType.TABLEAU, position=None, description="le tableau"),
    )
    status, out = apply_add(op, BeautifulSoup(html, "html.parser"))
    assert status == StatusCode.RESOLVED
    assert out.index("<table") < out.index("Suite")


def test_new_article_full_section_history_is_single_version_with_op_id() -> None:
    G = nx.MultiDiGraph()
    src = NodeId(arrete_id="1981-01-01", article_id="1")
    tgt = NodeId(arrete_id="1980-01-01", article_id="NEW_ARTICLE:2.1")
    add_node(G, src, "<section>x</section>")
    add_node(G, tgt, "")
    add_edge(
        G,
        Operation(
            id="create-21",
            source_id=src,
            target_id=tgt,
            operation_type=OperationType.ADD,
            operand="<p>Nouvel article</p>",
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="contenu entier"),
        ),
    )
    history: ArticleHistory = {}
    out, skipped = apply_subgraph_operations(G, history)
    assert skipped == []
    versions = out[tgt]
    assert len(versions) == 1
    assert versions[0]["version"] == 0
    assert versions[0]["operation_id"] == "create-21"
    assert "Nouvel article" in str(versions[0]["content"])


# ---------------------------------------------------------------------------
# _strip_duplicate_section_title
# ---------------------------------------------------------------------------


def test_strip_duplicate_section_title_removes_matching_title() -> None:
    target_title = "<h2>Article 1.1. Dispositions générales</h2>"
    operand = (
        '<section data-spec="section" data-number="1.1">'
        "<h2>Article 1.1. Dispositions générales</h2>"
        "<p>new content</p></section>"
    )
    result = _strip_duplicate_section_title(operand, "1.1", target_title)
    assert "<h2>" not in result
    assert "<section" not in result
    assert "new content" in result


def test_strip_duplicate_section_title_ignores_different_title() -> None:
    target_title = "<h2>Article 1.1. Dispositions générales</h2>"
    operand = (
        '<section data-spec="section" data-number="1.1">'
        "<h2>Article 1.1. Autre titre</h2>"
        "<p>new</p></section>"
    )
    result = _strip_duplicate_section_title(operand, "1.1", target_title)
    assert "<h2>" in result
    assert "Autre titre" in result


def test_strip_duplicate_section_title_ignores_no_section() -> None:
    target_title = "<h2>Article 1.1. Titre</h2>"
    operand = "<p>just content</p>"
    result = _strip_duplicate_section_title(operand, "1.1", target_title)
    assert result == operand


def test_strip_duplicate_section_title_ignores_different_data_number() -> None:
    target_title = "<h2>Article 1.1. Titre</h2>"
    operand = (
        '<section data-spec="section" data-number="2.3">'
        "<h2>Article 1.1. Titre</h2><p>new</p></section>"
    )
    result = _strip_duplicate_section_title(operand, "1.1", target_title)
    assert "<h2>" in result


def test_strip_duplicate_section_title_normalizes_whitespace() -> None:
    target_title = "<h2>Article  4.2.  Émissions</h2>"
    operand = '<section data-number="4.2"><h2>Article 4.2. Émissions</h2><p>new</p></section>'
    result = _strip_duplicate_section_title(operand, "4.2", target_title)
    assert "<h2>" not in result
    assert "new" in result


def test_strip_duplicate_section_title_applied_in_replace() -> None:
    """Full integration: REPLACE + FULL_SECTION with duplicate title in operand.

    Titles are stored separately, so the resolved content must not contain any heading.
    """
    G = nx.MultiDiGraph()
    src = NodeId(arrete_id="2020-01-01", article_id="6")
    tgt = NodeId(arrete_id="2010-01-01", article_id="1.1.1.1")
    target_title = "<h2>Article 1.1.1.1. Conditions</h2>"
    target_content = (
        '<section data-spec="section" data-number="1.1.1.1">' "<p>old body</p></section>"
    )
    operand_html = (
        '<section data-spec="section" data-number="1.1.1.1">'
        "<h2>Article 1.1.1.1. Conditions</h2>"
        "<p>new body</p></section>"
    )
    add_node(G, src, node_content="<section>source</section>")
    add_node(G, tgt, node_content=target_content, node_title=target_title)
    add_edge(
        G,
        Operation(
            id="op-dup",
            source_id=src,
            target_id=tgt,
            operation_type=OperationType.REPLACE,
            operand=operand_html,
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION, description="ALL"),
        ),
    )
    history: ArticleHistory = {}
    out, skipped = apply_subgraph_operations(G, history)
    assert skipped == []
    content = out[tgt][-1]["content"]
    titles = BeautifulSoup(content, "html.parser").find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    assert len(titles) == 0, (
        f"Expected 0 titles in content (title stored separately), "
        f"got {len(titles)}: {[t.get_text() for t in titles]}"
    )
    assert "new body" in content
    assert out[tgt][-1].get("title") == target_title
