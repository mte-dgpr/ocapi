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
Convert tagged HTML (after ``step_tagging``) into ocapi domain objects.

This module is not wired into the pipeline yet; it lives alongside the LLM-based
``step_detection`` so downstream code can progressively consume Arrêtify tags.
"""
from dataclasses import replace
from typing import cast

from arretify.semantic_tag_specs import DocumentReferenceSpec, SectionReferenceSpec
from arretify.types import DocumentContext, ProtectedSoup, ProtectedTag
from arretify.utils.html import TAG_ID_ATTR
from arretify.utils.html_semantic import css_selector, get_semantic_tag_data, is_semantic_tag
from arretify.utils.references import build_reference_tree
from bs4 import Tag

from ocapi.semantic_tag_specs import OperationSpec
from ocapi.types import ArreteFile, RawOperation
from ocapi.utils.arretify_utils import ARRETIFY_SECTION_DATA_SPEC
from ocapi.utils.logging_utils import get_logger

__all__ = [
    "document_context_to_arrete_file",
    "extract_operations_from_tagged_soup",
]

_LOGGER = get_logger(__name__)

_PARENT_REF_ATTR = "data-parent_reference"


def document_context_to_arrete_file(
    document_context: DocumentContext, base: ArreteFile
) -> ArreteFile:
    """Return ``base`` with its soup swapped for ``document_context.soup``.

    Placeholder for richer enrichment from ``header``/``identification`` tags.
    For now we only ensure the soup matches whatever ``step_tagging`` produced
    so downstream code sees the tagged DOM.
    """
    return replace(base, soup=document_context.soup)


def extract_operations_from_tagged_soup(soup: ProtectedSoup, arrete_id: str) -> list[RawOperation]:
    """Extract ``RawOperation`` objects from a tagged soup.

    Parameters
    ----------
    soup : ProtectedSoup
        HTML soup already processed by :func:`ocapi.step_tagging.step_tagging`.
    arrete_id : str
        ID of the arrêté currently being processed (used for log context).
    """
    operations: list[RawOperation] = []
    for operation_tag in soup.select(css_selector(OperationSpec)):
        operations.extend(_operation_tag_to_raw_operations(soup, operation_tag, arrete_id))
    return operations


def _operation_tag_to_raw_operations(
    soup: ProtectedSoup, operation_tag: ProtectedTag, arrete_id: str
) -> list[RawOperation]:
    data = get_semantic_tag_data(OperationSpec, operation_tag)
    operation_type = data.operation_type

    failure_parts: list[str] = []

    reference_ids = data.references or []
    if not reference_ids:
        failure_parts.append("no references on operation tag")

    leaf_tags: list[ProtectedTag] = []
    for ref_id in reference_ids:
        ref_tag = _find_by_tag_id(soup, ref_id)
        if ref_tag is None:
            failure_parts.append(f"unresolved reference tag_id={ref_id}")
            continue
        leaf_tags.append(ref_tag)

    tree: list[list[ProtectedTag]] = []
    if leaf_tags:
        first_section_leaf = next(
            (t for t in leaf_tags if is_semantic_tag(t, spec_in=[SectionReferenceSpec])),
            None,
        )
        anchor = first_section_leaf or leaf_tags[0]
        try:
            tree = build_reference_tree(anchor)
        except (RuntimeError, AssertionError):
            tree = []

    fallback_arrete = ""
    if not _extract_arrete_date(tree):
        # Fallback for trees without a document root (e.g. only a date tag).
        for ref_tag in leaf_tags:
            document_ref = _resolve_document_reference(soup, ref_tag)
            if document_ref is not None:
                doc_data = get_semantic_tag_data(DocumentReferenceSpec, document_ref)
                if doc_data.date:
                    fallback_arrete = doc_data.date
                    break

    targets = _extract_targets(tree, leaf_tags, fallback_arrete)
    if not targets:
        failure_parts.append("could not resolve target arrete date")
        targets = [("", None, None)]

    source_article = _infer_source_article(operation_tag)
    failure_message = "; ".join(failure_parts) if failure_parts else None
    if failure_message is not None:
        _LOGGER.warning(
            f"Tagged operation in arrête {arrete_id} partially resolved: {failure_message}"
        )

    return [
        RawOperation(
            operation_type=operation_type,
            source_article=source_article,
            target_arrete=target_arrete,
            target_article=target_article,
            sub_target=sub_target,
            failure_message=failure_message,
        )
        for target_arrete, target_article, sub_target in targets
    ]


def _extract_arrete_date(tree: list[list[ProtectedTag]]) -> str:
    for branch in tree:
        if not branch:
            continue
        root = branch[0]
        if is_semantic_tag(root, spec_in=[DocumentReferenceSpec]):
            doc_data = get_semantic_tag_data(DocumentReferenceSpec, root)
            if doc_data.date:
                return str(doc_data.date)
    return ""


def _extract_targets(
    tree: list[list[ProtectedTag]],
    leaf_tags: list[ProtectedTag],
    fallback_arrete: str,
) -> list[tuple[str, str | None, str | None]]:
    """Return one (target_arrete, target_article, sub_target) tuple per article referenced.

    When several articles are referenced (e.g. "les articles 5 et 6 sont supprimés"),
    one tuple is emitted per article so downstream code can split into independent
    operations.
    """
    tree_arrete = _extract_arrete_date(tree) or fallback_arrete

    article_groups: dict[int, list[list[ProtectedTag]]] = {}
    article_order: list[ProtectedTag] = []
    for branch in tree:
        if len(branch) < 2:
            continue
        article_tag = branch[1]
        if not is_semantic_tag(article_tag, spec_in=[SectionReferenceSpec]):
            continue
        key = id(article_tag)
        if key not in article_groups:
            article_groups[key] = []
            article_order.append(article_tag)
        article_groups[key].append(branch)

    if not article_order:
        if not tree_arrete:
            return []
        return [(tree_arrete, None, None)]

    leaf_set = {id(t) for t in leaf_tags}
    results: list[tuple[str, str | None, str | None]] = []
    for article_tag in article_order:
        branches = article_groups[id(article_tag)]
        target_article = _strip_text(" ".join(article_tag.stripped_strings))
        deeper_tags = [b[2] for b in branches if len(b) >= 3]
        sub_target: str | None = None
        if deeper_tags:
            selected = [t for t in deeper_tags if id(t) in leaf_set] or deeper_tags
            texts = [_strip_text(" ".join(t.stripped_strings)) for t in selected]
            sub_target = " et ".join(t for t in texts if t) or None
        results.append((tree_arrete, target_article, sub_target))
    return results


def _infer_source_article(operation_tag: ProtectedTag) -> str | None:
    """Return the ``data-number`` of the closest enclosing section, when any."""
    section = cast(Tag, operation_tag).find_parent(attrs={"data-spec": ARRETIFY_SECTION_DATA_SPEC})
    while isinstance(section, Tag):
        number = section.get("data-number")
        if isinstance(number, str) and number:
            return number
        section = section.find_parent(attrs={"data-spec": ARRETIFY_SECTION_DATA_SPEC})
    return None


def _resolve_document_reference(soup: ProtectedSoup, ref_tag: ProtectedTag) -> ProtectedTag | None:
    if is_semantic_tag(ref_tag, spec_in=[DocumentReferenceSpec]):
        return ref_tag

    current = ref_tag
    # Walk parent_reference chain until we land on a DocumentReference or hit a dead end.
    while True:
        parent_id = current.get(_PARENT_REF_ATTR)
        if not parent_id or not isinstance(parent_id, str):
            return None
        parent = _find_by_tag_id(soup, parent_id)
        if parent is None:
            return None
        if is_semantic_tag(parent, spec_in=[DocumentReferenceSpec]):
            return parent
        current = parent


def _find_by_tag_id(soup: ProtectedSoup, tag_id: str) -> ProtectedTag | None:
    matches = soup.select(f'[{TAG_ID_ATTR}="{tag_id}"]')
    return matches[0] if matches else None


def _strip_text(text: str) -> str:
    return " ".join(text.split())
