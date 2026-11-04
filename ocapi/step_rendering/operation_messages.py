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
"""Helpers to annotate source articles with operation-result messages.

Used by both ``make_other`` (modifying arrêtés) and ``make_main_content``
(main consolidated AP) so the same per-article messages appear wherever the
source arrêté is rendered.
"""

import logging
from collections import defaultdict
from typing import Literal, NamedTuple

from bs4 import BeautifulSoup, Tag

from ocapi.types import (
    ArticleHistory,
    ErrorCode,
    Operation,
    OperationType,
    SubTargetType,
    article_display_number,
    error_codes_reason,
    operation_type_label,
)
from ocapi.utils.arretify_utils import ARRETIFY_APPENDIX_DATA_SPEC
from ocapi.utils.subtarget_utils import FULL_SECTION_NAMES_LOWER

_LOGGER = logging.getLogger(__name__)

_WHOLE_ARRETE_ARTICLE_IDS = frozenset({"ALL", "END", "APPENDIX"})


def operation_status(error_codes: frozenset[ErrorCode] | None) -> Literal["success", "failure"]:
    return "failure" if error_codes else "success"


class OperationMessage(NamedTuple):
    operation_id: str
    status: Literal["success", "failure"]
    text: str


def format_target_reference(op: Operation) -> str:
    """Build the human-readable target reference for an operation message."""
    aid = op.target_id.article_id
    if aid in _WHOLE_ARRETE_ARTICLE_IDS:
        return f"l'arrêté {op.target_id.arrete_id}"
    display = article_display_number(aid)
    return f"l'article {display} de l'arrêté {op.target_id.arrete_id}"


def is_full_section_removal(op: Operation) -> bool:
    """Return whether *op* removes an entire article."""
    if op.operation_type != OperationType.REMOVE:
        return False
    sub_target = op.sub_target
    if sub_target is None:
        return True
    if sub_target.type != SubTargetType.FULL_SECTION or sub_target.description is None:
        return False
    return sub_target.description.strip().lower() in FULL_SECTION_NAMES_LOWER


def resolve_operation_error_codes(op: Operation, history: ArticleHistory) -> frozenset[ErrorCode]:
    """Return the error codes of the ArticleVersion produced by *op* (empty if resolved)."""
    target_versions = history.get(op.target_id, [])
    for version in target_versions:
        if version.get("operation_id") == op.id:
            return version.get("error_codes", op.error_codes)
    return op.error_codes


