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
Functions to build a directed operations graph from a list of operations.
Each node in the graph represents an article, and each edge represents an operation
between two articles.
"""

from typing import Tuple

import networkx as nx
from bs4 import BeautifulSoup, Tag

from ocapi.exceptions import SectionNotFoundError
from ocapi.types import (
    ArreteFile,
    ArreteId,
    Content,
    ErrorCode,
    NodeId,
    Operation,
    OperationType,
    SubTargetType,
)
from ocapi.utils.arretify_utils import ARRETIFY_APPENDIX_DATA_SPEC, ARRETIFY_SECTION_DATA_SPEC
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def add_node(
    G: nx.MultiDiGraph,
    node_id: NodeId,
    node_content: Content | None = None,
    node_title: Content | None = None,
) -> None:
    """Add a node to the graph if it does not already exist.

    Parameters
    ----------
    G : nx.MultiDiGraph
        Operations graph.
    node_id : NodeId
        Identifier of the node to add.
    node_content : Content | None
        Optional HTML content to attach to the node (without title).
    node_title : Content | None
        Optional HTML of the section heading.
    """
    if not G.has_node(node_id):
        node_data: dict[str, Content] = {}
        if node_content is not None:
            node_data["content"] = node_content
        if node_title is not None:
            node_data["title"] = node_title
        G.add_node(node_id, **node_data)


def update_node(
    G: nx.MultiDiGraph,
    node_id: NodeId,
    node_content: Content | None = None,
    node_title: Content | None = None,
) -> None:
    """Update an existing node's content and/or title."""
    if node_content is not None:
        G.nodes[node_id]["content"] = node_content
    if node_title is not None:
        G.nodes[node_id]["title"] = node_title


def add_edge(G: nx.MultiDiGraph, operation: Operation) -> None:
    """Add an edge to the graph from an ``Operation``.

    The edge goes from ``source_id`` to ``target_id`` and carries all operation
    data (type, operand, sub_target) as edge attributes.

    Parameters
    ----------
    G : nx.MultiDiGraph
        Operations graph.
    operation : Operation
        Operation to represent as a directed edge.
    """
    exclude: set[str] = {"source_id", "target_id"}
    if not operation.error_codes:
        exclude.add("error_codes")
    edge_data = operation.model_dump(
        exclude=exclude,
        exclude_none=True,
        exclude_defaults=True,
        mode="json",
    )
    G.add_edge(operation.source_id, operation.target_id, **edge_data)


def split_section_title(section_html: str) -> Tuple[str, str]:
    """Extract ``(title_html, inner_content)`` from a ``<section>`` element.

    Returns the heading (h1–h6) as title, and the remaining inner content
    of the section (without the ``<section>`` wrapper itself).
    """
    section_soup = BeautifulSoup(section_html, "html.parser")
    section_tag = section_soup.find("section")
    if not isinstance(section_tag, Tag):
        title_tag = section_soup.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        if not isinstance(title_tag, Tag):
            return "", section_html
        title_html = str(title_tag)
        title_tag.decompose()
        return title_html, str(section_soup)

    inner_title = section_tag.find(["h1", "h2", "h3", "h4", "h5", "h6"], recursive=False)
    title_html = str(inner_title) if isinstance(inner_title, Tag) else ""
    if isinstance(inner_title, Tag):
        inner_title.decompose()
    return title_html, str(section_tag.decode_contents())


