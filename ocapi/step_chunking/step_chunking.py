"""
Ce step prend une liste d'arretes (ArreteFile) et retourne une liste de documents chunkés (Document) et une map des images.
Chaque document correspond à un bloc d'articles extrait de l'arrêté, avec une taille cible définie pour chaque bloc.
"""

import math
from typing import Iterator, Tuple
from bs4 import BeautifulSoup, Tag

from ocapi.types import ArreteFile, ArreteId, ImageMap
from ocapi.utils.documents import ContentType, make_document_factory
from langchain_core.documents import Document

from ocapi.utils.utils import minify_html_fragment


_ARRETIFY_SECTION_SELECTOR = "*[data-spec=\"section\"]"



def split_blocs(
    minified_soup: BeautifulSoup, arrete_id: ArreteId, target_per_block: int,
) -> Iterator[Document]:
    document_factory = make_document_factory(ContentType.HTML, parent=arrete_id)    

    ignored_sections : list[Tag] = []
    selected_sections: list[Tag] = []

    for section in minified_soup.select(_ARRETIFY_SECTION_SELECTOR):
        if section in ignored_sections:
            continue
        if all((_is_arretify_section(child) or _is_arretify_section_title(child)) for child in section.contents):
            continue
        
        # Utiliser .select() au lieu de .find_all() pour les sélecteurs CSS
        child_sections = section.select(_ARRETIFY_SECTION_SELECTOR)
        if len(child_sections) == 0:
            selected_sections.append(section)
        else:
            selected_sections.append(section)
            ignored_sections.extend(section.select(_ARRETIFY_SECTION_SELECTOR))

    current_block: list[str]=[]
    current_size=0
    while selected_sections:
        current_block.append(str(selected_sections.pop(0)))
        current_size+=len(current_block[-1])
        if current_size >= target_per_block:
            yield document_factory("".join(current_block))
            current_block=[]
            current_size=0
    if current_block:
        yield document_factory("".join(current_block))


def _extract_and_strip_images(html: str) -> Tuple[str, ImageMap]:
    """
    Remplace les src des <img> par des tokens __IMG_n__ et retourne (html_modifié, img_map).
    img_map : { "__IMG_n__": original_src }
    """
    soup = BeautifulSoup(html, "html.parser")
    img_map: ImageMap = {}
    for i, img in enumerate(soup.find_all("img")):
        src = img.get("src") or img.get("data-src") or ""
        key = f"IMG_{i:03d}"
        if src:
            img_map[key] = src
        # remplacer src par token (garde la balise pour le LLM mais réduit la charge)
        img["src"] = key
    return str(soup), img_map


def step_chunking(
    arrete_file : ArreteFile,
)-> Tuple[list[Document], ImageMap]:

    minified = minify_html_fragment(str(arrete_file.soup))
    minified, img_map = _extract_and_strip_images(minified)
    soup_without_images = BeautifulSoup(minified, "html.parser")
    
    # Calculer le nombre de blocs basé sur la taille en caractères
    html_length = len(str(soup_without_images))
    number_of_blocks = min(math.ceil(html_length / 70000), 5)
    target_per_block = math.ceil(html_length / number_of_blocks)

    blocks = (
        split_blocs(soup_without_images, arrete_file.id, target_per_block=target_per_block)
    )

    return list(blocks), img_map


def _is_arretify_section(tag: Tag | str) -> bool:
    if not isinstance(tag, Tag):
        return False
    if tag.get("data-spec") == "section":
        return True
    return False


def _is_arretify_section_title(tag: Tag | str) -> bool:
    if not isinstance(tag, Tag):
        return False
    if tag.get("data-spec") == "section-title":
        return True
    return False