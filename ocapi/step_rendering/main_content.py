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

import logging

from bs4 import BeautifulSoup, Tag

from ocapi.config import FullSectionName
from ocapi.exceptions import InvalidArticleIdError, OcapiError
from ocapi.step_rendering.article_filter import filter_superfluous_sections
from ocapi.step_rendering.operation_messages import (
    build_source_operation_messages,
    inject_messages_into_body,
)
from ocapi.types import (
    ArreteFile,
    ArticleHistory,
    ArticleVersion,
    FileType,
    NodeId,
    Operation,
    OperationType,
    StatusCode,
    SubTargetType,
    article_display_number,
    article_id_sort_tuple,
    operation_type_label,
    status_code_reason,
)
from ocapi.utils.arretify_utils import ARRETIFY_SECTION_DATA_SPEC

_LOGGER = logging.getLogger(__name__)


def _select_initial_ap(arrete_files: list[ArreteFile]) -> ArreteFile:
    """Pick the arrêté to use as the consolidation base.

    Honours a user-provided ``principal`` flag when set (exactly one arrêté
    must be marked). Otherwise prefers the most recent non-abrogated
    AP_AUTORISATION (typically the latest refonte), falling back to the
    first non-abrogated arrêté.
    """
    principals = [af for af in arrete_files if af.principal]
    if len(principals) > 1:
        ids = ", ".join(af.id for af in principals)
        raise OcapiError(f"Multiple arrêtés flagged as principal: {ids}")
    if len(principals) == 1:
        return principals[0]

    active = [af for af in arrete_files if af.status]
    ap_autorisations = [af for af in active if af.file_type == FileType.AP_AUTORISATION]
    if ap_autorisations:
        return ap_autorisations[-1]
    if active:
        return active[0]
    return arrete_files[0]


def make_permit_content(
    history: ArticleHistory, arrete_files: list[ArreteFile], operations: list[Operation]
) -> str:
    """Generate the consolidated permit content from the modification history.

    1. Starts from the first non-abrogated AP (status=True); if the initial arrêté
       was replaced by a refonte (REPLACE ALL), it is skipped.
    2. For each article of that AP, applies the latest version from history
    3. Returns the consolidated HTML (without header)
    """
    ap_initial = _select_initial_ap(arrete_files)
    ap_initial_id = ap_initial.id

    # Clone the soup to avoid mutating the original
    consolidated_soup = BeautifulSoup(str(ap_initial.soup), "html.parser")

    # Extract only the main content (skip header)
    main = consolidated_soup.find("main")
    if main is None:
        return ""

    # Find all sections (articles) in the main element
    sections = main.find_all("section", attrs={"data-spec": ARRETIFY_SECTION_DATA_SPEC})
    filter_superfluous_sections(sections)
    operation_by_id = {operation.id: operation for operation in operations}

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
            ap_initial_id=ap_initial_id,
            operation_by_id=operation_by_id,
        )

    _insert_new_article_sections(
        main=main,
        history=history,
        ap_initial_id=ap_initial_id,
        operation_by_id=operation_by_id,
    )

    messages = build_source_operation_messages(ap_initial_id, operations, history)
    return inject_messages_into_body(str(main), messages)


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
    ap_initial_id: str,
    operation_by_id: dict[str, Operation],
) -> None:
    """Insert sections for ``NEW_ARTICLE:…`` keys after the numerically preceding article."""
    new_keys = [
        k
        for k in history
        if k.arrete_id == ap_initial_id and k.article_id.startswith("NEW_ARTICLE")
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
        assert section_el is not None

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
            ap_initial_id=ap_initial_id,
            operation_by_id=operation_by_id,
        )


def make_section_version(
    section: Tag,
    article_id: str,
    history: ArticleHistory,
    ap_initial_id: str,
    operation_by_id: dict[str, Operation],
) -> None:
    """Modify a section in-place into a SectionVersion with consolidated content.

    Adds the attributes:
    - data-is_modified
    - data-date_version
    """
    section["data-spec"] = "section_version"

    try:
        key = NodeId(arrete_id=ap_initial_id, article_id=article_id)
    except (InvalidArticleIdError, ValueError):
        _LOGGER.info(
            "Skipping section with non-standard article_id=%r (arrêté %s)",
            article_id,
            ap_initial_id,
        )
        section["data-is_modified"] = "false"
        section["data-date_version"] = ap_initial_id
        return

    if key not in history:
        section["data-is_modified"] = "false"
        section["data-date_version"] = ap_initial_id
        return

    versions = history[key]
    history_html = _build_section_history_html(versions=versions, operation_by_id=operation_by_id)
    latest_version = versions[-1]
    latest_operation_id = latest_version.get("operation_id")
    latest_operation = (
        operation_by_id.get(str(latest_operation_id)) if latest_operation_id else None
    )
    latest_date_version = (
        latest_operation.source_id.arrete_id if latest_operation else ap_initial_id
    )

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
    last_status_code = last_version.get("status_code")
    last_operation_id = last_version.get("operation_id")
    last_operation = operation_by_id.get(str(last_operation_id)) if last_operation_id else None
    last_reason = status_code_reason(last_status_code)
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
        status_code = version.get("status_code")
        operation_id = version.get("operation_id")
        operation = operation_by_id.get(str(operation_id)) if operation_id else None
        reason = status_code_reason(status_code)
        if index == 0 and not operation:
            text = "Version de l'arrêté initial"
        elif operation and reason is not None:
            text = (
                f"Opération non résolue "
                f"{operation_type_label(operation.operation_type)} de l'article "
                f"{operation.source_id.article_id} de l'arrêté {operation.source_id.arrete_id}"
                f" (raison : {reason})"
            )
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

_UNRESOLVED_STATUS_CODES = {
    StatusCode.ERROR_EXTRACTING_OPERAND,
    StatusCode.ERROR_FINDING_SUBTARGET,
    StatusCode.COMPLEX_SUBTARGET,
}


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
    status_code = latest_version.get("status_code")
    if status_code in _UNRESOLVED_STATUS_CODES:
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
