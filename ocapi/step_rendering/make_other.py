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

from ocapi.step_rendering.operation_messages import (
    build_source_operation_messages,
    inject_messages_into_main,
)
from ocapi.types import ArreteFile, ArticleHistory, Operation, StatusCode
from ocapi.utils.arretify_utils import extract_first_spec_html, extract_main


def has_no_ops(arrete_file: ArreteFile, operations: list[Operation]) -> bool:
    """Return True when the arrêté has no outgoing operations (pure complement)."""
    return not any(op.source_id.arrete_id == arrete_file.id for op in operations)


def has_unresolved_ops(arrete_file: ArreteFile, operations: list[Operation]) -> bool:
    """Return True when at least one outgoing operation is not resolved."""
    outgoing = [op for op in operations if op.source_id.arrete_id == arrete_file.id]
    return any(op.status_code != StatusCode.RESOLVED for op in outgoing)


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

        if has_no_ops(arrete_file, operations):
            complement_sections.append(
                f"""
   <article data-spec="permit_complement" data-date="{arrete_file.id}">
    {identification}
    {arrete_title}
    {main_content}
   </article>
"""
            )

        if has_unresolved_ops(arrete_file, operations) and history is not None:
            messages = build_source_operation_messages(
                arrete_file.id,
                operations,
                history,
            )
            annotated_main = inject_messages_into_main(main_content, messages)
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
