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

This module bridges Arrêtify tagging outputs with OCAPI operation models.
"""
import re
from dataclasses import replace
from typing import Callable, cast

from arretify.semantic_tag_specs import DocumentReferenceSpec, SectionReferenceSpec
from arretify.types import DocumentContext, ProtectedSoup, ProtectedTag
from arretify.utils.html import TAG_ID_ATTR
from arretify.utils.html_semantic import css_selector, get_semantic_tag_data, is_semantic_tag
from arretify.utils.references import build_reference_tree
from bs4 import Tag

from ocapi.semantic_tag_specs import OperationSpec
from ocapi.types import (
    ArreteFile,
    Operation,
    OperationOrigin,
    OperationType,
    RawOperation,
    RawOperationType,
    SubTarget,
    SubTargetType,
    canonicalize_article_id_candidate,
)
from ocapi.utils.arretify_utils import ARRETIFY_SECTION_DATA_SPEC
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.subtarget_utils import parse_subtarget

__all__ = [
    "document_context_to_arrete_file",
    "extract_raw_operations_from_tagged_soup",
    "extract_operations_from_tagged_soup",
]

_LOGGER = get_logger(__name__)

_PARENT_REF_ATTR = "data-parent_reference"
_NUMERIC_DOTTED_ARTICLE_PATTERN = re.compile(r"^\d+(?:\.\d+)*$")


def document_context_to_arrete_file(
    document_context: DocumentContext, base: ArreteFile
) -> ArreteFile:
    """Return ``base`` with its soup swapped for ``document_context.soup``.

    Placeholder for richer enrichment from ``header``/``identification`` tags.
    For now we only ensure the soup matches whatever ``step_tagging`` produced
    so downstream code sees the tagged DOM.
    """
    return replace(base, soup=document_context.soup)


def extract_raw_operations_from_tagged_soup(
    soup: ProtectedSoup, arrete_id: str
) -> list[RawOperation]:
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


def extract_operations_from_tagged_soup(
    soup: ProtectedSoup,
    arrete_id: str,
    next_operation_id: Callable[[], str],
) -> list[Operation]:
    """Extract deterministic operations from tagging when they are reliable enough.

    An operation is considered reliable when:
    - its target article is precise and parsable, or it is a full abrogation;
    - ADD/REPLACE operations have an operand extracted from tagging.
    """
    operations: list[Operation] = []
    for operation_tag in soup.select(css_selector(OperationSpec)):
        operation_data = get_semantic_tag_data(OperationSpec, operation_tag)
        operand_html = _extract_operand_html(soup, operation_data.operand)
        raw_operations = _operation_tag_to_raw_operations(soup, operation_tag, arrete_id)
        for raw_op in raw_operations:
            normalized_raw = _normalize_tagged_raw_operation(raw_op)
            if normalized_raw is None:
                continue

            sub_target = (
                parse_subtarget(normalized_raw.sub_target) if normalized_raw.sub_target else None
            )
            if sub_target is None and normalized_raw.target_article != "ALL":
                sub_target = SubTarget(type=SubTargetType.FULL_SECTION, description="ALL")

            try:
                operation = Operation.from_raw_detection(
                    raw_operation=normalized_raw,
                    operation_id=next_operation_id(),
                    operand=operand_html,
                    sub_target=sub_target,
                )
            except Exception as exc:
                _LOGGER.warning(
                    f"Skipping tagged operation in arrêté {arrete_id} (conversion error): {exc}"
                )
                continue

            if not _is_well_characterized(operation, operand_html):
                continue
            operations.append(operation)

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
        targets = [("", None, None, False, -1)]

    source_article = _infer_source_article(operation_tag)
    failure_message = "; ".join(failure_parts) if failure_parts else None
    if failure_message is not None:
        _LOGGER.warning(
            f"Tagged operation in arrête {arrete_id} partially resolved: {failure_message}"
        )

    range_group_first_seen: set[int] = set()
    operations: list[RawOperation] = []
    for target_arrete, target_article, sub_target, from_range, range_group_id in targets:
        effective_op_type = operation_type
        if operation_type == RawOperationType.REPLACE and from_range:
            if range_group_id in range_group_first_seen:
                effective_op_type = RawOperationType.REMOVE
            else:
                range_group_first_seen.add(range_group_id)

        operations.append(
            RawOperation(
                operation_type=effective_op_type,
                origin=OperationOrigin.REGEX,
                source_arrete=arrete_id,
                source_article=source_article,
                target_arrete=target_arrete,
                target_article=target_article,
                sub_target=sub_target,
                failure_message=failure_message,
            )
        )

    return operations


def _extract_operand_html(soup: ProtectedSoup, operand_tag_id: str | None) -> str | None:
    if not operand_tag_id:
        return None
    operand_tag = _find_by_tag_id(soup, operand_tag_id)
    if operand_tag is None:
        return None
    return str(operand_tag)


def _normalize_tagged_raw_operation(raw_op: RawOperation) -> RawOperation | None:
    source_article = canonicalize_article_id_candidate(raw_op.source_article)
    if source_article is None:
        return None

    target_article = canonicalize_article_id_candidate(raw_op.target_article)
    if target_article is None and raw_op.operation_type == RawOperationType.REMOVE:
        target_article = "ALL"
    if target_article is None:
        return None

    return raw_op.model_copy(
        update={
            "source_article": source_article,
            "target_article": target_article,
        }
    )


def _is_well_characterized(operation: Operation, operand_html: str | None) -> bool:
    if operation.target_id.article_id == "ALL" and operation.operation_type != OperationType.REMOVE:
        return False
    if operation.operation_type in {OperationType.ADD, OperationType.REPLACE} and not operand_html:
        return False
    return True


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
) -> list[tuple[str, str | None, str | None, bool, int]]:
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
        return [(tree_arrete, None, None, False, -1)]

    leaf_set = {id(t) for t in leaf_tags}
    results: list[tuple[str, str | None, str | None, bool, int]] = []
    for article_tag in article_order:
        branches = article_groups[id(article_tag)]
        target_articles, from_range = _extract_target_article_numbers(article_tag)
        deeper_tags = [b[2] for b in branches if len(b) >= 3]
        sub_target: str | None = None
        if deeper_tags:
            selected = [t for t in deeper_tags if id(t) in leaf_set] or deeper_tags
            texts = [_strip_text(" ".join(t.stripped_strings)) for t in selected]
            sub_target = " et ".join(t for t in texts if t) or None
        if not target_articles:
            results.append((tree_arrete, None, sub_target, False, id(article_tag)))
            continue

        for target_article in target_articles:
            results.append((tree_arrete, target_article, sub_target, from_range, id(article_tag)))
    return results


def _extract_target_article_numbers(article_tag: ProtectedTag) -> tuple[list[str], bool]:
    if is_semantic_tag(article_tag, spec_in=[SectionReferenceSpec]):
        section_data = get_semantic_tag_data(SectionReferenceSpec, article_tag)
        start_num = canonicalize_article_id_candidate(section_data.start_num)
        end_num = canonicalize_article_id_candidate(section_data.end_num)
        if start_num and end_num:
            expanded = _expand_article_range(start_num, end_num)
            if expanded:
                return expanded, True
            return [start_num], False
        if start_num:
            return [start_num], False

    text_candidate = _strip_text(" ".join(article_tag.stripped_strings))
    text_article = canonicalize_article_id_candidate(text_candidate)
    return ([text_article], False) if text_article else ([], False)


def _expand_article_range(start_article: str, end_article: str) -> list[str] | None:
    if not _NUMERIC_DOTTED_ARTICLE_PATTERN.match(start_article):
        return None
    if not _NUMERIC_DOTTED_ARTICLE_PATTERN.match(end_article):
        return None

    start_levels = [int(level) for level in start_article.split(".")]
    end_levels = [int(level) for level in end_article.split(".")]
    if len(start_levels) != len(end_levels):
        return None
    if start_levels[:-1] != end_levels[:-1]:
        return None
    if end_levels[-1] < start_levels[-1]:
        return None

    prefix = start_levels[:-1]
    return [
        ".".join([*(str(level) for level in prefix), str(i)])
        for i in range(start_levels[-1], end_levels[-1] + 1)
    ]


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
