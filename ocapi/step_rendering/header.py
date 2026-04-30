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
from bs4 import BeautifulSoup

from ocapi.types import ArreteFile
from ocapi.utils.arretify_utils import (
    extract_first_spec_html,
    extract_first_spec_text,
    extract_specs,
)


def _ordered_arretes(arrete_files: list[ArreteFile]) -> list[ArreteFile]:
    """Sort arrêtés by date (YYYY-MM-DD ID)."""
    return sorted(arrete_files, key=lambda arrete: arrete.id)


def _extract_visa(soup: BeautifulSoup) -> list[str]:
    """Extract VisaSpec entries from an arrêté."""
    return [str(tag) for tag in extract_specs(soup, "visa")]


def _extract_motifs(soup: BeautifulSoup) -> list[str]:
    """Extract MotifSpec entries from an arrêté."""
    return [str(tag) for tag in extract_specs(soup, "motifs")]


def make_permit_title_spec(arrete_files: list[ArreteFile]) -> str:
    """Build PermitTitleSpec with a unique AIOT code."""
    aiot_values = sorted({arrete_file.aiot for arrete_file in arrete_files if arrete_file.aiot})

    if len(aiot_values) > 1:
        raise ValueError(f"Found arretes associated with multiple AIOT: {aiot_values}")

    aiot_label = aiot_values[0] if aiot_values else "non renseigné"
    return f"""
   <div data-spec="permit_title">
    <h1>Permis d'Exploitation Consolidé</h1>
    <p><strong>Code AIOT ICPE :</strong> {aiot_label}</p>
   </div>
"""


def make_permit_sources(arrete_files: list[ArreteFile]) -> str:
    """Build PermitSources sorted chronologically with ArreteTitleSpec."""
    items: list[str] = []
    for arrete_file in _ordered_arretes(arrete_files):
        arrete_title_html = extract_first_spec_html(arrete_file.soup, "arrete_title")
        arrete_title_text = extract_first_spec_text(arrete_file.soup, "arrete_title")
        if arrete_title_html:
            title_soup = BeautifulSoup(arrete_title_html, "html.parser")
            for h1_tag in title_soup.find_all("h1"):
                h1_tag.name = "p"
            source_title = str(title_soup)
        else:
            source_title = f"<div>{arrete_file.filename}</div>"
        status = "active" if arrete_file.status else "abroge"
        label = arrete_title_text or arrete_file.filename
        abroge_mention = " (ABROGE)" if not arrete_file.status else ""
        items.append(
            f"""
    <li data-spec="permit_source" data-date="{arrete_file.id}" data-status="{status}">
     <p><strong>Date arrêté :</strong> {arrete_file.id}{abroge_mention}</p>
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
    """Build PermitVisa by grouping visas per arrêté in chronological order."""
    visa_sections: list[str] = []
    for arrete_file in _ordered_arretes(arrete_files):
        extracted_visas = _extract_visa(arrete_file.soup)
        if not extracted_visas:
            continue
        title = extract_first_spec_text(arrete_file.soup, "arrete_title") or arrete_file.filename
        visas_html = "\n".join(extracted_visas)
        visa_sections.append(
            f"""
    <section data-spec="permit_visa_group" data-date="{arrete_file.id}">
     <h3>Visas de l'arrêté {arrete_file.id}</h3>
     <p>{title}</p>
     {visas_html}
    </section>
"""
        )
    return f"""
   <section data-spec="permit_visa" style="margin-top: var(--spacing-2);">
    <details>
     <summary><h2 style="display: inline;">Visas consolidés</h2></summary>
{''.join(visa_sections)}
    </details>
   </section>
"""


def make_permit_motif(arrete_files: list[ArreteFile]) -> str:
    """Build PermitMotif by concatenating MotifSpec entries per arrêté (chronological order)."""
    motifs_sections: list[str] = []
    for arrete_file in _ordered_arretes(arrete_files):
        extracted_motifs = _extract_motifs(arrete_file.soup)
        if not extracted_motifs:
            continue
        title = extract_first_spec_text(arrete_file.soup, "arrete_title") or arrete_file.filename
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
    <details>
     <summary><h2 style="display: inline;">Considérants</h2></summary>
{''.join(motifs_sections)}
    </details>
   </section>
"""


def make_permit_header(arrete_files: list[ArreteFile]) -> str:
    """Build the consolidated header in the stable output format."""
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
