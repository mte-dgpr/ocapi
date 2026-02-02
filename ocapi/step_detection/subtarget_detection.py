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
"""
Détection et parsing de sub-targets simples dans les opérations.

Gère les cas simples par regex, délègue les cas complexes au LLM.

Exemples de cas simples détectés :
- "le tableau"
- "première phrase", "deuxième phrase", "dernière phrase"
- "l'alinéa", "premier alinéa", "deuxième alinéa"
- "le paragraphe", "premier paragraphe"
- "ligne du tableau", "première ligne du tableau"
- "colonne du tableau", "deuxième colonne"
"""

import re

from bs4 import BeautifulSoup

from ocapi.types import SubTarget, SubTargetType

# Patterns pour les ordinaux (masculin/féminin)
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
    r"\bdernier\b": 0,
    r"\bdernier[eè]\b": 0,
}

# Patterns pour les éléments cibles
ELEMENTS = {
    r"\bphrase\b": SubTargetType.PHRASE,
    r"\balin[ée]a\b": SubTargetType.ALINEA,
    r"\bligne\s+(?:du\s+)?tableau\b": SubTargetType.LIGNE_TABLEAU,
    r"\bcolonne(?:\s+du\s+tableau)?\b": SubTargetType.COLONNE_TABLEAU,
}

# Patterns simples sans ordinal
SIMPLE_PATTERNS = [(r"\ble\s+tableau\b", SubTargetType.TABLEAU, None)]


def _ensure_subtarget_type(value: SubTargetType | str | None) -> SubTargetType:
    """
    Convertit une valeur potentiellement sérialisée en SubTargetType.
    """
    if isinstance(value, SubTargetType):
        return value
    try:
        return SubTargetType(str(value))
    except Exception:
        return SubTargetType.COMPLEX


def parse_subtarget(text: str) -> SubTarget:
    """
    Détecte le type de sub-target à partir du texte.

    Args:
        text: Texte décrivant le sub-target (ex: "première phrase")

    Returns:
        SubTarget: Le sub-target parsé, ou COMPLEX si non reconnu
    """
    if not text or text.strip() == "":
        return SubTarget(type=SubTargetType.FULL_SECTION, description=text)
    
    text_lower = text.lower().strip()
    
    # Cas spécial : "tout" ou variations
    if re.match(r'contenu entier', text_lower) or text_lower == "all":
        return SubTarget(type=SubTargetType.FULL_SECTION, description=text)
    
    # Tester les patterns simples d'abord
    for pattern, target_type, position in SIMPLE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return SubTarget(type=target_type, position=position, description=text)
    
    # Tester les combinaisons ordinal + élément
    for ordinal_pattern, position in ORDINAUX.items():
        for element_pattern, target_type in ELEMENTS.items():
            # Construire pattern combiné : "premier alinéa", "deuxième phrase", etc.
            combined_pattern = f"{ordinal_pattern}\\s+{element_pattern}"
            if re.search(combined_pattern, text_lower, re.IGNORECASE):
                return SubTarget(type=target_type, position=position, description=text)
    
    # Si aucun pattern ne correspond, marquer comme complexe
    return SubTarget(type=SubTargetType.COMPLEX, description=text)


def is_simple_subtarget(parsed: SubTarget) -> bool:
    """
    Vérifie si le sub-target peut être traité sans LLM.

    Args:
        text: Texte du sub-target

    Returns:
        bool: True si détectable par regex, False si nécessite LLM
    """
    return parsed.type != SubTargetType.COMPLEX


