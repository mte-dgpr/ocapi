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
import logging
from typing import Any, Callable

from arretify.semantic_tag_specs import (
    AlineaSpec,
    DocumentReferenceSpec,
    PageFooterSpec,
    PageHeaderSpec,
    PageSeparatorSpec,
    SectionReferenceSpec,
)
from arretify.types import DocumentContext, ProtectedTag, SectionType, protect_tag, unprotect_tag
from arretify.utils.html import ensure_tag_id, is_tag
from arretify.utils.html_element_ranges import (
    get_contiguous_elements_left,
    get_contiguous_elements_right,
)
from arretify.utils.html_semantic import (
    SemanticTagSpec,
    get_semantic_tag_data,
    is_semantic_tag,
    update_semantic_tag_data,
)
from arretify.utils.references import build_reference_tree
from bs4 import Tag

from ocapi.semantic_tag_specs import OperationSpec

PAGINATION_TAG_SPECS: list[SemanticTagSpec[Any]] = [
    PageSeparatorSpec,
    PageHeaderSpec,
    PageFooterSpec,
]

_LOGGER = logging.getLogger(__name__)


def resolve_references_and_operands(
    document_context: DocumentContext, operation_tag: ProtectedTag
) -> None:
    operation_data = get_semantic_tag_data(OperationSpec, operation_tag)
    if operation_data.direction == "rtl":
        reference_tags = _find_left_references(document_context, operation_tag)
    elif operation_data.direction == "ltr":
        reference_tags = _find_right_references(document_context, operation_tag)
    else:
        raise ValueError(f"Unknown operation direction: {operation_data.direction!r}")

    if len(reference_tags) == 0:
        _LOGGER.warning("No references found in operation")
        return
    operation_data = update_semantic_tag_data(
        OperationSpec,
        operation_tag,
        references=[ensure_tag_id(document_context.id_counters, tag) for tag in reference_tags],
    )

    if operation_data.has_operand:
        if operation_data.direction == "ltr":
            operand_tag = _find_ltr_operand(document_context, operation_tag)
        else:
            operand_tag = _find_rtl_operand(document_context, operation_tag)
        if operand_tag is None:
            _LOGGER.warning("No operand found for operation")
            return
        operation_data = update_semantic_tag_data(
            OperationSpec,
            operation_tag,
            operand=ensure_tag_id(document_context.id_counters, operand_tag),
        )


def _find_right_operand(
    document_context: DocumentContext, start_tag: ProtectedTag
) -> ProtectedTag | None:
    for element in get_contiguous_elements_right(start_tag):
        if is_tag(
            element,
            tag_name_in=[
                "blockquote",
                "q",
                "table",
            ],
        ):
            return element

        # We ignore inline tags like page separators and footers
        # and look recursively for the next neighbouring element.
        elif is_semantic_tag(element, spec_in=PAGINATION_TAG_SPECS):
            return _find_right_operand(document_context, element)
    return None


def _find_rtl_operand(
    document_context: DocumentContext, start_tag: ProtectedTag
) -> ProtectedTag | None:
    operand_in_same_alinea = _find_operand_in_same_alinea(start_tag)
    if operand_in_same_alinea is not None:
        return operand_in_same_alinea

    return _find_operand_in_next_alinea(start_tag)


def _find_ltr_operand(
    document_context: DocumentContext, start_tag: ProtectedTag
) -> ProtectedTag | None:
    """Find operand to the right of LTR operations.

    LTR operations frequently include target references between the operation
    keyword and the operand. We therefore first hop after the contiguous
    reference block, then fallback to a direct right lookup.
    """
    last_reference_tag: ProtectedTag | None = None
    for element in get_contiguous_elements_right(start_tag):
        if is_semantic_tag(element, spec_in=[SectionReferenceSpec, DocumentReferenceSpec]):
            last_reference_tag = element

    if last_reference_tag is not None:
        operand_after_refs = _find_operand_in_same_alinea(last_reference_tag)
        if operand_after_refs is not None:
            return operand_after_refs

    operand_in_same_alinea = _find_operand_in_same_alinea(start_tag)
    if operand_in_same_alinea is not None:
        return operand_in_same_alinea

    return _find_operand_in_next_alinea(start_tag)


def _find_operand_in_same_alinea(anchor_tag: ProtectedTag) -> ProtectedTag | None:
    alinea_tag = _find_parent_alinea(anchor_tag)
    if alinea_tag is None:
        return None

    seen_anchor = False
    for element in unprotect_tag(alinea_tag).descendants:
        if element is unprotect_tag(anchor_tag):
            seen_anchor = True
            continue
        if not seen_anchor:
            continue
        if isinstance(element, Tag):
            protected_element = protect_tag(element)
            if is_tag(
                protected_element,
                tag_name_in=[
                    "blockquote",
                    "q",
                    "table",
                ],
            ):
                return protected_element
    return None


def _find_operand_in_next_alinea(start_tag: ProtectedTag) -> ProtectedTag | None:
    alinea_tag = _find_parent_alinea(start_tag)
    if alinea_tag is None:
        return None

    next_alinea_tag = _find_next_alinea_sibling(alinea_tag)
    if next_alinea_tag is None:
        return None

    for element in unprotect_tag(next_alinea_tag).descendants:
        if isinstance(element, Tag):
            protected_element = protect_tag(element)
            if is_tag(
                protected_element,
                tag_name_in=[
                    "blockquote",
                    "table",
                ],
            ):
                return protected_element
    return None


