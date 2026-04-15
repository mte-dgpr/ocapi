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

from collections import defaultdict

from bs4 import BeautifulSoup

from ocapi.types import ArreteFile, ArticleHistory, Operation, OperationType, StatusCode
from ocapi.utils.arretify_utils import extract_first_spec_html, extract_main


def has_not_out_ops(arrete_file: ArreteFile, operations: list[Operation]) -> bool:
    """Return True if an arrêté generates no outgoing operations.

    An arrêté without outgoing operations is a non-modifying complementary
    arrêté (it does not modify any article of the initial AP).

    Parameters
    ----------
    arrete_file : ArreteFile
        Arrêté to test.
    operations : list[Operation]
        List of all detected operations.

    Returns
    -------
    bool
        ``True`` if the arrêté generates no outgoing operations.
    """
    return all(op.source_id.arrete_id != arrete_file.id for op in operations)


def detect_additional_prescriptions(arrete_files: list[ArreteFile]) -> str:
    # TODO: add LLM calls to detect non-modifying additional prescriptions?
    return ""


_STATUS_CODE_REASONS: dict[StatusCode, str] = {
    StatusCode.ERROR_EXTRACTING_OPERAND: ("le contenu de l'opération n'a pas pu être extrait"),
    StatusCode.ERROR_EXTRACTING_TARGET: ("l'article cible n'a pas pu être extrait"),
    StatusCode.ERROR_FINDING_SUBTARGET: ("la sous-cible n'a pas pu être trouvée dans l'article"),
    StatusCode.COMPLEX_SUBTARGET: (
        "la sous-cible est trop complexe pour être résolue automatiquement"
    ),
    StatusCode.PROPAGATED_ERROR: ("une erreur sur une opération précédente empêche l'application"),
}


def _operation_type_label(op: Operation) -> str:
    if op.operation_type == OperationType.REPLACE:
        return "modification"
    if op.operation_type == OperationType.REMOVE:
        return "abrogation"
    return "ajout"


def _resolve_operation_status(op: Operation, history: ArticleHistory) -> StatusCode | None:
    """Return the status_code of the ArticleVersion produced by *op*, or None if resolved."""
    target_versions = history.get(op.target_id, [])
    for version in target_versions:
        if version.get("operation_id") == op.id:
            return version.get("status_code")
    return op.status_code


def _build_source_operation_messages(
    arrete_id: str,
    operations: list[Operation],
    history: ArticleHistory,
) -> dict[str, list[str]]:
    """Build per-article_id list of HTML messages for source articles of *arrete_id*.

    Each message describes the resolution result of one operation targeting
    a given article in the initial AP.
    """
    ops_by_source_article: dict[str, list[Operation]] = defaultdict(list)
    for op in operations:
        if op.source_id.arrete_id == arrete_id:
            ops_by_source_article[op.source_id.article_id].append(op)

    messages: dict[str, list[str]] = {}
    for article_id, ops in ops_by_source_article.items():
        article_msgs: list[str] = []
        for op in ops:
            status = _resolve_operation_status(op, history)
            label = _operation_type_label(op)
            target = f"l'article {op.target_id.article_id} " f"de l'arrêté {op.target_id.arrete_id}"
            if status is None or status == StatusCode.RESOLVED:
                msg = f"Opération de consolidation résolue ({label}) " f"dans {target}"
            else:
                reason = _STATUS_CODE_REASONS.get(status, "opération non résolue")
                msg = (
                    f"Opération de consolidation non résolue ({label}) "
                    f"dans {target} (raison\u00a0: {reason})"
                )
            article_msgs.append(msg)
        if article_msgs:
            messages[article_id] = article_msgs
    return messages


def _inject_messages_into_main(main_html: str, messages: dict[str, list[str]]) -> str:
    """Inject operation result messages into the source arrêté's ``<main>`` HTML."""
    if not messages:
        return main_html
    soup = BeautifulSoup(main_html, "html.parser")
    for section in soup.find_all("section", attrs={"data-spec": "section"}):
        article_id = section.get("data-number")
        if not isinstance(article_id, str) or article_id not in messages:
            continue
        for msg in messages[article_id]:
            div = soup.new_tag(
                "div",
                attrs={
                    "data-spec": "operation_result",
                    "style": "color: #1b4d89; font-style: italic; margin: 0.5rem 0;",
                },
            )
            div.string = msg
            section.append(div)
    return str(soup)


def make_permit_other(
    arrete_files: list[ArreteFile],
    operations: list[Operation],
    history: ArticleHistory | None = None,
) -> str:
    """Generate the HTML sections for complementary and modifying arrêtés.

    - Non-modifying complementary arrêtés are rendered as before.
    - Modifying arrêtés (those with outgoing operations) get operation result
      messages injected into their source articles.

    Parameters
    ----------
    arrete_files : list[ArreteFile]
        All arrêtés; ``arrete_files[0]`` (initial AP) is skipped.
    operations : list[Operation]
        All detected operations.
    history : ArticleHistory | None
        Article version history, used to determine operation resolution status.

    Returns
    -------
    str
        HTML of the ``permit_complements`` section, or empty string if none.
    """
    complement_sections: list[str] = []
    modifying_sections: list[str] = []

    for i, arrete_file in enumerate(arrete_files):
        if i == 0:
            continue
        if not arrete_file.status:
            continue

        identification = extract_first_spec_html(arrete_file.soup, "identification")
        arrete_title = extract_first_spec_html(arrete_file.soup, "arrete_title")
        main_content = extract_main(arrete_file.soup)

        if has_not_out_ops(arrete_file, operations):
            complement_sections.append(
                f"""
   <article data-spec="permit_complement" data-date="{arrete_file.id}">
    {identification}
    {arrete_title}
    {main_content}
   </article>
"""
            )
        elif history is not None:
            messages = _build_source_operation_messages(
                arrete_file.id,
                operations,
                history,
            )
            annotated_main = _inject_messages_into_main(main_content, messages)
            modifying_sections.append(
                f"""
   <article data-spec="permit_modifying" data-date="{arrete_file.id}">
    {identification}
    {arrete_title}
    {annotated_main}
   </article>
"""
            )

    parts: list[str] = []

    if modifying_sections:
        parts.append(
            f"""
  <section data-spec="permit_modifying_arretes">
   <h2>Arrêtés préfectoraux modificatifs</h2>
{''.join(modifying_sections)}
  </section>
"""
        )

    if complement_sections:
        parts.append(
            f"""
  <section data-spec="permit_complements">
   <h2>Autres dispositions prévues par des arrêtés préfectoraux
    qui ne modifient pas l'arrêté préfectoral d'autorisation</h2>
{''.join(complement_sections)}
  </section>
"""
        )

    return "".join(parts)
