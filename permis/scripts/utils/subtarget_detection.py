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
from typing import Optional, Dict, Any
from enum import Enum
from permis.scripts.constants import FULL_SECTION


class SubTargetType(Enum):
    """Types de sub-targets détectables."""
    FULL_SECTION = "FULL_SECTION"
    TABLEAU = "TABLEAU"
    PHRASE = "PHRASE"
    ALINEA = "ALINEA"
    PARAGRAPHE = "PARAGRAPHE"
    LIGNE_TABLEAU = "LIGNE_TABLEAU"
    COLONNE_TABLEAU = "COLONNE_TABLEAU"
    COMPLEX = "COMPLEX"  # Nécessite LLM


class SubTarget:
    """Représente un sub-target parsé."""
    def __init__(self, type: SubTargetType, position: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        self.type = type
        self.position = position  # None = dernière, 1 = première, 2 = deuxième, etc.

    def __repr__(self):
        return f"SubTarget({self.type.value}, pos={self.position}, details={self.details})"


# Patterns pour les ordinaux (masculin/féminin)
ORDINAUX = {
    r'\bpremier\b': 1,
    r'\bpremi[eè]re\b': 1,
    r'\b1er\b': 1,
    r'\b1[eè]re\b': 1,
    r'\bdeuxi[eè]me\b': 2,
    r'\b2[eè]me\b': 2,
    r'\btroisi[eè]me\b': 3,
    r'\b3[eè]me\b': 3,
    r'\bquatri[eè]me\b': 4,
    r'\b4[eè]me\b': 4,
    r'\bcinqui[eè]me\b': 5,
    r'\b5[eè]me\b': 5,
    r'\bsixi[eè]me\b': 6,
    r'\b6[eè]me\b': 6,
    r'\bsepti[eè]me\b': 7,
    r'\b7[eè]me\b': 7,
    r'\bhuiti[eè]me\b': 8,
    r'\b8[eè]me\b': 8,
    r'\bneuvi[eè]me\b': 9,
    r'\b9[eè]me\b': 9,
    r'\bdixi[eè]me\b': 10,
    r'\b10[eè]me\b': 10,
    r'\bdernier\b': None,
    r'\bdernier[eè]\b': None
}

# Patterns pour les éléments cibles
ELEMENTS = {
    r'\bphrase\b': SubTargetType.PHRASE,
    r'\balin[ée]a\b': SubTargetType.ALINEA,
    r'\bparagraphe\b': SubTargetType.PARAGRAPHE,
    r'\bligne\s+(?:du\s+)?tableau\b': SubTargetType.LIGNE_TABLEAU,
    r'\bcolonne(?:\s+du\s+tableau)?\b': SubTargetType.COLONNE_TABLEAU,
}

# Patterns simples sans ordinal
SIMPLE_PATTERNS = [
    (r'\ble\s+tableau\b', SubTargetType.TABLEAU, None)
]


def detect_subtarget(text: str) -> SubTarget:
    """
    Détecte le type de sub-target à partir du texte.
    
    Args:
        text: Texte décrivant le sub-target (ex: "première phrase")
        
    Returns:
        SubTarget: Le sub-target parsé, ou COMPLEX si non reconnu
    """
    if not text or text.strip() == "":
        return SubTarget(SubTargetType.FULL_SECTION)
    
    text_lower = text.lower().strip()
    
    # Cas spécial : "tout" ou variations
    if re.match(r'contenu entier', text_lower):
        return SubTarget(SubTargetType.FULL_SECTION)
    
    # Tester les patterns simples d'abord
    for pattern, target_type, position in SIMPLE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return SubTarget(target_type, position)
    
    # Tester les combinaisons ordinal + élément
    for ordinal_pattern, position in ORDINAUX.items():
        for element_pattern, target_type in ELEMENTS.items():
            # Construire pattern combiné : "premier alinéa", "deuxième phrase", etc.
            combined_pattern = f"{ordinal_pattern}\\s+{element_pattern}"
            if re.search(combined_pattern, text_lower, re.IGNORECASE):
                return SubTarget(target_type, position)
    
    # Si aucun pattern ne correspond, marquer comme complexe
    return SubTarget(SubTargetType.COMPLEX, details={"original_text": text})


def is_simple_subtarget(text: str) -> bool:
    """
    Vérifie si le sub-target peut être traité sans LLM.
    
    Args:
        text: Texte du sub-target
        
    Returns:
        bool: True si détectable par regex, False si nécessite LLM
    """
    result = detect_subtarget(text)
    return result.type != SubTargetType.COMPLEX