def _find_parent_alinea(start_tag: ProtectedTag) -> ProtectedTag | None:
    if is_semantic_tag(start_tag, spec_in=[AlineaSpec]):
        return start_tag

    parent: Any = unprotect_tag(start_tag).parent
    while isinstance(parent, Tag):
        protected_parent = protect_tag(parent)
        if is_semantic_tag(protected_parent, spec_in=[AlineaSpec]):
            return protected_parent
        parent = unprotect_tag(protected_parent).parent
    return None


def _find_next_alinea_sibling(alinea_tag: ProtectedTag) -> ProtectedTag | None:
    for sibling in unprotect_tag(alinea_tag).next_siblings:
        if not isinstance(sibling, Tag):
            continue
        protected_sibling = protect_tag(sibling)
        if is_semantic_tag(protected_sibling, spec_in=PAGINATION_TAG_SPECS):
            continue
        if is_semantic_tag(protected_sibling, spec_in=[AlineaSpec]):
            return protected_sibling
        break
    return None


def _find_left_references(
    document_context: DocumentContext, start_tag: ProtectedTag
) -> list[ProtectedTag]:
    return _find_references(
        document_context,
        start_tag,
        get_contiguous_elements_left,
        _find_left_references,
    )


def _find_right_references(
    document_context: DocumentContext, start_tag: ProtectedTag
) -> list[ProtectedTag]:
    return _find_references(
        document_context,
        start_tag,
        get_contiguous_elements_right,
        _find_right_references,
    )


def _find_references(
    document_context: DocumentContext,
    start_tag: ProtectedTag,
    get_contiguous_elements: Callable[[ProtectedTag], list[Any]],
    recurse: Callable[[DocumentContext, ProtectedTag], list[ProtectedTag]],
) -> list[ProtectedTag]:
    contiguous_elements = get_contiguous_elements(start_tag)
    reference_tags: list[ProtectedTag] = []

    for element in contiguous_elements:
        if is_semantic_tag(
            element,
            spec_in=[
                SectionReferenceSpec,
                DocumentReferenceSpec,
            ],
        ):
            # Take the leaves of the reference tree, i.e. the most
            # specific reference in a chain of sections.
            # For example in "l'alinéa 3 de l'article 5 du présent arrêté",
            # the operation applies to "alinéa 3".
            reference_tree = build_reference_tree(element)
            reference_tags = _extract_relevant_reference_leaves(reference_tree)
            if len(reference_tags) == 0:
                # Keep scanning neighbours when this branch only yields ignored
                # references (e.g. section_reference type="tableau").
                continue
            break

        # We ignore inline tags like page separators and footers
        # and look recursively for the next neighbouring element.
        elif is_semantic_tag(element, spec_in=PAGINATION_TAG_SPECS):
            return recurse(document_context, element)

    if len(reference_tags) == 0:
        for element in contiguous_elements:
            if is_semantic_tag(element, spec_in=[DocumentReferenceSpec]):
                reference_tags = [element]
                break

    return reference_tags


def _extract_relevant_reference_leaves(
    reference_tree: list[list[ProtectedTag]],
) -> list[ProtectedTag]:
    """Extract the most specific useful references from a reference tree.

    Business rule for table references:
    - if a table reference has parents in the same branch (e.g. "tableau de
      l'article X"), the table itself is the target and must be kept;
    - if a table reference is alone (e.g. "le tableau suivant"), it should not
      drive target resolution and is ignored so the scan can continue.
    """
    result: list[ProtectedTag] = []
    seen: set[int] = set()

    for branch in reference_tree:
        for branch_idx in range(len(branch) - 1, -1, -1):
            tag = branch[branch_idx]
            if is_semantic_tag(tag, spec_in=[SectionReferenceSpec]):
                section_type = _get_section_type_value(tag)
                if _is_table_section_type(section_type):
                    if not _has_reference_parent(branch, branch_idx):
                        continue
                key = id(tag)
                if key not in seen:
                    seen.add(key)
                    result.append(tag)
                break

            if is_semantic_tag(tag, spec_in=[DocumentReferenceSpec]):
                key = id(tag)
                if key not in seen:
                    seen.add(key)
                    result.append(tag)
                break

    return result


def _is_table_section_type(section_type: Any) -> bool:
    table_enum = getattr(SectionType, "TABLEAU", None)
    if table_enum is not None and section_type == table_enum:
        return True
    raw_value = getattr(section_type, "value", section_type)
    return str(raw_value).lower() == "tableau"


def _get_section_type_value(tag: ProtectedTag) -> Any:
    try:
        section_data = get_semantic_tag_data(SectionReferenceSpec, tag)
        section_type = section_data.type
        if section_type is not None:
            return section_type
    except Exception:
        # Some snapshot fixtures carry section types not accepted by the
        # current pydantic enum; fallback to the raw HTML attribute.
        pass
    return tag.attrs.get("data-type")


def _has_reference_parent(branch: list[ProtectedTag], branch_idx: int) -> bool:
    for parent_tag in branch[:branch_idx]:
        if is_semantic_tag(parent_tag, spec_in=[SectionReferenceSpec, DocumentReferenceSpec]):
            return True
    return False
