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

from bs4 import Tag

from ocapi.utils.utils import normalize_section_title

_LOGGER = logging.getLogger(__name__)

# Exact titles (after normalisation) considered superfluous in the consolidated permit.
_SUPERFLUOUS_TITLES: frozenset[str] = frozenset(
    normalize_section_title(raw)
    for raw in (
        "MODIFICATIONS ET COMPLÉMENTS APPORTÉS AUX PRESCRIPTIONS DES ACTES ANTÉRIEURS",
        "MODALITÉS D'EXÉCUTION",
        "FRAIS",
        "SANCTIONS",
        "DIFFUSION",
        "PUBLICATION",
        "PUBLICATION ET AMPLIATION",
        "AMPLIATION",
        "TRANSMISSION À L'EXPLOITANT",
        "EXÉCUTION",
        "DÉLAIS ET VOIES DE RECOURS",
    )
)


def is_superfluous_section(section: Tag) -> bool:
    """Return True when *section*'s data-title matches one of the superfluous titles."""
    if not getattr(section, "attrs", None):
        return False
    data_title = section.get("data-title")
    if not data_title or not isinstance(data_title, str):
        return False
    return normalize_section_title(data_title) in _SUPERFLUOUS_TITLES


def filter_superfluous_sections(sections: list[Tag]) -> list[Tag]:
    """Remove superfluous sections from *sections* in-place and return those removed."""
    removed: list[Tag] = []
    for section in sections:
        if not getattr(section, "attrs", None):
            continue
        if is_superfluous_section(section):
            display = section.get("data-number", "?")
            data_title = section.get("data-title", "?")
            _LOGGER.info("Filtered superfluous article %s: %s", display, data_title)
            section.decompose()
            removed.append(section)
    return removed
