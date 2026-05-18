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

from bs4 import BeautifulSoup, Tag

from ocapi.config import FullSectionName
from ocapi.exceptions import InvalidArticleIdError
from ocapi.step_rendering.article_filter import filter_superfluous_sections
from ocapi.step_rendering.operation_messages import (
    build_source_operation_messages,
    inject_messages_into_body,
)
from ocapi.types import (
    ArreteFile,
    ArticleHistory,
    ArticleVersion,
    ErrorCode,
    NodeId,
    Operation,
    OperationType,
    SubTargetType,
    article_display_number,
    article_id_sort_tuple,
    error_codes_reason,
    operation_type_label,
)
from ocapi.utils.arretify_utils import ARRETIFY_APPENDIX_DATA_SPEC, ARRETIFY_SECTION_DATA_SPEC

_LOGGER = logging.getLogger(__name__)


def make_permit_content(
    history: ArticleHistory,
    arrete: ArreteFile,
    operations: list[Operation],
) -> str:
    """Consolidate one arrêté: apply article history versions to its body.

    Walks the ``<main>`` and the appendix ``<footer>`` of *arrete*, replacing
    each article section with its consolidated ``section_version`` (latest
    content plus collapsed history). Messages for operations sourced from this
    arrêté are then injected into the body. Returns the resulting HTML
    fragment (main + appendix) without the document header.
    """
    arrete_id = arrete.id
    consolidated_soup = BeautifulSoup(str(arrete.soup), "html.parser")
    main = consolidated_soup.find("main")
    appendix = consolidated_soup.find("footer", attrs={"data-spec": ARRETIFY_APPENDIX_DATA_SPEC})
    if not isinstance(main, Tag) and not isinstance(appendix, Tag):
        return ""

    operation_by_id = {operation.id: operation for operation in operations}

    if isinstance(main, Tag):
        sections = main.find_all("section", attrs={"data-spec": ARRETIFY_SECTION_DATA_SPEC})
        filter_superfluous_sections(sections)
        # Re-query after filtering (decomposed sections are gone from the tree)
        sections = main.find_all("section", attrs={"data-spec": ARRETIFY_SECTION_DATA_SPEC})
        for section in sections:
            article_id = section.get("data-number")
            if not article_id or not isinstance(article_id, str):
                continue

            make_section_version(
                section=section,
                article_id=article_id,
                history=history,
                arrete_id=arrete_id,
                operation_by_id=operation_by_id,
            )

        _insert_new_article_sections(
            main=main,
            history=history,
            arrete_id=arrete_id,
            operation_by_id=operation_by_id,
        )

    if isinstance(appendix, Tag):
        for section in appendix.find_all(
            "section", attrs={"data-spec": ARRETIFY_SECTION_DATA_SPEC}
        ):
            data_number = section.get("data-number")
            if not isinstance(data_number, str) or not data_number:
                continue
            make_section_version(
                section=section,
                article_id=f"APPENDIX:{data_number}",
                history=history,
                arrete_id=arrete_id,
                operation_by_id=operation_by_id,
            )

    body_parts: list[str] = []
    if isinstance(main, Tag):
        body_parts.append(str(main))
    if isinstance(appendix, Tag):
        body_parts.append(str(appendix))
    body_html = "".join(body_parts)

    messages = build_source_operation_messages(arrete_id, operations, history)
    return inject_messages_into_body(body_html, messages)


def _top_level_sections(main: Tag) -> list[Tag]:
    """Direct ``<section>`` children of ``main`` (ignore nested sections e.g. in history)."""
    return [c for c in main.children if isinstance(c, Tag) and c.name == "section"]


def _find_predecessor_display_id(new_display: str, pool: set[str]) -> str | None:
    """Return the greatest article number in ``pool`` strictly before ``new_display``."""
    new_t = article_id_sort_tuple(new_display)
    candidates = [p for p in pool if article_id_sort_tuple(p) < new_t]
    if not candidates:
        return None
    return max(candidates, key=article_id_sort_tuple)