def get_node_content(node: NodeId, soup: BeautifulSoup) -> Tuple[str, str]:
    """Retrieve the ``(title, content)`` of an article from its NodeId.

    Title is the section heading (h1–h6), content is the section HTML without it.
    """
    arrete_id, article_id = node.arrete_id, node.article_id

    if article_id.startswith("NEW_ARTICLE"):
        return "", ""

    if article_id.startswith("APPENDIX"):
        article_id = article_id.split("APPENDIX:", 1)[1]
        appendix_tag = soup.select_one(f'footer[data-spec="{ARRETIFY_APPENDIX_DATA_SPEC}"]')
        if appendix_tag is None:
            raise SectionNotFoundError(f"Section {article_id} not found in arrete {arrete_id}")
        else:
            section_tag = appendix_tag.select_one(
                f'section[data-spec="{ARRETIFY_SECTION_DATA_SPEC}"][data-number="{article_id}"]'
            )
            if section_tag is None:
                raise SectionNotFoundError(
                    f"Section {article_id} not found in Appendix of arrete {arrete_id}"
                )
            return split_section_title(str(section_tag))

    section_tag = soup.select_one(
        f'section[data-spec="{ARRETIFY_SECTION_DATA_SPEC}"][data-number="{article_id}"]'
    )
    if section_tag is None:
        raise SectionNotFoundError(f"Section {article_id} not found in arrete {arrete_id}")
    return split_section_title(str(section_tag))


def build_graph(
    ops: list[Operation], arrete_files: list[ArreteFile]
) -> Tuple[nx.MultiDiGraph, list[ArreteFile], list[tuple[Operation, str]], list[Operation]]:
    """Build the operations graph.

    Returns the graph, the list of arrêtés, the list of skipped operations
    (as ``(operation, reason)`` pairs), and the full operations list with
    their ``error_codes`` updated for the cases handled at graph-building
    time:

    * Full removals (REMOVE/REPLACE ALL) that are successfully applied keep
      ``error_codes`` empty.
    * Full removals whose target arrêté is absent from the permit are marked
      ``MISSING_ARRETE``.
    * Full removals whose target arrêté is ``principal`` are marked
      ``ERROR_EXTRACTING_TARGET`` (likely a detection mistake).
    * Full removals that overlap with narrower operations from the same
      source are marked ``LESS_IMPORTANT``.
    * Non-full-removal operations whose target arrêté is missing are marked
      ``MISSING_ARRETE`` and added to ``skipped_ops``.
    * Operations whose target section is not found receive
      ``ERROR_EXTRACTING_TARGET``; missing source sections receive
      ``ERROR_EXTRACTING_SOURCE``.
    """
    G = nx.MultiDiGraph()
    soups: dict[ArreteId, BeautifulSoup] = {
        arrete_file.id: arrete_file.soup for arrete_file in arrete_files
    }
    principal_ids = {af.id for af in arrete_files if af.principal}
    skipped_ops: list[tuple[Operation, str]] = []  # (operation, reason) for each failure
    updated_ops: list[Operation] = []

    for op in ops:
        try:
            if _is_full_removal_op(op):
                if op.target_id.arrete_id in principal_ids:
                    _LOGGER.warning(
                        "A full removal of the principal arrete has been detected. "
                        "This operation was not resolved."
                    )
                    updated_ops.append(
                        op.model_copy(
                            update={
                                "error_codes": op.error_codes | {ErrorCode.ERROR_EXTRACTING_TARGET}
                            }
                        )
                    )
                    continue
                if _has_more_specific_ops(op, ops):
                    _LOGGER.warning(
                        "Full removal of arrete %s by %s overlaps with narrower operations "
                        "from the same source; dropping the abrogation as LESS_IMPORTANT.",
                        op.target_id.arrete_id,
                        op.source_id.arrete_id,
                    )
                    updated_ops.append(
                        op.model_copy(
                            update={"error_codes": op.error_codes | {ErrorCode.LESS_IMPORTANT}}
                        )
                    )
                    continue
                if op.target_id.arrete_id not in soups:
                    _LOGGER.warning(
                        "Full removal of arrete %s by %s targets an arrete missing "
                        "from the permit; marking MISSING_ARRETE.",
                        op.target_id.arrete_id,
                        op.source_id.arrete_id,
                    )
                    updated_ops.append(
                        op.model_copy(
                            update={"error_codes": op.error_codes | {ErrorCode.MISSING_ARRETE}}
                        )
                    )
                    continue
                for arrete_file in arrete_files:
                    if arrete_file.id == op.target_id.arrete_id:
                        arrete_file.status = False
                        break
                updated_ops.append(op)
                continue

            target_soup = soups.get(op.target_id.arrete_id)
            if target_soup is None:
                error_msg = f"Operation {op.id}: arrêté {op.target_id.arrete_id} not found in files"
                _LOGGER.warning(error_msg)
                op = op.model_copy(
                    update={"error_codes": op.error_codes | {ErrorCode.MISSING_ARRETE}}
                )
                skipped_ops.append((op, error_msg))
                updated_ops.append(op)
                continue

            try:
                target_title, target_content = get_node_content(op.target_id, target_soup)
            except SectionNotFoundError:
                _LOGGER.warning(
                    "Operation %s: target section %s not found — "
                    "creating empty node with ERROR_EXTRACTING_TARGET",
                    op.id,
                    op.target_id,
                )
                target_title, target_content = "", ""
                op = op.model_copy(
                    update={"error_codes": op.error_codes | {ErrorCode.ERROR_EXTRACTING_TARGET}}
                )

            source_soup = soups[op.source_id.arrete_id]
            try:
                source_title, source_content = get_node_content(op.source_id, source_soup)
            except SectionNotFoundError:
                _LOGGER.warning(
                    "Operation %s: source section %s not found — "
                    "creating empty node with ERROR_EXTRACTING_SOURCE",
                    op.id,
                    op.source_id,
                )
                source_title, source_content = "", ""
                op = op.model_copy(
                    update={"error_codes": op.error_codes | {ErrorCode.ERROR_EXTRACTING_SOURCE}}
                )
            add_node(G, op.source_id, node_content=source_content, node_title=source_title)
            add_node(G, op.target_id, node_content=target_content, node_title=target_title)
            add_edge(G, op)
            updated_ops.append(op)
        except Exception as e:
            error_msg = f"Operation {op.id} skipped: {str(e)}"
            _LOGGER.warning(error_msg)
            skipped_ops.append((op, error_msg))
            updated_ops.append(op)
            continue

    if skipped_ops:
        _LOGGER.warning(f"{len(skipped_ops)} operation(s) skipped while building the graph")

    return G, arrete_files, skipped_ops, updated_ops


