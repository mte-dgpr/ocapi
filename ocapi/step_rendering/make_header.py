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


from bs4 import BeautifulSoup

from ocapi.types import ArreteFile


def extract_visa(soup: BeautifulSoup) -> list[str]:
    """
    Extrait les divs 'visa' du header d'un document HTML.

    Cherche des divs avec l'attribut data-spec="visa" et retourne leur contenu HTML.
    Si aucun div n'est trouvé, retourne une liste vide.
    """
    visa_divs = soup.find_all("div", attrs={"data-spec": "visa"})
    if visa_divs:
        return [str(div) for div in visa_divs]
    return []


def extract_motif(soup: BeautifulSoup) -> list[str]:
    """
    Extrait les divs 'motif' du header d'un document HTML.


    Cherche des divs avec l'attribut data-spec="motif" et retourne leur contenu HTML.
    Si aucun div n'est trouvé, retourne une liste vide.
    """

    motif_divs = soup.find_all("div", attrs={"data-spec": "motifs"})
    if motif_divs:
        return [str(div) for div in motif_divs]
    return []


def make_liste_arretes(arrete_files: list[ArreteFile]) -> str:
    """
    Génère la liste des arrêtés utilisés pour construire le permis. (indique si arrêté abrogé)


    Retourne une section HTML listant tous les arrêtés par leur ID et nom de fichier.
    """
    arretes_list = []
    for arrete_file in arrete_files:
        if arrete_file.status:
            arretes_list.append(
                f"<li><strong>Arrêté {arrete_file.id}</strong> : "
                f"{arrete_file.filename} (AIOT: {arrete_file.aiot})</li>"
            )
        else:
            arretes_list.append(
                f"<li><strong>Arrêté {arrete_file.id} (ABROGÉ)</strong> : "
                f"{arrete_file.filename} (AIOT: {arrete_file.aiot})</li>"
            )

    return f"""
   <div data-spec="arrete_title">
    <h1>Permis d'Exploitation Consolidé</h1>
   </div>
   <div data-spec="supplementary_motif_info" style="margin-top: var(--spacing-2);">
    <h2>Arrêtés sources</h2>
    <p>Ce permis consolidé a été construit à partir des arrêtés suivants :</p>
    <ul style="list-style: disc; margin-left: 2rem;">
{''.join(arretes_list)}
    </ul>
   </div>
"""


def make_visa_permis(arrete_files: list[ArreteFile]) -> str:
    """
    Génère la liste consolidée des visas pour le permis à partir des arrete_files.


    Parcourt chaque arrete_file, extrait les visas et les ajoute à une liste.
    Retourne la liste fusionnée des visas = sans doublons.
    """
    visas = []
    for arrete_file in arrete_files:
        if arrete_file.status:
            visas.extend(extract_visa(arrete_file.soup))
    # Supprimer les doublons tout en préservant l'ordre
    seen = set()
    unique_visas = []
    for visa in visas:
        if visa not in seen:
            seen.add(visa)
            unique_visas.append(visa)
    return "\n".join(unique_visas)


def make_motif_permis(arrete_files: list[ArreteFile]) -> str:
    """
    Génère la liste consolidée des motifs pour le permis à partir des arrete_files.


    Parcourt chaque arrete_file, extrait les motifs et les ajoute à une liste groupée par arrêté.
    Retourne la liste fusionnée des motifs avec un titre pour chaque arrêté.
    """
    motifs_sections = []
    for arrete_file in arrete_files:
        if arrete_file.status:
            extracted_motifs = extract_motif(arrete_file.soup)
            if extracted_motifs:
                motifs_sections.append(
                    f'   <div data-spec="supplementary_motif_info" '
                    f'style="margin-top: var(--spacing-2);">\n'
                    f"    <h2>Considérants de l'arrêté {arrete_file.id}</h2>\n"
                    f"   </div>\n"
                )
                motifs_sections.extend(extracted_motifs)
    return "\n".join(motifs_sections)


def make_header_permis(arrete_files: list[ArreteFile]) -> str:
    """
    Génère le document HTML complet du permis consolidé avec :
    1. La liste des arrêtés sources
    2. Les visas fusionnés (sans doublons)
    3. Les considérants groupés par arrêté


    Args:
        arrete_files: Liste des arrêtés utilisés pour construire le permis


    Returns:
        HTML du header du permis
    """
    liste_arretes = make_liste_arretes(arrete_files)
    visas_permis = make_visa_permis(arrete_files)
    motifs_permis = make_motif_permis(arrete_files)

    header_html = f"""  <header data-spec="header">
{liste_arretes}
   <details style="margin-top: var(--spacing-2);">
    <summary style="cursor: pointer; font-size: 1.5rem; font-weight: bold; padding: 0.5rem 0;">
     Visas consolidés
    </summary>
    <div style="margin-left: 1rem; margin-top: 1rem;">
{visas_permis}
    </div>
   </details>
   <details style="margin-top: var(--spacing-2);">
    <summary style="cursor: pointer; font-size: 1.5rem; font-weight: bold; padding: 0.5rem 0;">
     Considérants
    </summary>
    <div style="margin-left: 1rem; margin-top: 1rem;">
{motifs_permis}
    </div>
   </details>
  </header>
"""
    return header_html