def replace_subtarget(soup: BeautifulSoup, subtarget: SubTarget, operand: str) -> BeautifulSoup:
    """
    Remplace l'élément ciblé par le nouveau contenu (operand) dans le soup.

    Args:
        soup: BeautifulSoup de la section
        subtarget: SubTarget parsé indiquant quoi remplacer
        operand: Nouveau contenu HTML à insérer

    Returns:
        BeautifulSoup: Le soup modifié avec le remplacement effectué
    """
    from copy import copy

    operand_soup = BeautifulSoup(operand, "html.parser")
    # Prélever un fragment « propre » (évite d'insérer <html><body> dans le DOM)
    operand_children = [
        c for c in operand_soup.contents if not (isinstance(c, str) and c.strip() == "")
    ]
    operand_fragment = operand_children[0] if len(operand_children) == 1 else operand_soup
    # Copier le fragment pour éviter les problèmes de mutation
    operand_fragment = copy(operand_fragment)
    subtarget_type = _ensure_subtarget_type(subtarget.type)

    if subtarget_type == SubTargetType.FULL_SECTION:
        # Remplacer tout le contenu sauf le titre (h1, h2, h3, etc.)
        title = soup.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        soup.clear()
        if title:
            soup.append(title)
        # Append all children from operand_fragment
        if hasattr(operand_fragment, "children"):
            children = list(operand_fragment.children)
        else:
            children = [operand_fragment]
        for child in children:
            soup.append(child)
        return soup

    elif subtarget_type == SubTargetType.TABLEAU:
        table = soup.find("table")
        if table:
            table.replace_with(operand_fragment)
        return soup

    elif subtarget_type == SubTargetType.PHRASE:
        # Trouver tous les nœuds texte et reconstruire les phrases
        full_text = soup.get_text()
        phrases = [p.strip() for p in full_text.split(".") if p.strip()]

        # Déterminer quelle phrase remplacer
        target_phrase = None
        if subtarget.position is None and phrases:
            target_phrase = phrases[-1]
        elif subtarget.position and 1 <= subtarget.position <= len(phrases):
            target_phrase = phrases[subtarget.position - 1]

        if target_phrase:
            # Chercher le texte de la phrase dans le soup et le remplacer
            for text_node in soup.find_all(string=True):
                if target_phrase in text_node:
                    # Remplacer uniquement cette occurrence
                    new_text = text_node.replace(target_phrase, operand)
                    text_node.replace_with(new_text)
                    break
        return soup

    elif subtarget_type == SubTargetType.ALINEA:
        from copy import copy

        alineas = soup.find_all("div", class_="arretify-alinea")
        target_alinea = None

        if subtarget.position is None and alineas:
            target_alinea = alineas[-1]
        else:
            for alinea in alineas:
                if alinea.get("data-number") == str(subtarget.position):
                    target_alinea = alinea
                    break

        if target_alinea:
            # Créer un nouveau div avec le contenu de l'operand
            new_div = soup.new_tag("div")
            new_div["class"] = "arretify-alinea"
            data_num = target_alinea.get("data-number")
            new_div["data-number"] = str(data_num) if data_num else ""
            new_div.string = operand if isinstance(operand, str) else str(copy(operand_fragment))
            target_alinea.replace_with(new_div)
        return soup

    elif subtarget_type == SubTargetType.LIGNE_TABLEAU:
        table = soup.find("table")
        if table:
            lignes = table.find_all("tr")
            target_ligne = None

            if subtarget.position is None and lignes:
                target_ligne = lignes[-1]
            elif subtarget.position and 1 <= subtarget.position <= len(lignes):
                target_ligne = lignes[subtarget.position - 1]

            if target_ligne:
                target_ligne.replace_with(operand_fragment)
        return soup

    elif subtarget_type == SubTargetType.COLONNE_TABLEAU:
        table = soup.find("table")
        if table:
            # Remplacer toutes les cellules de la colonne
            rows = table.find_all("tr")
            for row in rows:
                colonnes = row.find_all(["td", "th"])
                target_col = None

                if subtarget.position is None and colonnes:
                    target_col = colonnes[-1]
                elif subtarget.position and 1 <= subtarget.position <= len(colonnes):
                    target_col = colonnes[subtarget.position - 1]

                if target_col:
                    replacement = (
                        operand_fragment.find(["td", "th"])
                        if hasattr(operand_fragment, "find")
                        else None
                    )
                    target_col.replace_with(replacement or operand_fragment)
        return soup

    return soup


# Note: Les cas complexes nécessitant un LLM ne sont pas gérés ici.