def _has_more_specific_ops(op: Operation, ops: list[Operation]) -> bool:
    """Return True if *ops* contains other non-full-removal operations from the
    same source arrêté and targeting the same arrêté as *op*.

    A full removal is treated as suspect when narrower operations from the same
    source already touch parts of the target: the abrogation is then most
    likely a detection mistake.
    """
    for other in ops:
        if other is op:
            continue
        if other.source_id.arrete_id != op.source_id.arrete_id:
            continue
        if other.target_id.arrete_id != op.target_id.arrete_id:
            continue
        if _is_full_removal_op(other):
            continue
        return True
    return False


def _is_full_removal_op(operation: Operation) -> bool:
    """Return True if the operation removes or replaces an entire arrêté (REMOVE/REPLACE ALL).

    REMOVE with target ALL = explicit abrogation.
    REPLACE with target ALL = arrêté refonte : the source arrêté replaces the entire
    target arrêté (e.g. 2021 replaces 2020), so the target is effectively abrogated.
    """
    if operation.target_id.article_id != "ALL":
        return False
    if operation.operation_type not in (
        OperationType.REMOVE,
        OperationType.REPLACE,
    ):
        return False
    # A target=ALL with a narrower sub_target is ill-defined: the LLM tried to
    # target something specific inside "all articles". Do not abrogate.
    if operation.sub_target is not None and operation.sub_target.type != SubTargetType.FULL_SECTION:
        return False
    # Only abrogate when the operation was cleanly resolved.
    if operation.error_codes:
        return False
    return True