def build_source_operation_messages(
    arrete_id: str,
    operations: list[Operation],
    history: ArticleHistory,
    modifying_arrete: bool = False,
) -> dict[str, list[OperationMessage]]:
    """Build per-article_id list of HTML messages for source articles of *arrete_id*."""
    ops_by_source_article: dict[str, list[Operation]] = defaultdict(list)
    for op in operations:
        if op.source_id.arrete_id == arrete_id:
            ops_by_source_article[op.source_id.article_id].append(op)

    messages: dict[str, list[OperationMessage]] = {}
    for article_id, ops in ops_by_source_article.items():
        article_msgs: list[OperationMessage] = []
        for op in ops:
            error_codes = resolve_operation_error_codes(op, history)
            label = operation_type_label(op.operation_type)
            target = format_target_reference(op)
            if not error_codes and modifying_arrete:
                if op.operation_type == OperationType.REPLACE:
                    msg = (
                        "Les dispositions de cet article ont bien été automatiquement intégrées "
                        f"au permis consolidé en remplacement de celles prévues à {target}. "
                        "Vérifiez l'exactitude des dispositions modifiées avant d'effacer "
                        "cet article."
                    )
                elif op.operation_type == OperationType.ADD:
                    msg = (
                        f"L'article suivant a été automatiquement ajouté dans {target}. "
                        "Vérifiez l'exactitude des dispositions ajoutées avant d'effacer "
                        "l'article modificatif."
                    )
                elif is_full_section_removal(op):
                    msg = (
                        f"La suppression prévue dans {target} a fonctionné. "
                        "Vous pouvez supprimer le présent article après vérification."
                    )
                else:
                    msg = f"Opération de consolidation résolue ({label}) dans {target}"
            elif error_codes and modifying_arrete and op.operation_type == OperationType.REPLACE:
                source_article = article_display_number(op.source_id.article_id)
                msg = (
                    "La prise en compte de la modification prévue dans ce présent article "
                    f"pour {target} n'a pas été jusqu'au bout de l'opération. "
                    "Après vérification, vous pouvez intégrer manuellement les dispositions de cet "
                    f"article vers l'article {source_article} de l'arrêté "
                    f"{op.source_id.arrete_id} et effacer le présent article."
                )
            elif error_codes and modifying_arrete and op.operation_type == OperationType.ADD:
                target_arrete_id = op.target_id.arrete_id
                msg = (
                    f"L'ajout de cet article dans {target} n'a pas fonctionné. "
                    f"Vous pouvez vérifier si l'arrêté {target_arrete_id} est intégré dans la "
                    "sélection des arrêtés intégrés au permis consolidé. "
                    f"Si l'arrêté était présent, vous pouvez intégrer manuellement les "
                    f"dispositions de cet article dans l'arrêté {target_arrete_id} et "
                    "l'effacer après vérification. "
                    "Si l'arrêté était manquant, vous pouvez (si nécessaire) regénérer un "
                    "nouveau permis avec tous les arrêtés nécessaires (<!> risque de perte "
                    "d'information sur le permis actuel)."
                )
            elif (
                error_codes
                and modifying_arrete
                and op.operation_type == OperationType.REMOVE
                and ErrorCode.MISSING_ARRETE in error_codes
            ):
                target_arrete_id = op.target_id.arrete_id
                msg = (
                    f"La suppression prévue par cet article dans {target} n'a pas fonctionné. "
                    f"Vous pouvez vérifier si l'arrêté {target_arrete_id} est intégré dans la "
                    "sélection des arrêtés intégrés au permis consolidé. "
                    f"Si l'arrêté était présent, vous pouvez supprimer manuellement les "
                    f"dispositions de cet article dans l'arrêté {target_arrete_id} et "
                    "l'effacer après vérification. "
                    "Si l'arrêté était manquant, vous pouvez (si nécessaire) regénérer un "
                    "nouveau permis avec tous les arrêtés nécessaires (<!> risque de perte "
                    "d'information sur le permis actuel)."
                )
            elif error_codes:
                reason = error_codes_reason(error_codes) or "opération non résolue"
                msg = (
                    f"Opération de consolidation non résolue ({label}) "
                    f"dans {target} (raison\u00a0: {reason})"
                )
            else:
                msg = f"Opération de consolidation résolue ({label}) dans {target}"
            article_msgs.append(OperationMessage(op.id, operation_status(error_codes), msg))
        if article_msgs:
            messages[article_id] = article_msgs
    return messages


def _section_logical_id(section: Tag) -> str | None:
    """Return the logical article id of *section* (with ``APPENDIX:`` prefix when in appendix)."""
    data_number = section.get("data-number")
    if not isinstance(data_number, str):
        return None
    if section.find_parent("footer", attrs={"data-spec": ARRETIFY_APPENDIX_DATA_SPEC}):
        return f"APPENDIX:{data_number}"
    return data_number


def inject_messages_into_body(body_html: str, messages: dict[str, list[OperationMessage]]) -> str:
    """Inject operation result messages into a body HTML fragment.

    The fragment may contain the ``<main>`` element and/or an appendix
    ``<footer data-spec="appendix">``. Messages keyed by ``APPENDIX:x.y`` are
    placed inside the matching appendix section, while plain article ids land
    in the corresponding ``<section>`` of the main.

    Messages are inserted right after the section title (``<hX>``), or at the
    beginning of the section if no title is found. Sections are matched on
    their logical id so this works on both raw arrêté sections
    (``data-spec="section"``) and consolidated ones (``data-spec="section_version"``).
    """
    if not messages:
        return body_html
    soup = BeautifulSoup(body_html, "html.parser")
    injected: set[str] = set()
    for section in soup.find_all("section"):
        article_id = _section_logical_id(section)
        if article_id is None or article_id not in messages:
            continue
        if article_id in injected:
            _LOGGER.warning(
                "Duplicate article_id encountered in arrete while injecting operation messages; "
                "skipping duplicate (article_id=%s)",
                article_id,
            )
            continue
        injected.add(article_id)
        title_el = section.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        for msg in reversed(messages[article_id]):
            div = soup.new_tag(
                "div",
                attrs={
                    "data-spec": "operation_result",
                    "data-operation-id": msg.operation_id,
                    "data-operation-status": msg.status,
                    "style": "color: #1b4d89; font-style: italic; margin: 0.5rem 0;",
                },
            )
            div.string = msg.text
            if title_el is not None:
                title_el.insert_after(div)
            else:
                section.insert(0, div)
    return str(soup)
