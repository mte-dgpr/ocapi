"""
Ce fichier contient la logique pour extraire le contenu (operand) d'une opération
à partir d'un bloc HTML analysé, en utilisant des marqueurs de début et de fin.
"""

# TODO corriger l'article source lors de l'extraction de contenu.
# TODO plus tard :des qu'un texte mais respecte pas les marker, a revoir.
# TODO plus tard: modification des operations. (modif des titres etc)


import html
import re

from bs4 import BeautifulSoup

ImageMap = dict[str, str]  # mapping from placeholder src to real src


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
    # Chercher une section avec data-number correspondant
    for section in soup.find_all("section", attrs={"data-spec": "section"}):
        data_number = section.get("data-number")
        if data_number and data_number == source_article:
            return str(section)
    raise ValueError("No matching section found for the given source article.")


def _rehydrate_images(fragment_html: str, img_map: dict[str, str]) -> str:
    if not img_map:
        return fragment_html
    soup = BeautifulSoup(fragment_html, "html.parser")
    for img in soup.find_all("img"):
        src_attr = img.get("src")
        src = str(src_attr) if src_attr is not None else None
        if src and src in img_map:
            img["src"] = img_map[src]
    return str(soup)


# TODO : insérer un fallback llm si pas trouvé


def extract_operand_with_images(
    block_html: str, source_article: str, start_marker: str, end_marker: str, img_map: ImageMap
) -> str:

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
        fragment = working_html[start_idx : end_idx + len(end_marker)]
        fragment = _rehydrate_images(fragment, img_map)
        return fragment
    else:
        raise ValueError("End marker not found in analysis HTML.")
