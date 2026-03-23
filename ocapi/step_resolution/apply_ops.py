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
"""
Functions to apply detected operations to the content of arrêté articles.

Each operation is applied according to its type (REPLACE, REMOVE, ADD) and its
sub-target. When the sub-target is complex, a LLM is used to determine where to
insert the modified content.

For each arrêté, a sub-graph of the operations it defines is built and operations
are applied in order. This builds a version history of modified articles across
successive operations.
"""

import networkx as nx
from bs4 import BeautifulSoup

from ocapi.exceptions import ComplexSubtargetError, OperationError, SubtargetNotFoundError
from ocapi.types import (
    ArreteFile,
    ArreteId,
    ArticleHistory,
    ArticleVersion,
    Content,
    NodeId,
    Operation,
    OperationId,
    OperationType,
    StatusCode,
)
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.subtarget_utils import is_simple_subtarget, replace_subtarget

_LOGGER = get_logger(__name__)


def _to_operation_type(raw_type: OperationType | str) -> OperationType:
    """Ensure we always work with an OperationType instance."""
    if isinstance(raw_type, OperationType):
        return raw_type
    raw_str = getattr(raw_type, "value", raw_type)
    return OperationType(raw_str)


def _edge_to_operation(
    operations_graph: nx.MultiDiGraph, src: NodeId, tgt: NodeId, key: int
) -> Operation:
    """Convert a graph edge into an Operation instance."""
    data = operations_graph[src][tgt][key]
    op_type = _to_operation_type(data["operation_type"])
    operation = Operation(
        id=data["id"],
        source_id=src,
        target_id=tgt,
        operation_type=op_type,
        operand=data.get("operand", None),
        sub_target=data.get("sub_target", None),
        status_code=data.get("status_code", None),
    )
    return operation


def _ensure_soup(soup_input: Content | BeautifulSoup) -> BeautifulSoup:
    return (
        soup_input
        if isinstance(soup_input, BeautifulSoup)
        else BeautifulSoup(soup_input, "html.parser")
    )


def apply_replace(operation: Operation, soup_input: Content | BeautifulSoup) -> Content:
    """Apply a REPLACE operation to an article's content.

    Only handles simple sub-targets via regex. Raises ``ComplexSubtargetError``
    for COMPLEX sub-targets and ``SubtargetNotFoundError`` when the target element
    cannot be located.

    Parameters
    ----------
    operation : Operation
        REPLACE operation; must have both ``sub_target`` and ``operand``.
    soup_input : Content | BeautifulSoup
        Current HTML content of the target article.

    Returns
    -------
    Content
        HTML content of the article after replacement.

    Raises
    ------
    OperationError
        If ``sub_target`` or ``operand`` is missing from the operation.
    ComplexSubtargetError
        If the sub-target is of type COMPLEX.
    SubtargetNotFoundError
        If the target element is not found or ambiguous.
    """
    if operation.sub_target is None or operation.operand is None:
        raise OperationError("REPLACE operations require sub_target and operand.")
    if not is_simple_subtarget(operation.sub_target):
        raise ComplexSubtargetError(
            f"Sub-target is COMPLEX for operation {operation.id}: "
            f"'{operation.sub_target.description}'"
        )
    soup = _ensure_soup(soup_input)
    modified_soup = replace_subtarget(soup, operation.sub_target, operation.operand)
    return str(modified_soup)


def apply_remove(operation: Operation, soup_input: Content | BeautifulSoup) -> Content:
    """Apply a REMOVE operation to an article's content.

    Only handles simple sub-targets via regex. Raises ``ComplexSubtargetError``
    for COMPLEX sub-targets and ``SubtargetNotFoundError`` when the target element
    cannot be located.

    Parameters
    ----------
    operation : Operation
        REMOVE operation; must have ``sub_target``.
    soup_input : Content | BeautifulSoup
        Current HTML content of the target article.

    Returns
    -------
    Content
        HTML content of the article after removal of the sub-target.

    Raises
    ------
    OperationError
        If ``sub_target`` is missing from the operation.
    ComplexSubtargetError
        If the sub-target is of type COMPLEX.
    SubtargetNotFoundError
        If the target element is not found or ambiguous.
    """
    if operation.sub_target is None:
        raise OperationError("REMOVE operations require sub_target.")
    sub_target = operation.sub_target
    if not is_simple_subtarget(sub_target):
        raise ComplexSubtargetError(
            f"Sub-target is COMPLEX for operation {operation.id}: " f"'{sub_target.description}'"
        )
    soup = _ensure_soup(soup_input)
    modified_soup = replace_subtarget(soup, sub_target, "")
    return str(modified_soup)


def apply_add(operation: Operation, soup_input: Content | BeautifulSoup) -> Content:
    """Apply an ADD operation to an article's content.

    Simple sub-targets are not yet supported for ADD. COMPLEX sub-targets raise
    ``ComplexSubtargetError``.

    Parameters
    ----------
    operation : Operation
        ADD operation; must have both ``sub_target`` and ``operand``.
    soup_input : Content | BeautifulSoup
        Current HTML content of the target article.

    Returns
    -------
    Content
        HTML content of the article after inserting the new content.

    Raises
    ------
    OperationError
        If ``sub_target`` or ``operand`` is missing from the operation.
    ComplexSubtargetError
        If the sub-target is of type COMPLEX.
    NotImplementedError
        If the sub-target is simple (not yet supported for ADD).
    """
    if operation.sub_target is None or operation.operand is None:
        raise OperationError("ADD operations require sub_target and operand.")
    sub_target = operation.sub_target
    if not is_simple_subtarget(sub_target):
        raise ComplexSubtargetError(
            f"Sub-target is COMPLEX for operation {operation.id}: " f"'{sub_target.description}'"
        )
    raise NotImplementedError("apply_add is not implemented for simple subtargets yet.")


