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
"""
Detection and parsing of simple sub-targets in operations.

Handles simple cases via regex, delegates complex cases to the LLM.

Examples of simple cases detected:
- "le tableau"
- "première phrase", "deuxième phrase", "dernière phrase"
- "l'alinéa", "premier alinéa", "deuxième alinéa"
- "le paragraphe", "premier paragraphe"
- "ligne du tableau", "première ligne du tableau"
- "colonne du tableau", "deuxième colonne"
"""
import re
from copy import copy
from typing import TypeVar

from bs4 import BeautifulSoup, Tag

from ocapi.config import FullSectionName
from ocapi.exceptions import SubtargetNotFoundError
from ocapi.types import SubTarget, SubTargetType

_FULL_SECTION_NAMES_LOWER: frozenset[str] = frozenset(
    name.value.lower() for name in FullSectionName
)

# Ordinal patterns (masculine/feminine)
ORDINAUX = {
    r"\bpremier\b": 1,
    r"\bpremi[eè]re\b": 1,
    r"\b1er\b": 1,
    r"\b1[eè]re\b": 1,
    r"\bdeuxi[eè]me\b": 2,
    r"\b2[eè]me\b": 2,
    r"\btroisi[eè]me\b": 3,
    r"\b3[eè]me\b": 3,
    r"\bquatri[eè]me\b": 4,
    r"\b4[eè]me\b": 4,
    r"\bcinqui[eè]me\b": 5,
    r"\b5[eè]me\b": 5,
    r"\bsixi[eè]me\b": 6,
    r"\b6[eè]me\b": 6,
    r"\bsepti[eè]me\b": 7,
    r"\b7[eè]me\b": 7,
    r"\bhuiti[eè]me\b": 8,
    r"\b8[eè]me\b": 8,
    r"\bneuvi[eè]me\b": 9,
    r"\b9[eè]me\b": 9,
    r"\bdixi[eè]me\b": 10,
    r"\b10[eè]me\b": 10,
    r"\bdernier\b": -1,
    r"\bdernier[eè]\b": -1,
}

# Target element patterns
ELEMENTS = {
    r"\bphrase\b": SubTargetType.PHRASE,
    r"\balin[ée]a\b": SubTargetType.ALINEA,
    r"\bligne\s+(?:du\s+)?tableau\b": SubTargetType.LIGNE_TABLEAU,
    r"\bcolonne(?:\s+du\s+tableau)?\b": SubTargetType.COLONNE_TABLEAU,
}

# Simple patterns without ordinal
SIMPLE_PATTERNS = [(r"\ble\s+tableau\b", SubTargetType.TABLEAU, None)]


def _ensure_subtarget_type(value: SubTargetType | str | None) -> SubTargetType:
    """Convert a potentially serialised value to a SubTargetType."""
    if isinstance(value, SubTargetType):
        return value
    try:
        return SubTargetType(str(value))
    except Exception:
        return SubTargetType.COMPLEX


def parse_subtarget(text: str) -> SubTarget:
    """Convert a sub-target text detected by the LLM into a SubTarget object.

    Handles simple cases via regex; returns COMPLEX otherwise.

    Parameters
    ----------
    text : str
        Raw sub-target description string from the LLM.

    Returns
    -------
    SubTarget
        Parsed sub-target with type, optional position and original description.
    """
    if not text or text.strip() == "":
        return SubTarget(type=SubTargetType.FULL_SECTION, description=text)

    text_lower = text.lower().strip()

    if text_lower in _FULL_SECTION_NAMES_LOWER:
        return SubTarget(type=SubTargetType.FULL_SECTION, description=text)

    # Try simple patterns first
    for pattern, target_type, position in SIMPLE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return SubTarget(type=target_type, position=position, description=text)

    # Try ordinal + element combinations
    for ordinal_pattern, position in ORDINAUX.items():
        for element_pattern, target_type in ELEMENTS.items():
            combined_pattern = f"{ordinal_pattern}\\s+{element_pattern}"
            if re.search(combined_pattern, text_lower, re.IGNORECASE):
                return SubTarget(type=target_type, position=position, description=text)

    # No pattern matched: mark as complex
    return SubTarget(type=SubTargetType.COMPLEX, description=text)


def is_simple_subtarget(parsed: SubTarget) -> bool:
    """Return True if the sub-target can be resolved without the LLM.

    Parameters
    ----------
    parsed : SubTarget
        Parsed sub-target object.

    Returns
    -------
    bool
        True if the sub-target type is not COMPLEX.
    """
    return parsed.type != SubTargetType.COMPLEX


