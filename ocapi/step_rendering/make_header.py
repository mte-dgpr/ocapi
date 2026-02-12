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
from bs4 import BeautifulSoup, Tag

from ocapi.types import ArreteFile


def _ordered_arretes(arrete_files: list[ArreteFile]) -> list[ArreteFile]:
    """Trie les arrêtés par date (ID YYYY-MM-DD)."""
    return sorted(arrete_files, key=lambda arrete: arrete.id)


def _extract_specs(soup: BeautifulSoup, spec: str) -> list[Tag]:
    """Extrait les blocs HTML correspondant à une spec Arrêtify."""
    return [tag for tag in soup.find_all(attrs={"data-spec": spec}) if isinstance(tag, Tag)]


def _extract_visa(soup: BeautifulSoup) -> list[str]:
    """Extrait les VisaSpec d'un arrêté."""
    return [str(tag) for tag in _extract_specs(soup, "visa")]


def _extract_motifs(soup: BeautifulSoup) -> list[str]:
    """Extrait les MotifSpec d'un arrêté."""
    return [str(tag) for tag in _extract_specs(soup, "motifs")]


def _extract_first_spec_html(soup: BeautifulSoup, spec: str) -> str:
    tags = _extract_specs(soup, spec)
    if not tags:
        return ""
    return str(tags[0])


def _extract_first_spec_text(soup: BeautifulSoup, spec: str) -> str:
    tags = _extract_specs(soup, spec)
    if not tags:
        return ""
    return str(tags[0].get_text(" ", strip=True))


def make_permit_title_spec(arrete_files: list[ArreteFile]) -> str:
    """Construit PermitTitleSpec avec le(s) code(s) AIOT."""
    aiot_values = sorted({arrete_file.aiot for arrete_file in arrete_files if arrete_file.aiot})
    aiot_label = ", ".join(aiot_values) if aiot_values else "non renseigné"
    return f"""
   <div data-spec="permit_title">
    <h1>Permis d'Exploitation Consolidé</h1>
    <p><strong>Code AIOT ICPE :</strong> {aiot_label}</p>
   </div>
"""


def make_permit_sources(arrete_files: list[ArreteFile]) -> str:
    """Construit PermitSources trié chronologiquement avec ArreteTitleSpec."""
    items: list[str] = []
    for arrete_file in _ordered_arretes(arrete_files):
        arrete_title_html = _extract_first_spec_html(arrete_file.soup, "arrete_title")
        arrete_title_text = _extract_first_spec_text(arrete_file.soup, "arrete_title")
        source_title = arrete_title_html or f"<div>{arrete_file.filename}</div>"
        status = "active" if arrete_file.status else "abroge"
        label = arrete_title_text or arrete_file.filename
        items.append(
            f"""
    <li data-spec="permit_source" data-date="{arrete_file.id}" data-status="{status}">
     <p><strong>Date arrêté :</strong> {arrete_file.id}</p>
     <div data-spec="permit_source_title" aria-label="{label}">
      {source_title}
     </div>
    </li>
"""
        )

    return f"""
   <section data-spec="permit_sources" style="margin-top: var(--spacing-2);">
    <h2>Arrêtés sources</h2>
    <ul style="list-style: disc; margin-left: 2rem;">
{''.join(items)}
    </ul>
   </section>
"""


def make_permit_visa(arrete_files: list[ArreteFile]) -> str:
    """Construit PermitVisa par union ordonnée (set puis liste)."""
    seen: set[str] = set()
    ordered_unique_visas: list[str] = []
    for arrete_file in _ordered_arretes(arrete_files):
        for visa in _extract_visa(arrete_file.soup):
            if visa not in seen:
                seen.add(visa)
                ordered_unique_visas.append(visa)
    visas_html = "\n".join(ordered_unique_visas)
    return f"""
   <section data-spec="permit_visa" style="margin-top: var(--spacing-2);">
    <h2>Visas consolidés</h2>
    <div style="margin-left: 1rem; margin-top: 1rem;">
{visas_html}
    </div>
   </section>
"""


def make_permit_motif(arrete_files: list[ArreteFile]) -> str:
    """Construit PermitMotif en concaténant les MotifSpec par arrêté (ordre chrono)."""
    motifs_sections: list[str] = []
    for arrete_file in _ordered_arretes(arrete_files):
        extracted_motifs = _extract_motifs(arrete_file.soup)
        if not extracted_motifs:
            continue
        title = _extract_first_spec_text(arrete_file.soup, "arrete_title") or arrete_file.filename
        motifs_html = "\n".join(extracted_motifs)
        motifs_sections.append(
            f"""
    <section data-spec="permit_motif_group" data-date="{arrete_file.id}">
     <h3>Arrêté {arrete_file.id}</h3>
     <p>{title}</p>
     {motifs_html}
    </section>
"""
        )
    return f"""
   <section data-spec="permit_motif" style="margin-top: var(--spacing-2);">
    <h2>Considérants</h2>
{''.join(motifs_sections)}
   </section>
"""


def make_header_permis(arrete_files: list[ArreteFile]) -> str:
    """Construit le header consolidé au format de sortie stable."""
    permit_title = make_permit_title_spec(arrete_files)
    permit_sources = make_permit_sources(arrete_files)
    permit_visa = make_permit_visa(arrete_files)
    permit_motif = make_permit_motif(arrete_files)

    header_html = f"""  <header data-spec="header">
{permit_title}
{permit_sources}
{permit_visa}
{permit_motif}
  </header>
"""
    return header_html
