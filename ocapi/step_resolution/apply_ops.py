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

from ocapi.exceptions import OperationError, SubtargetNotFoundError
from ocapi.llm_utils import call_llm_api, config_model_llm, query_llm_for_subtarget
from ocapi.llm_utils.logging import llm_consolidation_log
from ocapi.llm_utils.prompts import extract_html_from_llm_response
from ocapi.step_resolution.build_op_graph import split_section_title
from ocapi.types import (
    ArreteFile,
    ArreteId,
    ArticleHistory,
    ArticleVersion,
    Content,
    ErrorCode,
    NodeId,
    Operation,
    OperationId,
    OperationType,
    SubTargetType,
    _to_operation_type,
    article_display_number,
)
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.subtarget_utils import (
    insert_content_after_subtarget,
    is_simple_subtarget,
    replace_subtarget,
)
from ocapi.utils.utils import ensure_soup, normalize_title_text

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
        error_codes=data.get("error_codes") or frozenset(),
    )
    return operation


def _strip_duplicate_section_title(
    operand: str, target_data_number: str, target_title_html: str
) -> str:
    """Remove section envelope and title from operand when they duplicate the target's.

    Titles are stored separately from content; this strips the redundant
    ``<section>`` wrapper + heading from the operand so they don't leak into
    the content.
    """
    operand_soup = BeautifulSoup(operand, "html.parser")
    section = operand_soup.find("section", attrs={"data-number": target_data_number})
    if section is None:
        return operand

    operand_title = section.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    if operand_title is None:
        return operand

    if not target_title_html:
        return operand

    target_title_soup = BeautifulSoup(target_title_html, "html.parser")
    target_title = target_title_soup.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    if target_title is None:
        return operand

    if normalize_title_text(operand_title.get_text()) != normalize_title_text(
        target_title.get_text()
    ):
        return operand

    _LOGGER.debug(
        "Stripping duplicate section title from operand (data-number=%s, title=%r)",
        target_data_number,
        operand_title.get_text(strip=True)[:80],
    )
    operand_title.decompose()
    section.unwrap()
    return str(operand_soup).strip()


def apply_replace(
    operation: Operation,
    soup_input: Content | BeautifulSoup,
    *,
    source_content: str | None = None,
    enable_llm: bool = True,
) -> tuple[frozenset[ErrorCode], Content]:
    """Apply a REPLACE operation to an article's content.

    Simple sub-targets are resolved via regex; complex or ambiguous ones fall
    back to the LLM.

    Parameters
    ----------
    operation : Operation
        REPLACE operation; must have both ``sub_target`` and ``operand``.
    soup_input : Content | BeautifulSoup
        Current HTML content of the target article.
    source_content : str | None
        Optional HTML of the source article (arrêté modifiant), passed to the LLM
        when regex resolution fails or the sub-target is complex.
    enable_llm : bool
        When ``False``, return ``DISABLED_LLM_CALL`` instead of calling the LLM.

    Returns
    -------
    tuple[frozenset[ErrorCode], Content]
        Resolution status (empty when resolved) and HTML content after replacement.

    Raises
    ------
    OperationError
        If ``sub_target`` or ``operand`` is missing from the operation.
    """
    if operation.sub_target is None or operation.operand is None:
        raise OperationError("REPLACE operations require sub_target and operand.")
    soup = ensure_soup(soup_input)
    if is_simple_subtarget(operation.sub_target):
        try:
            modified_soup = replace_subtarget(soup, operation.sub_target, operation.operand)
            return frozenset(), str(modified_soup)
        except ValueError:
            # Ambiguity detected, fall back to LLM
            llm_consolidation_log(operation, "replace")
    else:
        llm_consolidation_log(operation, "replace")
    # Complex or ambiguous case: use the LLM (or skip if disabled)
    if not enable_llm:
        return frozenset({ErrorCode.DISABLED_LLM_CALL}), str(soup)
    prompt = query_llm_for_subtarget(
        OperationType.REPLACE,
        str(soup),
        operation.sub_target.description or "",
        target_article_id=operation.target_id.article_id,
        operand=operation.operand,
        source_content=source_content,
    )
    raw = call_llm_api(LLM_CFG, prompt)
    return frozenset(), extract_html_from_llm_response(raw, str(soup))


