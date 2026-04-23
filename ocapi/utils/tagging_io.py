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
Convert tagged HTML (after ``step_tagging``) into ocapi domain objects.

This module is not wired into the pipeline yet; it lives alongside the LLM-based
``step_detection`` so downstream code can progressively consume Arrêtify tags.
"""
from dataclasses import replace

from arretify.semantic_tag_specs import DocumentReferenceSpec, OperationSpec, SectionReferenceSpec
from arretify.types import DocumentContext
from arretify.types import OperationType as ArretifyOperationType
from arretify.utils.html import TAG_ID_ATTR
from arretify.utils.html_semantic import css_selector, get_semantic_tag_data, is_semantic_tag
from bs4 import BeautifulSoup, Tag

from ocapi.types import ArreteFile, RawOperation, RawOperationType
from ocapi.utils.logging_utils import get_logger

__all__ = [
    "document_context_to_arrete_file",
    "extract_operations_from_tagged_soup",
]

_LOGGER = get_logger(__name__)

_PARENT_REF_ATTR = "data-parent_reference"

_OPERATION_TYPE_MAP: dict[ArretifyOperationType, RawOperationType] = {
    ArretifyOperationType.ADD: RawOperationType.ADD,
    ArretifyOperationType.DELETE: RawOperationType.REMOVE,
    ArretifyOperationType.REPLACE: RawOperationType.REPLACE,
}


def document_context_to_arrete_file(
    document_context: DocumentContext, base: ArreteFile
) -> ArreteFile:
    """Return ``base`` with its soup swapped for ``document_context.soup``.

    Placeholder for richer enrichment from ``header``/``identification`` tags.
    For now we only ensure the soup matches whatever ``step_tagging`` produced
    so downstream code sees the tagged DOM.
    """
    return replace(base, soup=document_context.soup)


def extract_operations_from_tagged_soup(soup: BeautifulSoup, arrete_id: str) -> list[RawOperation]:
    """Extract ``RawOperation`` objects from a tagged soup.

    Parameters
    ----------
    soup : BeautifulSoup
        HTML soup already processed by :func:`ocapi.step_tagging.step_tagging`.
    arrete_id : str
        ID of the arrêté currently being processed (used for log context).
    """
    operations: list[RawOperation] = []
    for operation_tag in soup.select(css_selector(OperationSpec)):
        operations.append(_operation_tag_to_raw_operation(soup, operation_tag, arrete_id))
    return operations


def _operation_tag_to_raw_operation(
    soup: BeautifulSoup, operation_tag: Tag, arrete_id: str
) -> RawOperation:
    data = get_semantic_tag_data(OperationSpec, operation_tag)
    operation_type = _OPERATION_TYPE_MAP.get(
        ArretifyOperationType(data.operation_type), RawOperationType.AUTRE
    )

    target_arrete = ""
    target_article: str | None = None
    failure_parts: list[str] = []

    reference_ids = data.references or []
    if not reference_ids:
        failure_parts.append("no references on operation tag")

    for ref_id in reference_ids:
        ref_tag = _find_by_tag_id(soup, ref_id)
        if ref_tag is None:
            failure_parts.append(f"unresolved reference tag_id={ref_id}")
            continue

        if target_article is None and is_semantic_tag(ref_tag, spec_in=[SectionReferenceSpec]):
            target_article = _strip_text(ref_tag.get_text())

        if not target_arrete:
            document_ref = _resolve_document_reference(soup, ref_tag)
            if document_ref is not None:
                doc_data = get_semantic_tag_data(DocumentReferenceSpec, document_ref)
                if doc_data.date:
                    target_arrete = doc_data.date

    if not target_arrete:
        failure_parts.append("could not resolve target arrete date")

    failure_message = "; ".join(failure_parts) if failure_parts else None
    if failure_message is not None:
        _LOGGER.warning(
            f"Tagged operation in arrête {arrete_id} partially resolved: {failure_message}"
        )

    return RawOperation(
        operation_type=operation_type,
        source_article=None,
        target_arrete=target_arrete,
        target_article=target_article,
        failure_message=failure_message,
    )


def _resolve_document_reference(soup: BeautifulSoup, ref_tag: Tag) -> Tag | None:
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


def _find_by_tag_id(soup: BeautifulSoup, tag_id: str) -> Tag | None:
    return soup.select_one(f'[{TAG_ID_ATTR}="{tag_id}"]')


def _strip_text(text: str) -> str:
    return " ".join(text.split())