def _insert_new_article_sections(
    main: Tag,
    history: ArticleHistory,
    arrete_id: str,
    operation_by_id: dict[str, Operation],
) -> None:
    """Insert sections for ``NEW_ARTICLE:…`` keys after the numerically preceding article."""
    new_keys = [
        k for k in history if k.arrete_id == arrete_id and k.article_id.startswith("NEW_ARTICLE")
    ]
    if not new_keys:
        return

    new_keys_sorted = sorted(new_keys, key=lambda k: article_id_sort_tuple(k.article_id))

    pool: dict[str, Tag] = {}
    for sec in _top_level_sections(main):
        num = sec.get("data-number")
        if isinstance(num, str):
            pool[num] = sec

    for node_key in new_keys_sorted:
        disp = article_display_number(node_key.article_id)
        if disp in pool:
            _LOGGER.info("New article %s already present in main content, skipping", disp)
            continue
        latest = history[node_key][-1]
        latest_content = latest.get("content", "")
        if not isinstance(latest_content, str) or not latest_content.strip():
            continue

        latest_title = latest.get("title", "")
        section_html = (
            f'<section data-spec="section" data-number="{disp}"'
            f' data-type="article">'
            f"{latest_title}{latest_content}</section>"
        )
        frag = BeautifulSoup(section_html, "html.parser")
        section_el = frag.find("section")
        assert isinstance(section_el, Tag)

        pred = _find_predecessor_display_id(disp, set(pool))
        if pred is None:
            first = next(iter(pool.values()), None)
            if first is not None:
                first.insert_before(section_el)
            else:
                main.append(section_el)
        else:
            anchor = pool.get(pred)
            if anchor is None:
                main.append(section_el)
            else:
                anchor.insert_after(section_el)

        pool[disp] = section_el

        make_section_version(
            section=section_el,
            article_id=node_key.article_id,
            history=history,
            arrete_id=arrete_id,
            operation_by_id=operation_by_id,
        )


def make_section_version(
    section: Tag,
    article_id: str,
    history: ArticleHistory,
    arrete_id: str,
    operation_by_id: dict[str, Operation],
) -> None:
    """Modify a section in-place into a SectionVersion with consolidated content.

    Adds the attributes:
    - data-is_modified
    - data-date_version
    """
    section["data-spec"] = "section_version"

    try:
        key = NodeId(arrete_id=arrete_id, article_id=article_id)
    except (InvalidArticleIdError, ValueError):
        _LOGGER.info(
            "Skipping section with non-standard article_id=%r (arrêté %s)",
            article_id,
            arrete_id,
        )
        section["data-is_modified"] = "false"
        section["data-date_version"] = arrete_id
        return

    if key not in history:
        section["data-is_modified"] = "false"
        section["data-date_version"] = arrete_id
        return

    versions = history[key]
    history_html = _build_section_history_html(versions=versions, operation_by_id=operation_by_id)
    latest_version = versions[-1]
    latest_operation_id = latest_version.get("operation_id")
    latest_operation = (
        operation_by_id.get(str(latest_operation_id)) if latest_operation_id else None
    )
    latest_date_version = latest_operation.source_id.arrete_id if latest_operation else arrete_id

    section["data-is_modified"] = "true"
    section["data-date_version"] = latest_date_version

    latest_title = latest_version.get("title", "")
    if latest_title:
        title_html = latest_title
    else:
        section_title = section.find(attrs={"data-spec": "section_title"})
        title_html = str(section_title) if section_title else ""

    section.clear()

    if _is_abrogated(latest_version=latest_version, operation_by_id=operation_by_id):
        consolidated_content = f"{title_html}{history_html}<p><em>Article abrogé</em></p>"
    else:
        latest_content = latest_version.get("content", "")
        consolidated_content = (
            f"{title_html}{history_html}"
            f"{latest_content if isinstance(latest_content, str) else ''}"
        )

    consolidated_soup = BeautifulSoup(consolidated_content, "html.parser")
    for child in list(consolidated_soup.contents):
        section.append(child)


