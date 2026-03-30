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

from copy import copy

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
    SubTargetType,
    article_display_number,
)
from ocapi.utils.llm_utils import call_llm_api, config_model_llm, query_llm_for_subtarget
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.subtarget_utils import (
    insert_content_after_subtarget,
    is_simple_subtarget,
    replace_subtarget,
)

_LOGGER = get_logger(__name__)
LLM_CFG = config_model_llm()


def _is_unambiguous_all_operation(op: Operation) -> bool:
    """Return True when the operation fully replaces or removes an article.

    Such operations do not depend on the current content of the target article
    (the whole content is discarded) so they can be applied even if a previous
    version had an unresolved error.

    Unambiguous cases:
    - REPLACE with ``sub_target.type == FULL_SECTION`` ("replace all")
    - REMOVE  with ``sub_target.type == FULL_SECTION`` ("remove all")
    """
    if op.operation_type not in (OperationType.REPLACE, OperationType.REMOVE):
        return False
    return op.sub_target is not None and op.sub_target.type == SubTargetType.FULL_SECTION


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


def _llm_consolidation_log(operation: Operation, action: str) -> None:
    """Log LLM fallback for add / replace / remove (complex or ambiguous sub-target)."""
    op_type = (
        operation.operation_type.value
        if isinstance(operation.operation_type, OperationType)
        else str(operation.operation_type)
    )
    _LOGGER.info(
        "LLM consolidation fallback: operation_id=%s action=%s operation_type=%s target=%s",
        operation.id,
        action,
        op_type,
        operation.target_id,
    )


def apply_replace(
    operation: Operation,
    soup_input: Content | BeautifulSoup,
    *,
    source_content: str | None = None,
) -> Content:
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
    source_content : str | None
        Optional HTML of the source article (arrêté modifiant), passed to the LLM
        when regex resolution fails or the sub-target is complex.

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
    soup = _ensure_soup(soup_input)
    if is_simple_subtarget(operation.sub_target):
        try:
            modified_soup = replace_subtarget(soup, operation.sub_target, operation.operand)
            return str(modified_soup)
        except ValueError:
            # Ambiguity detected, fall back to LLM
            _llm_consolidation_log(operation, "replace")
    else:
        _llm_consolidation_log(operation, "replace")
    # Complex or ambiguous case: use the LLM
    prompt = query_llm_for_subtarget(
        OperationType.REPLACE,
        str(soup),
        operation.sub_target.description or "",
        source_content=source_content,
    )
    raw = call_llm_api(LLM_CFG, prompt)
    output = str(soup)
    for line in raw.splitlines():
        if "<NEWCONTENT>" in line:
            output = line.replace("<NEWCONTENT>", operation.operand)
            break
    return output


def apply_remove(
    operation: Operation,
    soup_input: Content | BeautifulSoup,
    *,
    source_content: str | None = None,
) -> Content:
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
    soup = _ensure_soup(soup_input)
    if is_simple_subtarget(sub_target):
        try:
            modified_soup = replace_subtarget(soup, sub_target, "")
            return str(modified_soup)
        except ValueError:
            _llm_consolidation_log(operation, "remove")
    else:
        _llm_consolidation_log(operation, "remove")
    # Complex or ambiguous case: use the LLM
    prompt = query_llm_for_subtarget(
        OperationType.REMOVE,
        str(soup),
        sub_target.description or "",
        source_content=source_content,
    )
    raw = call_llm_api(LLM_CFG, prompt)
    output = str(soup)
    for line in raw.splitlines():
        if "<NEWCONTENT>" in line:
            output = line.replace("<NEWCONTENT>", "")
            break
    return output


def _append_operand_to_section_body(soup: BeautifulSoup, operand: str) -> str:
    """Append operand HTML fragments at the end of an existing article section."""
    operand_soup = BeautifulSoup(operand, "html.parser")
    for child in list(operand_soup.contents):
        if isinstance(child, str) and not str(child).strip():
            continue
        soup.append(copy(child))
    return str(soup)


def _wrap_new_article_section_html(article_id: str, operand: str) -> str:
    """Build a full ``<section>`` for a brand-new article (``NEW_ARTICLE:x.x``).

    When the operand is already a ``<section>`` element, return it as-is to
    avoid double-wrapping.
    """
    stripped = operand.strip()
    if stripped.startswith("<section"):
        return stripped
    num = article_display_number(article_id)
    return f'<section data-spec="section" data-number="{num}">{operand}</section>'


def _is_new_article_full_section_add(op: Operation) -> bool:
    """True when ADD creates a full new article (single initial history version).

    Covers both the explicit ``FULL_SECTION`` sub-target case and the case where
    the detection step produced a ``NEW_ARTICLE`` target with no sub-target.
    """
    if op.operation_type != OperationType.ADD:
        return False
    if not op.target_id.article_id.startswith("NEW_ARTICLE"):
        return False
    if op.sub_target is None:
        return True
    st = op.sub_target.type
    if isinstance(st, str):
        st = SubTargetType(st)
    return st == SubTargetType.FULL_SECTION


