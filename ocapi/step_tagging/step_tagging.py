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
from arretify.semantic_tag_specs import AlineaSpec, DocumentReferenceSpec, SectionReferenceSpec
from arretify.types import DocumentContext, ProtectedTagOrStr, unprotect_tag
from arretify.utils.html_create import replace_contents
from arretify.utils.html_semantic import css_selector

from ocapi.semantic_tag_specs import OperationSpec

from .operands_detection import resolve_references_and_operands
from .operations_detection import parse_operations


def _merge_adjacent_strings(contents: list[ProtectedTagOrStr]) -> list[ProtectedTagOrStr]:
    merged: list[ProtectedTagOrStr] = []
    for content in contents:
        if isinstance(content, str) and merged and isinstance(merged[-1], str):
            merged[-1] = merged[-1] + content
        else:
            merged.append(content)
    return merged


def _strip_existing_operation_tags(document_context: DocumentContext) -> None:
    """Unwrap pre-existing operation tags before re-tagging.

    This preserves semantic inner tags (notably references) while removing
    stale operation wrappers; legacy <b> emphasis is unwrapped to recover plain
    text for regex matching.
    """
    for operation_tag in list(document_context.protected_soup.select(css_selector(OperationSpec))):
        # Legacy operation tags often wrap the keyword in <b>; strip that
        # formatting to recover the plain sentence for regex re-tagging.
        for bold_tag in list(operation_tag.select("b")):
            unprotect_tag(bold_tag).unwrap()
        unprotect_tag(operation_tag).unwrap()


def step_tagging(document_context: DocumentContext) -> DocumentContext:
    """Tag operations and resolve their references/operands in the soup.

    Ported from ``arretify.step_consolidation``; runs before detection so
    downstream steps can rely on ``data-spec="operation"`` annotations.
    """
    _strip_existing_operation_tags(document_context)

    container_tags = document_context.protected_soup.select(
        f"{css_selector(AlineaSpec)}, {css_selector(AlineaSpec)} *"
    )
    # Process deeper nodes first: replacing an ancestor's contents can detach
    # previously selected descendants from the active tree.
    for container_tag in reversed(container_tags):
        contents: list[ProtectedTagOrStr] = _merge_adjacent_strings(list(container_tag.contents))
        # Only parse when the alinea carries a document or section reference; avoids
        # a lot of false positives on plain prose.
        document_reference_tags = container_tag.select(
            f"{css_selector(DocumentReferenceSpec)}, {css_selector(SectionReferenceSpec)}"
        )
        if document_reference_tags:
            contents = parse_operations(document_context, contents)
            replace_contents(container_tag, contents)

    for operation_tag in document_context.protected_soup.select(css_selector(OperationSpec)):
        resolve_references_and_operands(document_context, operation_tag)

    return document_context