def _build_section_history_html(
    versions: list[ArticleVersion],
    operation_by_id: dict[str, Operation],
) -> str:
    """Build the HTML version history of an article.

    Generates a ``<div data-spec="section_version_history">`` block containing:
    - a description of the current version (bold)
    - previous versions in collapsible ``<details>`` elements

    Parameters
    ----------
    versions : list[ArticleVersion]
        Ordered list of article versions (last item is the current version).
    operation_by_id : dict[str, Operation]
        Operation index by ID, used to retrieve metadata for each version.

    Returns
    -------
    str
        HTML of the history block to insert into the ``section_version``.
    """
    history_parts = [
        '<div data-spec="section_version_history" style="color: #1b4d89; margin-bottom: 1rem;">'
    ]
    if not versions:
        history_parts.append("</div>")
        return "".join(history_parts)

    last_version = versions[-1]
    last_error_codes = last_version.get("error_codes")
    last_operation_id = last_version.get("operation_id")
    last_operation = operation_by_id.get(str(last_operation_id)) if last_operation_id else None
    last_reason = error_codes_reason(last_error_codes)
    if last_operation and last_reason is not None:
        last_text = (
            f"Opération non résolue {operation_type_label(last_operation.operation_type)} "
            f"de l'article {last_operation.source_id.article_id} de l'arrêté "
            f"{last_operation.source_id.arrete_id}"
            f" (raison : {last_reason})"
        )
    elif last_operation:
        last_text = (
            "Version actuelle après "
            f"{operation_type_label(last_operation.operation_type)} "
            f"par l'article {last_operation.source_id.article_id} "
            f"de l'arrêté {last_operation.source_id.arrete_id}"
        )
    else:
        last_text = "Version actuelle de l'arrêté initial"

    history_parts.append(f'<p style="font-weight: bold; margin-top: 0.5rem;">{last_text}</p>')

    for index, version in enumerate(versions[:-1]):
        error_codes = version.get("error_codes")
        operation_id = version.get("operation_id")
        operation = operation_by_id.get(str(operation_id)) if operation_id else None
        reason = error_codes_reason(error_codes)
        if operation and reason is not None:
            # Unresolved op: previous content was just recopied, so the dropdown
            # would only duplicate the surrounding version. Keep the message only.
            history_parts.append(
                f'<p style="margin-left: 1rem; margin-top: 0.5rem;">'
                f"Opération non résolue "
                f"{operation_type_label(operation.operation_type)} de l'article "
                f"{operation.source_id.article_id} de l'arrêté "
                f"{operation.source_id.arrete_id}"
                f" (raison : {reason})</p>"
            )
            continue

        if index == 0 and not operation:
            text = "Version de l'arrêté initial"
        elif operation:
            text = (
                f"Version après {operation_type_label(operation.operation_type)} "
                f"par l'article "
                f"{operation.source_id.article_id} de l'arrêté {operation.source_id.arrete_id}"
            )
        else:
            text = "Version précédente"

        content = version.get("content", "")
        history_parts.append(
            f"""
            <details style="margin-left: 1rem; margin-top: 0.5rem; margin-bottom: 0.5rem;">
             <summary style="cursor: pointer; font-weight: bold;">{text}</summary>
             <div
              style="color: #1b4d89; border-left: 3px solid #1b4d89; padding-left: 1rem;
              margin-top: 0.5rem;"
             >
              {content}
             </div>
            </details>
"""
        )
    history_parts.append("</div>")
    return "".join(history_parts)


_FULL_REMOVAL_DESCRIPTIONS: frozenset[str] = frozenset(name.value for name in FullSectionName)

_UNRESOLVED_ERROR_CODES = frozenset(
    {
        ErrorCode.ERROR_EXTRACTING_OPERAND,
        ErrorCode.ERROR_FINDING_SUBTARGET,
        ErrorCode.COMPLEX_SUBTARGET,
    }
)


def _is_abrogated(
    latest_version: ArticleVersion,
    operation_by_id: dict[str, Operation],
) -> bool:
    """Return True if the latest article version corresponds to a full abrogation.

    An article is considered abrogated if and only if its last operation is a
    REMOVE with sub_target ``FULL_SECTION`` and a description matching one of the
    ``FullSectionName`` values, or without a sub_target (implicit full abrogation),
    AND the operation was successfully resolved.

    Parameters
    ----------
    latest_version : ArticleVersion
        Latest version of the article in history.
    operation_by_id : dict[str, Operation]
        Operation index by ID.

    Returns
    -------
    bool
        ``True`` if the article should be marked as abrogated.
    """
    error_codes = latest_version.get("error_codes") or frozenset()
    if error_codes & _UNRESOLVED_ERROR_CODES:
        return False
    operation_id = latest_version.get("operation_id")
    if not operation_id:
        return False
    latest_operation = operation_by_id.get(str(operation_id))
    if not latest_operation:
        return False
    if latest_operation.operation_type != OperationType.REMOVE:
        return False
    sub_target = latest_operation.sub_target
    if sub_target is None:
        return True
    if sub_target.type != SubTargetType.FULL_SECTION:
        return False
    return sub_target.description in _FULL_REMOVAL_DESCRIPTIONS