def apply_add(
    operation: Operation,
    soup_input: Content | BeautifulSoup,
    *,
    source_content: str | None = None,
) -> Content:
    """Apply an ADD operation to an article's content.

    - ``FULL_SECTION`` + ``NEW_ARTICLE:…``: wrap operand as a new section (no LLM).
    - ``FULL_SECTION`` on an existing article: append operand at the end of the section.
    - Other simple sub-targets: insert operand after the matched fragment (regex).
    - ``COMPLEX`` sub-target: LLM-assisted insertion via ``<NEWCONTENT>``.

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
    """
    if operation.operand is None:
        raise OperationError("ADD operations require operand.")

    if _is_new_article_full_section_add(operation):
        return _wrap_new_article_section_html(operation.target_id.article_id, operation.operand)

    if operation.sub_target is None:
        raise OperationError("ADD operations require sub_target.")
    sub_target = operation.sub_target
    soup = _ensure_soup(soup_input)
    st = sub_target.type
    if isinstance(st, str):
        st = SubTargetType(st)

    if st == SubTargetType.FULL_SECTION:
        return _append_operand_to_section_body(soup, operation.operand)

    if is_simple_subtarget(sub_target):
        modified = insert_content_after_subtarget(soup, sub_target, operation.operand)
        return str(modified)

    _llm_consolidation_log(operation, "add")
    desc = sub_target.description or ""
    prompt = query_llm_for_subtarget(
        OperationType.ADD, str(soup), desc, source_content=source_content
    )
    raw = call_llm_api(LLM_CFG, prompt)
    output = str(soup)
    for line in raw.splitlines():
        if "<NEWCONTENT>" in line:
            output = line.replace("<NEWCONTENT>", operation.operand)
            break
    return output


def apply_subgraph_operations(
    subG: nx.MultiDiGraph, history: ArticleHistory
) -> tuple[ArticleHistory, list[tuple[OperationId, str]]]:
    """Apply sub-graph operations and update the article history.

    For each operation, appends a new version to the target article's history.
    For ADD + ``FULL_SECTION`` + ``NEW_ARTICLE:…``, a **single** version ``0`` is
    stored with ``operation_id`` set to the creation operation (#377).

    Returns the updated history and the list of failed operations.

    Operations may carry ``status_code=COMPLEX_SUBTARGET`` to indicate that the
    sub-target requires LLM consolidation; that code is **not** copied onto the
    article history as an error — the apply functions run the LLM path instead.

    Error propagation
    -----------------
    If the latest version of a target article carries a non-resolved
    ``status_code`` (e.g. ``ERROR_EXTRACTING_OPERAND`` or ``PROPAGATED_ERROR``),
    the new operation is *not* applied and the new version receives
    ``status_code = PROPAGATED_ERROR`` — unless the operation is *unambiguous*
    (see :func:`_is_unambiguous_all_operation`).  Unambiguous operations
    (REPLACE or REMOVE with ``sub_target.type == FULL_SECTION``) discard the
    existing content entirely, so the previous error is irrelevant and the
    operation is applied normally.
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

                creation = _is_new_article_full_section_add(op)

                # Retrieve current content (latest version) of the target article
                if tgt not in history:
                    if not creation:
                        initial_content = subG.nodes[tgt].get("content", "")
                        history[tgt] = [
                            ArticleVersion(
                                version=0,
                                content=initial_content,
                                operation_id=None,
                            )
                        ]

                if tgt not in history:
                    current_content = subG.nodes[tgt].get("content", "") or ""
                else:
                    current_content = history[tgt][-1]["content"]

                # HTML of the source article (arrêté modifiant), for LLM consolidation prompts.
                raw_src = subG.nodes[src].get("content", "") or ""
                source_html = raw_src if isinstance(raw_src, str) else str(raw_src)

                # Propagate an earlier error unless the operation is unambiguous
                # (i.e. it replaces/removes the full article and does not rely on
                # the current — potentially corrupted — content).
                previous_status = history[tgt][-1].get("status_code") if tgt in history else None
                previous_has_error = (
                    previous_status is not None and previous_status != StatusCode.RESOLVED
                )

                article_status_code: StatusCode
                new_content = current_content
                if previous_has_error and not _is_unambiguous_all_operation(op):
                    article_status_code = StatusCode.PROPAGATED_ERROR
                    _LOGGER.warning(
                        f"Operation {op.id} skipped (propagated_error): "
                        f"target={tgt} had previous status_code={previous_status}"
                    )
                else:
                    try:
                        if op.status_code in (
                            StatusCode.ERROR_EXTRACTING_OPERAND,
                            StatusCode.ERROR_EXTRACTING_TARGET,
                        ):
                            article_status_code = op.status_code
                        elif op.operation_type == OperationType.REPLACE:
                            new_content = apply_replace(
                                op,
                                BeautifulSoup(current_content, "html.parser"),
                                source_content=source_html,
                            )
                            article_status_code = StatusCode.RESOLVED
                        elif op.operation_type == OperationType.REMOVE:
                            new_content = apply_remove(
                                op,
                                BeautifulSoup(current_content, "html.parser"),
                                source_content=source_html,
                            )
                            article_status_code = StatusCode.RESOLVED
                        elif op.operation_type == OperationType.ADD:
                            new_content = apply_add(
                                op,
                                BeautifulSoup(current_content, "html.parser"),
                                source_content=source_html,
                            )
                            article_status_code = StatusCode.RESOLVED
                        else:
                            raise OperationError(f"Unknown operation type: {op.operation_type}")
                    except SubtargetNotFoundError as e:
                        _LOGGER.warning(f"Operation {op_id}: sub-target element not found — {e}")
                        article_status_code = StatusCode.ERROR_FINDING_SUBTARGET
                    except ComplexSubtargetError as e:
                        _LOGGER.warning(
                            f"Operation {op_id}: complex sub-target, not resolved — {e}"
                        )
                        article_status_code = StatusCode.COMPLEX_SUBTARGET

                if creation:
                    new_version = ArticleVersion(
                        version=0,
                        content=new_content,
                        operation_id=op.id,
                    )
                    if article_status_code != StatusCode.RESOLVED:
                        new_version["status_code"] = article_status_code
                    history[tgt] = [new_version]
                    continue

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
