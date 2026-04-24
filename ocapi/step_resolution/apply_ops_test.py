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
import pytest
from bs4 import BeautifulSoup

from ocapi.exceptions import OperationError, SubtargetNotFoundError
from ocapi.step_resolution.apply_ops import (
    _is_unambiguous_all_operation,
    _strip_duplicate_section_title,
    apply_add,
    apply_all_ops,
    apply_remove,
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
from ocapi.utils.testing import make_testing_op


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
    output_history, _skipped, _resolved = apply_subgraph_operations(G, history)

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
    output_history, skipped_ops, _resolved = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    mock_replace.assert_called_once()
    assert output_history[target][-1]["content"] == "consolidated"
    assert output_history[target][-1]["status_code"] == StatusCode.RESOLVED


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
    output_history, skipped_ops, _resolved = apply_subgraph_operations(G, history)

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
    output_history, skipped_ops, _resolved = apply_subgraph_operations(G, history)

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
    output_history, skipped_ops, _resolved = apply_subgraph_operations(G, history)

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
    output_history, skipped_ops, _resolved = apply_subgraph_operations(G, history)

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
        "status_code": StatusCode.RESOLVED,
    }
    assert output_history[target][2] == {
        "version": 2,
        "title": "",
        "content": "updated twice",
        "operation_id": "op-2",
        "status_code": StatusCode.RESOLVED,
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
    history, _skipped, _resolved = apply_all_ops(G, arrete_list)

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
    output_history, skipped_ops, _resolved = apply_subgraph_operations(G, history)

    assert skipped_ops == []
    mock_replace.assert_not_called()
    last = output_history[target][-1]
    assert last["content"] == ""
    assert last["status_code"] == StatusCode.ERROR_EXTRACTING_TARGET
    assert last["operation_id"] == "op-missing-target"


# ---------------------------------------------------------------------------
# _is_unambiguous_all_operation
# ---------------------------------------------------------------------------


def test_is_unambiguous_all_replace_full_section() -> None:
    op = make_testing_op(OperationType.REPLACE, SubTarget(type=SubTargetType.FULL_SECTION))
    assert _is_unambiguous_all_operation(op) is True


def test_is_unambiguous_all_remove_full_section() -> None:
    op = make_testing_op(OperationType.REMOVE, SubTarget(type=SubTargetType.FULL_SECTION))
    assert _is_unambiguous_all_operation(op) is True


def test_is_unambiguous_all_replace_partial() -> None:
    op = make_testing_op(OperationType.REPLACE, SubTarget(type=SubTargetType.PHRASE, position=1))
    assert _is_unambiguous_all_operation(op) is False


def test_is_unambiguous_all_add_returns_false() -> None:
    op = make_testing_op(OperationType.ADD, SubTarget(type=SubTargetType.FULL_SECTION))
    assert _is_unambiguous_all_operation(op) is False


def test_is_unambiguous_all_replace_no_subtarget() -> None:
    op = make_testing_op(OperationType.REPLACE, sub_target=None)
    assert _is_unambiguous_all_operation(op) is False


def test_is_unambiguous_all_remove_no_subtarget() -> None:
    op = make_testing_op(OperationType.REMOVE, sub_target=None)
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
    output_history, skipped, _resolved = apply_subgraph_operations(G, history)

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
    output_history, skipped, _resolved = apply_subgraph_operations(G, history)

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
    output_history, skipped, _resolved = apply_subgraph_operations(G, history)

    assert skipped == []
    mock_replace.assert_called_once()
    last = output_history[target][-1]
    assert last["content"] == "replaced all content"
    assert last["status_code"] == StatusCode.RESOLVED


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
    output_history, skipped, _resolved = apply_subgraph_operations(G, history)

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
    output_history, skipped, _resolved = apply_subgraph_operations(G, history)

    assert skipped == []
    mock_remove.assert_called_once()
    last = output_history[target][-1]
    assert last["content"] == ""
    assert last["status_code"] == StatusCode.RESOLVED


def test_apply_add_full_section_new_article_returns_inner_content() -> None:
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
    assert "Corps neuf" in out
    assert "<section" not in out


def test_apply_add_new_article_unwraps_section_operand() -> None:
    op = Operation(
        id="add-wrapped",
        source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
        target_id=NodeId(arrete_id="1980-01-01", article_id="NEW_ARTICLE:5.1"),
        operation_type=OperationType.ADD,
        operand='<section data-spec="section" data-number="5.1"><p>Wrapped</p></section>',
        sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
    )
    status, out = apply_add(op, BeautifulSoup("", "html.parser"))
    assert status == StatusCode.RESOLVED
    assert "Wrapped" in out
    assert "<section" not in out


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


def test_apply_remove_without_subtarget_raises() -> None:
    op = Operation(
        id="rm-no-sub",
        source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
        target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
        operation_type=OperationType.REMOVE,
    )
    with pytest.raises(OperationError):
        apply_remove(op, BeautifulSoup("", "html.parser"))


def test_apply_remove_simple_drops_table() -> None:
    html = """
    <section data-spec="section" data-number="1">
      <p>Before</p>
      <table><tr><td>a</td></tr></table>
      <p>After</p>
    </section>
    """
    op = Operation(
        id="rm-table",
        source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
        target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
        operation_type=OperationType.REMOVE,
        sub_target=SubTarget(type=SubTargetType.TABLEAU, position=None, description="le tableau"),
    )
    status, out = apply_remove(op, BeautifulSoup(html, "html.parser"))
    assert status == StatusCode.RESOLVED
    assert "<table" not in out
    assert "Before" in out
    assert "After" in out


@mock.patch("ocapi.step_resolution.apply_ops.call_llm_api")
def test_apply_remove_complex_falls_back_to_llm(mock_llm: mock.Mock) -> None:
    mock_llm.return_value = "<section>cleaned</section>"
    html = "<section data-spec='section' data-number='1'><p>some content</p></section>"
    op = Operation(
        id="rm-complex",
        source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
        target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
        operation_type=OperationType.REMOVE,
        sub_target=SubTarget(type=SubTargetType.COMPLEX, description="le dernier alinéa"),
    )
    status, out = apply_remove(op, BeautifulSoup(html, "html.parser"))
    assert status == StatusCode.RESOLVED
    mock_llm.assert_called_once()
    assert "cleaned" in out


def test_apply_remove_complex_disabled_llm_returns_unchanged() -> None:
    html = "<section data-spec='section' data-number='1'><p>keep</p></section>"
    op = Operation(
        id="rm-disabled",
        source_id=NodeId(arrete_id="1981-01-01", article_id="1"),
        target_id=NodeId(arrete_id="1980-01-01", article_id="1"),
        operation_type=OperationType.REMOVE,
        sub_target=SubTarget(type=SubTargetType.COMPLEX, description="un truc vague"),
    )
    status, out = apply_remove(op, BeautifulSoup(html, "html.parser"), enable_llm=False)
    assert status == StatusCode.DISABLED_LLM_CALL
    assert "keep" in out


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
    out, skipped, _resolved = apply_subgraph_operations(G, history)
    assert skipped == []
    versions = out[tgt]
    assert len(versions) == 1
    assert versions[0]["version"] == 0
    assert versions[0]["operation_id"] == "create-21"
    assert "Nouvel article" in str(versions[0]["content"])


# ---------------------------------------------------------------------------
# enable_llm=False → DISABLED_LLM_CALL
# ---------------------------------------------------------------------------


def test_disabled_llm_returns_unchanged_content_and_status() -> None:
    """Complex sub-targets return DISABLED_LLM_CALL when enable_llm=False."""
    G = nx.MultiDiGraph()
    source = NodeId(arrete_id="1981-01-01", article_id="2")
    target = NodeId(arrete_id="1980-01-01", article_id="1")
    add_node(G, source, "<section>source</section>")
    add_node(G, target, "<section>target</section>")
    add_edge(
        G,
        Operation(
            id="op-complex-disabled",
            source_id=source,
            target_id=target,
            operation_type=OperationType.REPLACE,
            operand="<p>new</p>",
            sub_target=SubTarget(type=SubTargetType.COMPLEX, description="ligne 3"),
            status_code=StatusCode.COMPLEX_SUBTARGET,
        ),
    )
    history: ArticleHistory = {
        target: [{"version": 0, "title": "", "content": "content v0", "operation_id": None}],
    }
    output_history, skipped, _resolved = apply_subgraph_operations(G, history, enable_llm=False)

    assert skipped == []
    last = output_history[target][-1]
    assert last["content"] == "content v0"
    assert last["status_code"] == StatusCode.DISABLED_LLM_CALL


# ---------------------------------------------------------------------------
# _strip_duplicate_section_title
# ---------------------------------------------------------------------------


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
def test_chain_branch_size_2_propagates_updated_operand(mock_replace: mock.Mock) -> None:
    """Chain C → B → A: when C replaces B, B → A is re-applied with updated operand.

    Three arrêtés form a chain:
      A (2005) defines article 1 with original content.
      B (2012) article 3 replaces A article 1.
      C (2025) article 2 replaces B article 3.

    After processing all three, A article 1 should have 3 versions:
      v0 = original, v1 = B's operand, v2 = C's operand (propagated through B).
    """
    mock_replace.side_effect = lambda op, soup, **kw: (StatusCode.RESOLVED, op.operand)

    G = nx.MultiDiGraph()
    node_a = NodeId(arrete_id="2005-11-08", article_id="1")
    node_b = NodeId(arrete_id="2012-09-03", article_id="3")
    node_c = NodeId(arrete_id="2025-02-24", article_id="2")

    add_node(G, node_a, "<section>original A content</section>")
    add_node(G, node_b, "<section>original B content</section>")
    add_node(G, node_c, "<section>original C content</section>")

    add_edge(
        G,
        Operation(
            id="op-b-to-a",
            source_id=node_b,
            target_id=node_a,
            operation_type=OperationType.REPLACE,
            operand="content from B",
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
        ),
    )
    add_edge(
        G,
        Operation(
            id="op-c-to-b",
            source_id=node_c,
            target_id=node_b,
            operation_type=OperationType.REPLACE,
            operand="content from C",
            sub_target=SubTarget(type=SubTargetType.FULL_SECTION),
        ),
    )

    arrete_list = [
        ArreteFile(
            id="2005-11-08",
            aiot="aiot1",
            filename="a.html",
            soup=BeautifulSoup("<section/>", "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="2012-09-03",
            aiot="aiot1",
            filename="b.html",
            soup=BeautifulSoup("<section/>", "html.parser"),
            file_type=FileType.AUTRE,
        ),
        ArreteFile(
            id="2025-02-24",
            aiot="aiot1",
            filename="c.html",
            soup=BeautifulSoup("<section/>", "html.parser"),
            file_type=FileType.AUTRE,
        ),
    ]
    history, skipped, _resolved = apply_all_ops(G, arrete_list)

    assert skipped == []

    versions_a = history[node_a]
    assert len(versions_a) == 3
    assert versions_a[0]["content"] == "<section>original A content</section>"
    assert versions_a[1]["content"] == "content from B"
    assert versions_a[2]["content"] == "content from C"

    versions_b = history[node_b]
    assert len(versions_b) == 2
    assert versions_b[0]["content"] == "<section>original B content</section>"
    assert versions_b[1]["content"] == "content from C"


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
    out, skipped, _resolved = apply_subgraph_operations(G, history)
    assert skipped == []
    content = out[tgt][-1]["content"]
    titles = BeautifulSoup(content, "html.parser").find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    assert len(titles) == 0, (
        f"Expected 0 titles in content (title stored separately), "
        f"got {len(titles)}: {[t.get_text() for t in titles]}"
    )
    assert "new body" in content
    assert out[tgt][-1].get("title") == target_title


@mock.patch("ocapi.step_resolution.apply_ops.apply_replace")
@mock.patch("ocapi.step_resolution.apply_ops.apply_add")
def test_apply_subgraph_operations_resolved_status_dict(
    mock_add: mock.Mock, mock_replace: mock.Mock
) -> None:
    """Each processed operation must appear in the resolved_status mapping."""
    mock_replace.return_value = (StatusCode.RESOLVED, "ok replace")
    mock_add.return_value = (StatusCode.RESOLVED, "ok add")

    G = nx.MultiDiGraph()
    src_ok = NodeId(arrete_id="1981-01-01", article_id="2")
    src_err = NodeId(arrete_id="1981-01-01", article_id="3")
    tgt_replace = NodeId(arrete_id="1980-01-01", article_id="1")
    tgt_add = NodeId(arrete_id="1980-01-01", article_id="2")
    tgt_propagated = NodeId(arrete_id="1980-01-01", article_id="4")
    add_node(G, src_ok)
    add_node(G, src_err)
    add_node(G, tgt_replace)
    add_node(G, tgt_add)
    add_node(G, tgt_propagated)
    add_edge(
        G,
        Operation(
            id="op-ok",
            source_id=src_ok,
            target_id=tgt_replace,
            operation_type=OperationType.REPLACE,
            operand="x",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op-add",
            source_id=src_err,
            target_id=tgt_add,
            operation_type=OperationType.ADD,
            operand="y",
        ),
    )
    add_edge(
        G,
        Operation(
            id="op-err",
            source_id=src_err,
            target_id=tgt_propagated,
            operation_type=OperationType.REPLACE,
            operand=None,
            status_code=StatusCode.ERROR_EXTRACTING_OPERAND,
        ),
    )
    history: ArticleHistory = {
        tgt_replace: [{"version": 0, "title": "", "content": "v0", "operation_id": None}],
        tgt_add: [{"version": 0, "title": "", "content": "v0", "operation_id": None}],
        tgt_propagated: [{"version": 0, "title": "", "content": "v0", "operation_id": None}],
    }

    _out, skipped, resolved = apply_subgraph_operations(G, history)

    assert skipped == []
    assert resolved == {
        "op-ok": StatusCode.RESOLVED,
        "op-add": StatusCode.RESOLVED,
        "op-err": StatusCode.ERROR_EXTRACTING_OPERAND,
    }