def apply_remove(
    operation: Operation,
    soup_input: Content | BeautifulSoup,
    *,
    source_content: str | None = None,
    enable_llm: bool = True,
) -> tuple[frozenset[ErrorCode], Content]:
    """Apply a REMOVE operation to an article's content.

    Simple sub-targets are resolved via regex; complex or ambiguous ones fall
    back to the LLM.

    Parameters
    ----------
    operation : Operation
        REMOVE operation; must have ``sub_target``.
    soup_input : Content | BeautifulSoup
        Current HTML content of the target article.
    source_content : str | None
        Optional HTML of the source article (arrêté modifiant).
    enable_llm : bool
        When ``False``, return ``DISABLED_LLM_CALL`` instead of calling the LLM.

    Returns
    -------
    tuple[frozenset[ErrorCode], Content]
        Resolution status (empty when resolved) and HTML content after removal.

    Raises
    ------
    OperationError
        If ``sub_target`` is missing from the operation.
    """
    if operation.sub_target is None:
        raise OperationError("REMOVE operations require sub_target.")
    sub_target = operation.sub_target
    soup = ensure_soup(soup_input)
    if is_simple_subtarget(sub_target):
        try:
            modified_soup = replace_subtarget(soup, sub_target, "")
            return frozenset(), str(modified_soup)
        except ValueError:
            llm_consolidation_log(operation, "remove")
    else:
        llm_consolidation_log(operation, "remove")
    # Complex or ambiguous case: use the LLM (or skip if disabled)
    if not enable_llm:
        return frozenset({ErrorCode.DISABLED_LLM_CALL}), str(soup)
    prompt = query_llm_for_subtarget(
        OperationType.REMOVE,
        str(soup),
        sub_target.description or "",
        target_article_id=operation.target_id.article_id,
        source_content=source_content,
    )
    raw = call_llm_api(LLM_CFG, prompt)
    return frozenset(), extract_html_from_llm_response(raw, str(soup))


def _append_operand_to_section_body(soup: BeautifulSoup, operand: str) -> str:
    """Append operand HTML fragments at the end of an existing article section."""
    operand_soup = BeautifulSoup(operand, "html.parser")
    for child in list(operand_soup.contents):
        if isinstance(child, str) and not str(child).strip():
            continue
        soup.append(copy(child))
    return str(soup)


def _unwrap_operand_section(operand: str) -> str:
    """Return the inner content if operand is wrapped in a ``<section>``."""
    stripped = operand.strip()
    if not stripped.startswith("<section"):
        return operand
    soup = BeautifulSoup(stripped, "html.parser")
    sec = soup.find("section")
    if sec is None:
        return operand
    return str(sec.decode_contents())


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
    enable_llm: bool = True,
) -> tuple[frozenset[ErrorCode], Content]:
    """Apply an ADD operation to an article's content.

    - ``FULL_SECTION`` + ``NEW_ARTICLE:…``: wrap operand as a new section (no LLM).
    - ``FULL_SECTION`` on an existing article: append operand at the end of the section.
    - Other simple sub-targets: insert operand after the matched fragment (regex).
    - ``COMPLEX`` sub-target: LLM-assisted insertion.

    Parameters
    ----------
    operation : Operation
        ADD operation; must have both ``sub_target`` and ``operand``.
    soup_input : Content | BeautifulSoup
        Current HTML content of the target article.
    source_content : str | None
        Optional HTML of the source article (arrêté modifiant).
    enable_llm : bool
        When ``False``, return ``DISABLED_LLM_CALL`` instead of calling the LLM.

    Returns
    -------
    tuple[frozenset[ErrorCode], Content]
        Resolution status (empty when resolved) and HTML content after insertion.

    Raises
    ------
    OperationError
        If ``sub_target`` or ``operand`` is missing from the operation.
    """
    if operation.operand is None:
        raise OperationError("ADD operations require operand.")

    if _is_new_article_full_section_add(operation):
        return frozenset(), _unwrap_operand_section(operation.operand)

    if operation.sub_target is None:
        raise OperationError("ADD operations require sub_target.")
    sub_target = operation.sub_target
    soup = ensure_soup(soup_input)
    st = sub_target.type
    if isinstance(st, str):
        st = SubTargetType(st)

    if st == SubTargetType.FULL_SECTION:
        return frozenset(), _append_operand_to_section_body(soup, operation.operand)

    if is_simple_subtarget(sub_target):
        modified = insert_content_after_subtarget(soup, sub_target, operation.operand)
        return frozenset(), str(modified)

    # Complex sub-target: use the LLM (or skip if disabled)
    llm_consolidation_log(operation, "add")
    if not enable_llm:
        return frozenset({ErrorCode.DISABLED_LLM_CALL}), str(soup)
    desc = sub_target.description or ""
    prompt = query_llm_for_subtarget(
        OperationType.ADD,
        str(soup),
        desc,
        target_article_id=operation.target_id.article_id,
        operand=operation.operand,
        source_content=source_content,
    )
    raw = call_llm_api(LLM_CFG, prompt)
    return frozenset(), extract_html_from_llm_response(raw, str(soup))


