"""
Ce fichier lit data/operations_brutes/*.json
But :
- normaliser le format des opérations (type, cible, ordre, source_file, block_index)
- pour chaque opération contenant new_content_ref (start/end markers) :
    -> appeler remplacer_new_content pour remplir new_content_html
    -> supprimer champs temporaires
- marquer op["status"]="a_revoir" si extraction échoue (contexte ajouté)
- écrire résultats finaux dans data/operations_nettoyees/<source>.clean.json

à lancer comme un module "python -m permis.2_detection.nettoyer_ops  " je comprends pas pk mais bon
"""

# TODO corriger l'article source lors de l'extraction de contenu.
# TODO plus tard: remplacer les "a_revoir" tq des que ya autre chose qu'un abroge et pas de texte, a revoir
# TODO plus tard :des qu'un texte mais respecte pas les marker, a revoir.
# TODO plus tard: modification des operations. (modif des titres etc)


import re
from typing import Optional, Dict

from bs4 import BeautifulSoup
import html

ImageMap = Dict[str, str]  # mapping from placeholder src to real src

def _find_marker(haystack: str, marker: str) -> int:
    """ """
    if not marker:
        return -1
    i = haystack.find(marker)
    if i != -1:
        return i
    n = html.unescape(marker)
    pattern = re.sub(r"\s+", r"\\s+", re.escape(n))
    m = re.search(pattern, haystack, flags=re.IGNORECASE | re.DOTALL)
    return m.start() if m else -1


def _pick_section_html_for_source(analysis_html: str, source_article: Optional[str]) -> str:
    if not source_article:
        return analysis_html
    m = re.search(r"(\d+(?:\.\d+)*)", source_article)
    wanted = m.group(1) if m else source_article.strip()
    soup = BeautifulSoup(analysis_html, "html.parser")
    for sec in soup.find_all("section"):
        title_text = " ".join(sec.get_text(" ", strip=True).split())
        if re.search(rf"\b{re.escape(wanted)}\b", title_text, flags=re.IGNORECASE):
            return str(sec)
    return analysis_html


def _rehydrate_images(fragment_html: str, img_map: dict) -> str:
    if not img_map:
        return fragment_html
    soup = BeautifulSoup(fragment_html, "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and src in img_map:
            img["src"] = img_map[src]
    return str(soup)


def extract_operand(
    analysis_html: str,
    source_article: str,
    start_marker: str,
    end_marker: str,
    img_map: ImageMap
) -> str:
    # TODO : appeler rehydrate images sur le fragment avant de le retourner

    scope_html = _pick_section_html_for_source(analysis_html, source_article)
    working_html = scope_html
    start_idx = _find_marker(working_html, start_marker)
    if start_idx == -1:
        working_html = analysis_html
        start_idx = _find_marker(working_html, start_marker)
        if start_idx == -1:
            raise ValueError("Start marker not found in analysis HTML.")
    
    end_idx = -1
    end_idx = _find_marker(working_html, end_marker)
    if end_idx != -1:
        end_idx = end_idx + len(end_marker)
    if end_idx != -1:
        fragment = working_html[start_idx:end_idx]
        return fragment
    soup_scope = BeautifulSoup(working_html, "html.parser")
    for tag_name in ["blockquote", "table", "p", "div", "section"]:
        for tag in soup_scope.find_all(tag_name):
            tag_html = str(tag)
            if _find_marker(tag_html, start_marker) != -1:
                return tag_html
    window = 2000
    fragment = working_html[start_idx : start_idx + window]
    return fragment if fragment else None



