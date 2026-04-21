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
Functions to build a directed operations graph from a list of operations.
Each node in the graph represents an article, and each edge represents an operation
between two articles.
"""

from typing import Tuple

import networkx as nx
from bs4 import BeautifulSoup

from ocapi.exceptions import SectionNotFoundError
from ocapi.types import (
    ArreteFile,
    ArreteId,
    Content,
    NodeId,
    Operation,
    OperationType,
    StatusCode,
    SubTargetType,
)
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
    edge_data = operation.model_dump(
        exclude={"source_id", "target_id"},
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
    if section_tag is None:
        title_tag = section_soup.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        if title_tag is None:
            return "", section_html
        title_html = str(title_tag)
        title_tag.decompose()
        return title_html, str(section_soup)

    title_tag = section_tag.find(["h1", "h2", "h3", "h4", "h5", "h6"], recursive=False)
    title_html = str(title_tag) if title_tag else ""
    if title_tag:
        title_tag.decompose()
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
        appendix_tag = soup.select_one('footer[data-spec="appendix"]')
        if appendix_tag is None:
            raise SectionNotFoundError(f"Section {article_id} not found in arrete {arrete_id}")
        else:
            section_tag = appendix_tag.select_one(
                f'section[data-spec="section"][data-number="{article_id}"]'
            )
            if section_tag is None:
                raise SectionNotFoundError(
                    f"Section {article_id} not found in Appendix of arrete {arrete_id}"
                )
            return split_section_title(str(section_tag))

    section_tag = soup.select_one(f'section[data-spec="section"][data-number="{article_id}"]')
    if section_tag is None:
        raise SectionNotFoundError(f"Section {article_id} not found in arrete {arrete_id}")
    return split_section_title(str(section_tag))


def build_graph(
    ops: list[Operation], arrete_files: list[ArreteFile]
) -> Tuple[nx.MultiDiGraph, list[ArreteFile], list[tuple[Operation, str]]]:
    """Build the operations graph.

    Returns the graph, the list of arrêtés, and the list of failed operations.
    """
    G = nx.MultiDiGraph()
    soups: dict[ArreteId, BeautifulSoup] = {
        arrete_file.id: arrete_file.soup for arrete_file in arrete_files
    }
    skipped_ops: list[tuple[Operation, str]] = []  # (operation, reason) for each failure

    for op in ops:
        try:
            if _is_abrogation_arrete(op):
                for arrete_file in arrete_files:
                    if arrete_file.id == op.target_id.arrete_id:
                        arrete_file.status = False
                        break
                continue

            target_soup = soups.get(op.target_id.arrete_id)
            if target_soup is None:
                error_msg = f"Operation {op.id}: arrêté {op.target_id.arrete_id} not found in files"
                _LOGGER.warning(error_msg)
                skipped_ops.append((op, error_msg))
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
                op = op.model_copy(update={"status_code": StatusCode.ERROR_EXTRACTING_TARGET})

            source_soup = soups[op.source_id.arrete_id]
            source_title, source_content = get_node_content(op.source_id, source_soup)
            add_node(G, op.source_id, node_content=source_content, node_title=source_title)
            add_node(G, op.target_id, node_content=target_content, node_title=target_title)
            add_edge(G, op)
        except Exception as e:
            error_msg = f"Operation {op.id} skipped: {str(e)}"
            _LOGGER.warning(error_msg)
            skipped_ops.append((op, str(e)))
            continue

    if skipped_ops:
        _LOGGER.warning(f"{len(skipped_ops)} operation(s) skipped while building the graph")

    return G, arrete_files, skipped_ops


def _is_abrogation_arrete(operation: Operation) -> bool:
    """Return True if the operation abrogates an entire arrêté (REMOVE ALL or REPLACE ALL).

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
    if operation.status_code is not None and operation.status_code != StatusCode.RESOLVED:
        return False
    return True
