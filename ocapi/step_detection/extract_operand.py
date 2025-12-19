"""
Ce fichier contient la logique pour extraire le contenu (operand) d'une opération
à partir d'un bloc HTML analysé, en utilisant des marqueurs de début et de fin.
"""

# TODO corriger l'article source lors de l'extraction de contenu.
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


def pick_arretify_section(html: str, source_article: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Cas 1 : "APPENDIX" : retourner tout le footer appendix
    if source_article == "APPENDIX":
        footer = soup.find("footer", attrs={"data-spec": "appendix"})
        if footer: return str(footer)
        raise ValueError("No appendix footer found")
    
    # Cas 2 : "APPENDIX:X" ou "APPENDIX:X.Y.Z" → chercher dans le footer appendix
    if source_article.startswith("APPENDIX:"):
        appendix_number = source_article.split("APPENDIX:", 1)[1]
        footer = soup.find("footer", attrs={"data-spec": "appendix"})
        if footer: 
            for section in footer.find_all("section", attrs={"data-spec": "section"}):
                data_number = section.get("data-number")
                if data_number == appendix_number:
                    return str(section)
            raise ValueError(f"No section with data-number={appendix_number} found in appendix")
    
    # Cas 3 : Article normal (ex: "2.1.3")
    for section in soup.find_all("section", attrs={"data-spec": "section"}):
        data_number = section.get("data-number")
        if data_number == source_article:
            return str(section)
    print("Section not found for source_article:", source_article)
    raise ValueError("No matching section found for the given source article.")


def _rehydrate_images(fragment_html: str, img_map: dict) -> str:
    if not img_map:
        return fragment_html
    soup = BeautifulSoup(fragment_html, "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and src in img_map:
            img["src"] = img_map[src]
    return str(soup)

# TODO : insérer un fallback llm si pas trouvé

def extract_operand_with_images(
    block_html: str,
    source_article: str,
    start_marker: str,
    end_marker: str,
    img_map: ImageMap
) -> str:
    # garder working_html pour chercher les markers ? pourquoi on le change
    section = pick_arretify_section(block_html, source_article)
    working_html = section
    start_idx = _find_marker(working_html, start_marker)
    if start_idx == -1:
        working_html = block_html
        start_idx = _find_marker(working_html, start_marker)
        if start_idx == -1:
            raise ValueError("Start marker not found in analysis HTML.")

    end_idx = _find_marker(working_html, end_marker)
    if end_idx != -1:
        fragment = working_html[start_idx:end_idx+ len(end_marker)]
        fragment = _rehydrate_images(fragment, img_map)
        return fragment
    else:
        # Diagnostic détaillé
        context_start = max(0, start_idx - 200)
        context_end = min(len(working_html), start_idx + 500)
        context = working_html[context_start:context_end]
        raise ValueError(
            f"End marker not found in analysis HTML.\n"
            f"Looking for: {end_marker[:200]}\n"
            f"Context around start marker (200 chars before, 500 after):\n{context}"
        )