def _apply_single_edge(
    subG: nx.MultiDiGraph,
    src: NodeId,
    tgt: NodeId,
    key: int,
    history: ArticleHistory,
    skipped_ops: list[tuple[OperationId, str]],
    resolved_status: dict[OperationId, frozenset[ErrorCode]],
    *,
    chain_depth: int = 0,
    enable_llm: bool = True,
) -> None:
    """Apply one edge and recursively propagate to downstream targets."""
    op_id = None
    try:
        op = _edge_to_operation(subG, src, tgt, key)
        op_id = op.id

        # When re-applying a downstream edge in a chain, use the source's
        # latest resolved content as the operand.
        if chain_depth > 0 and tgt in history:
            source_latest = history[src][-1]["content"] if src in history else None
            if source_latest is not None and op.operand is not None:
                op = op.model_copy(update={"operand": source_latest})

        creation = _is_new_article_full_section_add(op)

        # Retrieve current content (latest version) of the target article
        if tgt not in history:
            if not creation:
                initial_content = subG.nodes[tgt].get("content", "")
                initial_title = subG.nodes[tgt].get("title", "")
                history[tgt] = [
                    ArticleVersion(
                        version=0,
                        title=initial_title,
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
        previous_status = (
            history[tgt][-1].get("error_codes") if tgt in history else None
        ) or frozenset()
        previous_has_error = bool(previous_status)

        article_error_codes: frozenset[ErrorCode]
        new_content = current_content
        if previous_has_error and not _is_unambiguous_all_operation(op):
            article_error_codes = frozenset({ErrorCode.PROPAGATED_ERROR})
            _LOGGER.warning(
                f"Operation {op.id} skipped (propagated_error): "
                f"target={tgt} had previous error_codes={sorted(c.value for c in previous_status)}"
            )
        else:
            try:
                detection_errors = op.error_codes & {
                    ErrorCode.ERROR_EXTRACTING_OPERAND,
                    ErrorCode.ERROR_EXTRACTING_TARGET,
                }
                if detection_errors:
                    article_error_codes = frozenset(op.error_codes)
                elif op.operation_type == OperationType.REPLACE:
                    if op.operand is None:
                        article_error_codes = frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND})
                    else:
                        target_title_html = (
                            history[tgt][-1].get("title", "")
                            if tgt in history
                            else subG.nodes[tgt].get("title", "")
                        )
                        cleaned = _strip_duplicate_section_title(
                            op.operand,
                            article_display_number(op.target_id.article_id),
                            target_title_html,
                        )
                        if cleaned != op.operand:
                            op = op.model_copy(update={"operand": cleaned})
                        article_error_codes, new_content = apply_replace(
                            op,
                            BeautifulSoup(current_content, "html.parser"),
                            source_content=source_html,
                            enable_llm=enable_llm,
                        )
                elif op.operation_type == OperationType.REMOVE:
                    article_error_codes, new_content = apply_remove(
                        op,
                        BeautifulSoup(current_content, "html.parser"),
                        source_content=source_html,
                        enable_llm=enable_llm,
                    )
                elif op.operation_type == OperationType.ADD:
                    if op.operand is None:
                        article_error_codes = frozenset({ErrorCode.ERROR_EXTRACTING_OPERAND})
                    else:
                        article_error_codes, new_content = apply_add(
                            op,
                            BeautifulSoup(current_content, "html.parser"),
                            source_content=source_html,
                            enable_llm=enable_llm,
                        )
                else:
                    raise OperationError(f"Unknown operation type: {op.operation_type}")
            except SubtargetNotFoundError as e:
                _LOGGER.warning(f"Operation {op_id}: sub-target element not found — {e}")
                article_error_codes = frozenset({ErrorCode.ERROR_FINDING_SUBTARGET})

        resolved_status[op.id] = article_error_codes

        if creation:
            created_title, created_content = split_section_title(new_content)
            new_version = ArticleVersion(
                version=0,
                title=created_title,
                content=created_content,
                operation_id=op.id,
                error_codes=article_error_codes,
            )
            history[tgt] = [new_version]
            return

        # Carry the title forward from the previous version
        prev_title = history[tgt][-1]["title"]
        new_version = ArticleVersion(
            version=len(history[tgt]),
            title=prev_title,
            content=new_content,
            operation_id=op.id,
            error_codes=article_error_codes,
        )
        history[tgt].append(new_version)

        # Propagate downstream: if the target itself has outgoing edges,
        # re-apply them with the updated content.
        downstream_edges = sorted(
            subG.out_edges(tgt, keys=True),
            key=lambda e: (e[1].arrete_id, e[1].article_id, e[2]),
        )
        for d_src, d_tgt, d_key in downstream_edges:
            _apply_single_edge(
                subG,
                d_src,
                d_tgt,
                d_key,
                history,
                skipped_ops,
                resolved_status,
                chain_depth=chain_depth + 1,
                enable_llm=enable_llm,
            )

    except Exception as e:
        error_msg = f"Operation {op_id or 'unknown'} skipped: {str(e)}"
        _LOGGER.warning(error_msg)
        skipped_ops.append((op_id or "unknown", str(e)))


