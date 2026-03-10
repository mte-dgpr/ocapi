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
    """Indique si un arrêté ne génère aucune opération sortante.

    Un arrêté sans opération sortante est un arrêté complémentaire non
    modificatif (il ne modifie aucun article de l'AP initial).

    Parameters
    ----------
    arrete_file : ArreteFile
        Arrêté à tester.
    operations : list[Operation]
        Liste de toutes les opérations détectées.

    Returns
    -------
    bool
        `True` si l'arrêté ne génère aucune opération sortante.
    """
    return all(op.source_id.arrete_id != arrete_file.id for op in operations)


def detect_additional_prescriptions(arrete_files: list[ArreteFile]) -> str:
    # TODO : refaire des appels LLM pour détecter les prescriptions
    # additionnelles non modificatives ? à voir.
    return ""


def make_permit_other(arrete_files: list[ArreteFile], operations: list[Operation]) -> str:
    """Génère la section HTML des arrêtés complémentaires non modificatifs.

    Inclut uniquement les arrêtés actifs (non abrogés) qui ne génèrent aucune
    opération sortante, c'est-à-dire les arrêtés qui ajoutent des prescriptions
    sans modifier l'AP d'autorisation.

    Parameters
    ----------
    arrete_files : list[ArreteFile]
        Tous les arrêtés ; `arrete_files[0]` (AP initial) est ignoré.
    operations : list[Operation]
        Toutes les opérations détectées, pour filtrer les arrêtés modificatifs.

    Returns
    -------
    str
        HTML de la section `permit_complements`, ou chaîne vide si aucun complément.
    """
    complement_sections: list[str] = []
    for i, arrete_file in enumerate(arrete_files):
        if i > 0:  # Skip first file (AP initial)
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
