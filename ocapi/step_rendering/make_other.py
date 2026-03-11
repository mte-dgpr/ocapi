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

from ocapi.types import ArreteFile, Operation
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


def make_permit_other(arrete_files: list[ArreteFile], operations: list[Operation]) -> str:
    """Generate the HTML section of non-modifying complementary arrêtés.

    Includes only active (non-abrogated) arrêtés that generate no outgoing
    operations, i.e. arrêtés that add prescriptions without modifying the
    initial authorisation AP.

    Parameters
    ----------
    arrete_files : list[ArreteFile]
        All arrêtés; ``arrete_files[0]`` (initial AP) is skipped.
    operations : list[Operation]
        All detected operations, used to filter out modifying arrêtés.

    Returns
    -------
    str
        HTML of the ``permit_complements`` section, or empty string if none.
    """
    complement_sections: list[str] = []
    for i, arrete_file in enumerate(arrete_files):
        if i > 0:  # Skip first file (initial AP)
            if arrete_file.status and has_not_out_ops(arrete_file, operations):
                identification = extract_first_spec_html(arrete_file.soup, "identification")
                arrete_title = extract_first_spec_html(arrete_file.soup, "arrete_title")
                main_content = extract_main(arrete_file.soup)
                complement_sections.append(
                    f"""
   <article data-spec="permit_complement" data-date="{arrete_file.id}">
    {identification}
    {arrete_title}
    {main_content}
   </article>
"""
                )
    if not complement_sections:
        return ""
    return f"""
  <section data-spec="permit_complements">
   <h2>Autres dispositions prévues par des arrêtés préfectoraux
    qui ne modifient pas l'arrêté préfectoral d'autorisation</h2>
{''.join(complement_sections)}
  </section>
"""
