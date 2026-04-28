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
"""Helpers to annotate source articles with operation-result messages.

Used by both ``make_other`` (modifying arrêtés) and ``make_main_content``
(main consolidated AP) so the same per-article messages appear wherever the
source arrêté is rendered.
"""

from collections import defaultdict

from bs4 import BeautifulSoup

from ocapi.types import (
    ArticleHistory,
    Operation,
    StatusCode,
    article_display_number,
    operation_type_label,
    status_code_reason,
)

_WHOLE_ARRETE_ARTICLE_IDS = frozenset({"ALL", "END", "APPENDIX"})


def format_target_reference(op: Operation) -> str:
    """Build the human-readable target reference for an operation message."""
    aid = op.target_id.article_id
    if aid in _WHOLE_ARRETE_ARTICLE_IDS:
        return f"l'arrêté {op.target_id.arrete_id}"
    display = article_display_number(aid)
    return f"l'article {display} de l'arrêté {op.target_id.arrete_id}"


def resolve_operation_status(op: Operation, history: ArticleHistory) -> StatusCode | None:
    """Return the status_code of the ArticleVersion produced by *op*, or None if resolved."""
    target_versions = history.get(op.target_id, [])
    for version in target_versions:
        if version.get("operation_id") == op.id:
            return version.get("status_code")
    return op.status_code


def build_source_operation_messages(
    arrete_id: str,
    operations: list[Operation],
    history: ArticleHistory,
) -> dict[str, list[str]]:
    """Build per-article_id list of HTML messages for source articles of *arrete_id*."""
    ops_by_source_article: dict[str, list[Operation]] = defaultdict(list)
    for op in operations:
        if op.source_id.arrete_id == arrete_id:
            ops_by_source_article[op.source_id.article_id].append(op)

    messages: dict[str, list[str]] = {}
    for article_id, ops in ops_by_source_article.items():
        article_msgs: list[str] = []
        for op in ops:
            status = resolve_operation_status(op, history)
            label = operation_type_label(op.operation_type)
            target = format_target_reference(op)
            if status is None or status == StatusCode.RESOLVED:
                msg = f"Opération de consolidation résolue ({label}) dans {target}"
            else:
                reason = status_code_reason(status) or "opération non résolue"
                msg = (
                    f"Opération de consolidation non résolue ({label}) "
                    f"dans {target} (raison\u00a0: {reason})"
                )
            article_msgs.append(msg)
        if article_msgs:
            messages[article_id] = article_msgs
    return messages


def inject_messages_into_main(main_html: str, messages: dict[str, list[str]]) -> str:
    """Inject operation result messages into a ``<main>`` HTML fragment.

    Messages are inserted right after the section title (``<hX>``), or at the
    beginning of the section if no title is found. Sections are matched by
    ``data-number`` so this works on both raw arrêté sections (``data-spec
    ="section"``) and consolidated ones (``data-spec="section_version"``).
    """
    if not messages:
        return main_html
    soup = BeautifulSoup(main_html, "html.parser")
    for section in soup.find_all("section"):
        article_id = section.get("data-number")
        if not isinstance(article_id, str) or article_id not in messages:
            continue
        title_el = section.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        for msg in reversed(messages[article_id]):
            div = soup.new_tag(
                "div",
                attrs={
                    "data-spec": "operation_result",
                    "style": "color: #1b4d89; font-style: italic; margin: 0.5rem 0;",
                },
            )
            div.string = msg
            if title_el is not None:
                title_el.insert_after(div)
            else:
                section.insert(0, div)
    return str(soup)