def apply_subgraph_operations(
    subG: nx.MultiDiGraph, history: ArticleHistory, *, enable_llm: bool = True
) -> tuple[ArticleHistory, list[tuple[OperationId, str]], dict[OperationId, frozenset[ErrorCode]]]:
    """Apply sub-graph operations and update the article history.

    For each operation, appends a new version to the target article's history.
    For ADD + ``FULL_SECTION`` + ``NEW_ARTICLE:…``, a **single** version ``0`` is
    stored with ``operation_id`` set to the creation operation.

    Returns the updated history, the list of failed operations, and a mapping
    of ``{operation_id: resolved_error_codes}`` for every processed operation.

    Operations may carry ``error_codes`` containing ``COMPLEX_SUBTARGET`` to
    indicate that the sub-target requires LLM consolidation; that code is
    **not** copied onto the article history as an error — the apply functions
    run the LLM path instead.

    Error propagation
    -----------------
    If the latest version of a target article carries any
    ``error_codes`` (e.g. ``ERROR_EXTRACTING_OPERAND`` or ``PROPAGATED_ERROR``),
    the new operation is *not* applied and the new version receives
    ``error_codes = {PROPAGATED_ERROR}`` — unless the operation is *unambiguous*
    (see :func:`_is_unambiguous_all_operation`).  Unambiguous operations
    (REPLACE or REMOVE with ``sub_target.type == FULL_SECTION``) discard the
    existing content entirely, so the previous error is irrelevant and the
    operation is applied normally.

    Chain propagation
    -----------------
    When a target node itself has outgoing edges in the subgraph (i.e. it is
    the source of downstream operations), those downstream operations are
    re-applied with the target's updated content as the operand.  This handles
    transitive chains like C → B → A.
    """
    skipped_ops: list[tuple[OperationId, str]] = []
    resolved_status: dict[OperationId, frozenset[ErrorCode]] = {}
    start_nodes = sorted(
        [node for node in subG.nodes if subG.in_degree(node) == 0],
        key=lambda n: (n.arrete_id, n.article_id),
    )
    for start_node in start_nodes:
        edges = sorted(
            subG.out_edges(start_node, keys=True),
            key=lambda e: (e[1].arrete_id, e[1].article_id, e[2]),
        )
        for src, tgt, key in edges:
            _apply_single_edge(
                subG,
                src,
                tgt,
                key,
                history,
                skipped_ops,
                resolved_status,
                enable_llm=enable_llm,
            )

    return history, skipped_ops, resolved_status


