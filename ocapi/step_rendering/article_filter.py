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
import re
import unicodedata

from bs4 import Tag

_LOGGER = logging.getLogger(__name__)

# Exact titles (after normalisation) considered superfluous in the consolidated permit.
_SUPERFLUOUS_TITLES: frozenset[str] = frozenset(
    _normalize
    for _raw in (
        "MODIFICATIONS ET COMPLÉMENTS APPORTÉS AUX PRESCRIPTIONS DES ACTES ANTÉRIEURS",
        "MODALITÉS D'EXÉCUTION",
        "FRAIS",
        "SANCTIONS",
        "DIFFUSION",
        "TRANSMISSION À L'EXPLOITANT",
        "EXÉCUTION",
        "DÉLAIS ET VOIES DE RECOURS",
    )
    if (
        _normalize := re.sub(r"\s+", " ", unicodedata.normalize("NFD", _raw))
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )
)


def _strip_accents(text: str) -> str:
    """Remove diacritical marks (é→e, à→a, …)."""
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")


def _normalize_section_title(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(text)).strip().lower()


def is_superfluous_section(section: Tag) -> bool:
    """Return True when *section*'s title matches one of the superfluous titles."""
    title_el = section.find(attrs={"data-spec": "section_title"})
    if title_el is None:
        return False
    normalized = _normalize_section_title(title_el.get_text())
    return normalized in _SUPERFLUOUS_TITLES


def filter_superfluous_sections(sections: list[Tag]) -> list[Tag]:
    """Remove superfluous sections from *sections* in-place and return those removed."""
    removed: list[Tag] = []
    for section in sections:
        if is_superfluous_section(section):
            display = section.get("data-number", "?")
            title_el = section.find(attrs={"data-spec": "section_title"})
            title_text = title_el.get_text(strip=True) if title_el else "?"
            _LOGGER.info("Filtered superfluous article %s: %s", display, title_text)
            section.decompose()
            removed.append(section)
    return removed
