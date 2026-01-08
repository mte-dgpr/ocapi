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
    r'\bdernier\b': 0,
    r'\bdernier[eè]\b': 0
}

# Patterns pour les éléments cibles
ELEMENTS = {
    r'\bphrase\b': SubTargetType.PHRASE,
    r'\balin[ée]a\b': SubTargetType.ALINEA,
    r'\bligne\s+(?:du\s+)?tableau\b': SubTargetType.LIGNE_TABLEAU,
    r'\bcolonne(?:\s+du\s+tableau)?\b': SubTargetType.COLONNE_TABLEAU,
}

# Patterns simples sans ordinal
SIMPLE_PATTERNS = [
    (r'\ble\s+tableau\b', SubTargetType.TABLEAU, None)
]


def parse_subtarget(text: str) -> SubTarget:
    # TODO: match avec le nouveau prompt
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


def is_simple_subtarget(parsed:SubTarget) -> bool:
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
    operand_soup = BeautifulSoup(operand, 'html.parser')
    
    if subtarget.type == "FULL_SECTION":
        # Remplacer tout le contenu sauf le titre (h1, h2, h3, etc.)
        title = soup.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        soup.clear()
        if title:
            soup.append(title)
        # Append all children from operand_soup
        for child in list(operand_soup.children):
            soup.append(child)
        return soup
    
    elif subtarget.type == "TABLEAU":
        table = soup.find('table')
        if table:
            table.replace_with(operand_soup)
        return soup
    
    elif subtarget.type == "PHRASE":
        # Trouver tous les nœuds texte et reconstruire les phrases
        full_text = soup.get_text()
        phrases = [p.strip() for p in full_text.split('.') if p.strip()]
        
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
    
    elif subtarget.type == "ALINEA":
        alineas = soup.find_all('div', class_='arretify-alinea')
        target_alinea = None
        
        if subtarget.position is None and alineas:
            target_alinea = alineas[-1]
        else:
            for alinea in alineas:
                if alinea.get('data-number') == str(subtarget.position):
                    target_alinea = alinea
                    break
        
        if target_alinea:
            target_alinea.replace_with(operand_soup)
        return soup
    
    elif subtarget.type == SubTargetType.LIGNE_TABLEAU:
        table = soup.find('table')
        if table:
            lignes = table.find_all('tr')
            target_ligne = None
            
            if subtarget.position is None and lignes:
                target_ligne = lignes[-1]
            elif subtarget.position and 1 <= subtarget.position <= len(lignes):
                target_ligne = lignes[subtarget.position - 1]
            
            if target_ligne:
                target_ligne.replace_with(operand_soup)
        return soup
    
    elif subtarget.type == SubTargetType.COLONNE_TABLEAU:
        table = soup.find('table')
        if table:
            # Remplacer toutes les cellules de la colonne
            rows = table.find_all('tr')
            for row in rows:
                colonnes = row.find_all(['td', 'th'])
                target_col = None
                
                if subtarget.position is None and colonnes:
                    target_col = colonnes[-1]
                elif subtarget.position and 1 <= subtarget.position <= len(colonnes):
                    target_col = colonnes[subtarget.position - 1]
                
                if target_col:
                    target_col.replace_with(operand_soup.find(['td', 'th']) or operand_soup)
        return soup
    
    return soup


# Note: Les cas complexes nécessitant un LLM ne sont pas gérés ici.