def apply_all_ops(
    operations_graph: nx.MultiDiGraph,
    arrete_list: list[ArreteFile],
    *,
    enable_llm: bool = True,
) -> tuple[ArticleHistory, list[tuple[OperationId, str]], dict[OperationId, frozenset[ErrorCode]]]:
    """Build the complete article history by processing arrêtés chronologically.

    Returns a dict ``{NodeId: [versions]}`` with all modifications, the list
    of failed operations, and a mapping of ``{operation_id: resolved_error_codes}``.
    """
    history: ArticleHistory = {}
    all_skipped_ops: list[tuple[OperationId, str]] = []
    all_resolved_status: dict[OperationId, frozenset[ErrorCode]] = {}

    for arrete_file in arrete_list:
        subG = build_next_subgraph(operations_graph, history, arrete_file.id)
        if subG.number_of_edges() > 0:
            history, skipped_ops, resolved_status = apply_subgraph_operations(
                subG, history, enable_llm=enable_llm
            )
            all_skipped_ops.extend(skipped_ops)
            all_resolved_status.update(resolved_status)

    if all_skipped_ops:
        _LOGGER.warning(f"{len(all_skipped_ops)} operation(s) skipped during application")

    return history, all_skipped_ops, all_resolved_status


def _collect_downstream_chain(
    graph: nx.MultiDiGraph, node: NodeId, visited: set[NodeId]
) -> set[NodeId]:
    """Recursively collect nodes reachable through downstream operation chains."""
    collected: set[NodeId] = set()
    for successor in graph.successors(node):
        if successor in visited:
            continue
        collected.add(successor)
        visited.add(successor)
        collected.update(_collect_downstream_chain(graph, successor, visited))
    return collected


def build_next_subgraph(
    operations_graph: nx.MultiDiGraph, history: ArticleHistory, arrete_id: ArreteId
) -> nx.MultiDiGraph:
    """Build the sub-graph of operations defined by the given arrêté.

    Includes downstream chain nodes so that transitive dependencies (e.g.
    C → B → A) are processed within a single subgraph pass.

    Updates node contents with their latest version from the history.
    """
    filtered_nodes: set[NodeId] = set()
    for node in operations_graph.nodes:
        if node.arrete_id == arrete_id:
            filtered_nodes.add(node)
            visited: set[NodeId] = {node}
            for successor in operations_graph.successors(node):
                filtered_nodes.add(successor)
                visited.add(successor)
                filtered_nodes.update(
                    _collect_downstream_chain(operations_graph, successor, visited)
                )

    # Build subgraph with deterministic node/edge ordering (set iteration is random)
    ordered = sorted(filtered_nodes, key=lambda n: (n.arrete_id, n.article_id))
    new_graph = nx.MultiDiGraph()
    for node in ordered:
        new_graph.add_node(node, **operations_graph.nodes[node])
    for u in ordered:
        for _, v, k, data in sorted(
            operations_graph.out_edges(u, keys=True, data=True),
            key=lambda e: (e[1].arrete_id, e[1].article_id, e[2]),
        ):
            if v in filtered_nodes:
                new_graph.add_edge(u, v, key=k, **data)

    # Update node contents with their latest version from the history
    for node in new_graph.nodes:
        if node in history and len(history[node]) > 0:
            latest_version = history[node][-1]
            new_graph.nodes[node]["content"] = latest_version["content"]
            new_graph.nodes[node]["title"] = latest_version["title"]

    return new_graph