T = TypeVar("T")


def _find_target_element(
    elements: list[T],
    position: int | None,
    description: str | None,
    element_name: str,
) -> T:
    """Select the target element according to the given position.

    Works with any element type (Tag, str for sentences, etc.).

    Parameters
    ----------
    elements : list[T]
        Available elements to pick from.
    position : int | None
        1-based position, -1 for last, None for unique.
    description : str | None
        Original sub-target description, used in error messages.
    element_name : str
        Human-readable name for the element type, used in error messages.

    Returns
    -------
    T
        The selected element.

    Raises
    ------
    SubtargetNotFoundError
        If no elements found, position is out of range, or ambiguous (None with multiple elements).
    """
    if not elements:
        raise SubtargetNotFoundError(f"No {element_name} found for '{description}'.")

    if position == -1:
        return elements[-1]
    elif position is None:
        if len(elements) == 1:
            return elements[0]
        else:
            raise SubtargetNotFoundError(
                f"Ambiguous: '{description}' but {len(elements)} {element_name} found."
            )
    elif position and 1 <= position <= len(elements):
        return elements[position - 1]
    else:
        raise SubtargetNotFoundError(
            f"Invalid position {position} for '{description}': "
            f"{len(elements)} {element_name} available."
        )


def replace_subtarget(soup: BeautifulSoup, subtarget: SubTarget, operand: str) -> BeautifulSoup:
    """Replace the targeted element with new content (operand) in the soup.

    Raises an error if the sub-target is ambiguous or not found.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed HTML of the article section to modify.
    subtarget : SubTarget
        Parsed sub-target describing which element to replace.
    operand : str
        HTML string of the new content to insert.

    Returns
    -------
    BeautifulSoup
        Modified soup (in-place modification).
    """
    operand_soup = BeautifulSoup(operand, "html.parser")
    # Extract a clean fragment (avoids inserting <html><body> into the DOM)
    operand_children = [
        c for c in operand_soup.contents if not (isinstance(c, str) and c.strip() == "")
    ]
    operand_fragment = operand_children[0] if len(operand_children) == 1 else operand_soup
    # Copy the fragment to avoid mutation issues
    operand_fragment = copy(operand_fragment)
    subtarget_type = _ensure_subtarget_type(subtarget.type)

    if subtarget_type == SubTargetType.FULL_SECTION:
        soup.clear()
        if hasattr(operand_fragment, "children"):
            children = list(operand_fragment.children)
        else:
            children = [operand_fragment]
        for child in children:
            soup.append(child)
        return soup

    elif subtarget_type == SubTargetType.TABLEAU:
        tables = soup.find_all("table")
        target_table = _find_target_element(
            tables, subtarget.position, subtarget.description, "tables"
        )
        if target_table:
            target_table.replace_with(operand_fragment)
        return soup

    elif subtarget_type == SubTargetType.PHRASE:
        full_text = soup.get_text()
        phrases = [p.strip() for p in full_text.split(".") if p.strip()]

        target_phrase = _find_target_element(
            phrases, subtarget.position, subtarget.description, "sentences"
        )

        for text_node in soup.find_all(string=True):
            if target_phrase in text_node:
                new_text = text_node.replace(target_phrase, operand)
                text_node.replace_with(new_text)
                break
        return soup

    elif subtarget_type == SubTargetType.ALINEA:
        alineas = soup.find_all("div", class_="arretify-alinea")
        target_alinea = _find_target_element(
            alineas, subtarget.position, subtarget.description, "alineas"
        )

        if target_alinea:
            new_div = soup.new_tag("div")
            new_div["class"] = "arretify-alinea"
            data_num = target_alinea.get("data-number")
            new_div["data-number"] = str(data_num) if data_num else ""
            new_div.string = operand if isinstance(operand, str) else str(copy(operand_fragment))
            target_alinea.replace_with(new_div)
        return soup

    elif subtarget_type == SubTargetType.LIGNE_TABLEAU:
        table = soup.find("table")
        if isinstance(table, Tag):
            rows = table.find_all("tr")
            target_row = _find_target_element(
                rows, subtarget.position, subtarget.description, "rows"
            )
            if target_row:
                target_row.replace_with(operand_fragment)
        return soup

    elif subtarget_type == SubTargetType.COLONNE_TABLEAU:
        table = soup.find("table")
        if isinstance(table, Tag):
            rows = table.find_all("tr")

            # For None position, check uniqueness on the first row
            if subtarget.position is None and rows:
                first_row_cols = rows[0].find_all(["td", "th"])
                if len(first_row_cols) != 1:
                    raise SubtargetNotFoundError(
                        f"Ambiguous: '{subtarget.description}' but "
                        f"{len(first_row_cols)} columns found."
                    )

            for row in rows:
                cols = row.find_all(["td", "th"])
                target_col = _find_target_element(
                    cols, subtarget.position, subtarget.description, "columns"
                )

                if target_col:
                    replacement = (
                        operand_fragment.find(["td", "th"])
                        if hasattr(operand_fragment, "find")
                        else None
                    )
                    target_col.replace_with(replacement or operand_fragment)
        return soup
    return soup