def apply_subgraph_operations(
    subG: nx.MultiDiGraph, history: ArticleHistory
) -> tuple[ArticleHistory, list[tuple[OperationId, str]]]:
    """Apply sub-graph operations and update the article history.

    For each operation, appends a new version to the target article's history.
    Returns the updated history and the list of failed operations.
    """
    skipped_ops: list[tuple[OperationId, str]] = []  # list of (operation_id, error_message)
    start_nodes = [node for node in subG.nodes if subG.in_degree(node) == 0]
    for start_node in start_nodes:
        for succ in subG.successors(start_node):
            if len(list(subG.successors(succ))) > 1:
                raise NotImplementedError(
                    "Branches with multiple successors are not supported yet."
                )

        for src, tgt, key in subG.out_edges(start_node, keys=True):
            op_id = None
            try:
                op = _edge_to_operation(subG, src, tgt, key)
                op_id = op.id

                # Retrieve current content (latest version) of the target article
                if tgt not in history:
                    # Initialise history with version 0 from the target node content
                    # (fallback: empty string)
                    initial_content = subG.nodes[tgt].get("content", "")
                    history[tgt] = [
                        ArticleVersion(
                            version=0,
                            content=initial_content,
                            operation_id=None,
                        )
                    ]

                current_content = history[tgt][-1]["content"]

                article_status_code: StatusCode
                new_content = current_content
                try:
                    if op.status_code == StatusCode.ERROR_EXTRACTING_OPERAND:
                        article_status_code = StatusCode.ERROR_EXTRACTING_OPERAND
                    elif op.operation_type == OperationType.REPLACE:
                        new_content = apply_replace(
                            op, BeautifulSoup(current_content, "html.parser")
                        )
                        article_status_code = StatusCode.RESOLVED
                    elif op.operation_type == OperationType.REMOVE:
                        new_content = apply_remove(
                            op, BeautifulSoup(current_content, "html.parser")
                        )
                        article_status_code = StatusCode.RESOLVED
                    elif op.operation_type == OperationType.ADD:
                        new_content = apply_add(op, BeautifulSoup(current_content, "html.parser"))
                        article_status_code = StatusCode.RESOLVED
                    else:
                        raise OperationError(f"Unknown operation type: {op.operation_type}")
                except SubtargetNotFoundError as e:
                    _LOGGER.warning(f"Operation {op_id}: sub-target element not found — {e}")
                    article_status_code = StatusCode.ERROR_FINDING_SUBTARGET
                except ComplexSubtargetError as e:
                    _LOGGER.warning(f"Operation {op_id}: complex sub-target, not resolved — {e}")
                    article_status_code = StatusCode.COMPLEX_SUBTARGET

                # Append the new version to the history
                new_version = ArticleVersion(
                    version=len(history[tgt]),
                    content=new_content,
                    operation_id=op.id,
                )
                if article_status_code != StatusCode.RESOLVED:
                    new_version["status_code"] = article_status_code
                history[tgt].append(new_version)
            except Exception as e:
                error_msg = f"Operation {op_id or 'unknown'} skipped: {str(e)}"
                _LOGGER.warning(error_msg)
                skipped_ops.append((op_id or "unknown", str(e)))
                continue

    return history, skipped_ops


def apply_all_ops(
    operations_graph: nx.MultiDiGraph,
    arrete_list: list[ArreteFile],
) -> tuple[ArticleHistory, list[tuple[OperationId, str]]]:
    """Build the complete article history by processing arrêtés chronologically.

    Returns a dict ``{NodeId: [versions]}`` with all modifications and the list
    of failed operations.
    """
    history: ArticleHistory = {}
    all_skipped_ops: list[tuple[OperationId, str]] = []

    for arrete_file in arrete_list:
        subG = build_next_subgraph(operations_graph, history, arrete_file.id)
        if subG.number_of_edges() > 0:
            history, skipped_ops = apply_subgraph_operations(subG, history)
            all_skipped_ops.extend(skipped_ops)

    if all_skipped_ops:
        _LOGGER.warning(f"{len(all_skipped_ops)} operation(s) skipped during application")

    return history, all_skipped_ops


def build_next_subgraph(
    operations_graph: nx.MultiDiGraph, history: ArticleHistory, arrete_id: ArreteId
) -> nx.MultiDiGraph:
    """Build the sub-graph of operations defined by the given arrêté.

    Updates node contents with their latest version from the history.
    """
    filtered_nodes: set[NodeId] = set()
    for node in operations_graph.nodes:
        node_arrete_id = node.arrete_id

        if node_arrete_id == arrete_id:
            filtered_nodes.add(node)
            for successor in operations_graph.successors(node):
                filtered_nodes.add(successor)

    new_graph = operations_graph.subgraph(filtered_nodes).copy()

    # Update node contents with their latest version from the history
    for node in new_graph.nodes:
        if node in history and len(history[node]) > 0:
            latest_version = history[node][-1]
            new_graph.nodes[node]["content"] = latest_version["content"]

    return new_graph