def insert_content_after_subtarget(
    soup: BeautifulSoup, subtarget: SubTarget, operand: str
) -> BeautifulSoup:
    """Insert ``operand`` HTML immediately *after* the element matched by ``subtarget``.

    Used for ADD operations with a simple sub-target (not ``FULL_SECTION`` / ``COMPLEX``).

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed HTML of the article section to modify.
    subtarget : SubTarget
        Parsed sub-target describing the anchor after which to insert.
    operand : str
        HTML fragment to insert.

    Returns
    -------
    BeautifulSoup
        Modified soup (in-place).

    Raises
    ------
    ValueError
        If the sub-target is ambiguous or not found (same as :func:`replace_subtarget`).
    """
    operand_soup = BeautifulSoup(operand, "html.parser")
    operand_children = [
        c for c in operand_soup.contents if not (isinstance(c, str) and c.strip() == "")
    ]
    operand_fragment = operand_children[0] if len(operand_children) == 1 else operand_soup
    operand_fragment = copy(operand_fragment)
    subtarget_type = _ensure_subtarget_type(subtarget.type)

    if subtarget_type == SubTargetType.FULL_SECTION:
        raise ValueError("FULL_SECTION ADD must be handled in apply_add, not insert_after.")
    if subtarget_type == SubTargetType.COMPLEX:
        raise ValueError("COMPLEX sub-target requires the LLM path.")

    if subtarget_type == SubTargetType.TABLEAU:
        tables = soup.find_all("table")
        target_table = _find_target_element(
            tables, subtarget.position, subtarget.description, "tables"
        )
        if target_table:
            target_table.insert_after(operand_fragment)
        return soup

    if subtarget_type == SubTargetType.PHRASE:
        full_text = soup.get_text()
        phrases = [p.strip() for p in full_text.split(".") if p.strip()]
        target_phrase = _find_target_element(
            phrases, subtarget.position, subtarget.description, "sentences"
        )
        for text_node in soup.find_all(string=True):
            if target_phrase in text_node:
                parent = text_node.parent
                if parent:
                    parent.insert_after(operand_fragment)
                break
        return soup

    if subtarget_type == SubTargetType.ALINEA:
        alineas = soup.find_all("div", class_="arretify-alinea")
        target_alinea = _find_target_element(
            alineas, subtarget.position, subtarget.description, "alineas"
        )
        if target_alinea:
            target_alinea.insert_after(operand_fragment)
        return soup

    if subtarget_type == SubTargetType.LIGNE_TABLEAU:
        table = soup.find("table")
        if isinstance(table, Tag):
            rows = table.find_all("tr")
            target_row = _find_target_element(
                rows, subtarget.position, subtarget.description, "rows"
            )
            if target_row:
                target_row.insert_after(operand_fragment)
        return soup

    if subtarget_type == SubTargetType.COLONNE_TABLEAU:
        table = soup.find("table")
        if isinstance(table, Tag):
            rows = table.find_all("tr")
            if subtarget.position is None and rows:
                first_row_cols = rows[0].find_all(["td", "th"])
                if len(first_row_cols) != 1:
                    raise ValueError(
                        f"Ambiguous: '{subtarget.description}' but "
                        f"{len(first_row_cols)} columns found."
                    )
            for row in rows:
                cols = row.find_all(["td", "th"])
                target_col = _find_target_element(
                    cols, subtarget.position, subtarget.description, "columns"
                )
                if target_col:
                    target_col.insert_after(operand_fragment)
                    break
        return soup

    return soup
