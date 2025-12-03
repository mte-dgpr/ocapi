"""
Ce fichier doit
- lire data/arretes_bruts/*.html
- diviser chaque arrêté qui n'est pas marqué comme inutile en blocs pour préparer envoie LLM.
- écrire par AP un fichier JSON dans data/arretes_blocs/<nom>.blocks.json
Format attendu : liste de dicts {"index":i, "html": "..."} (normaliser la sortie si besoin). 
Le HTML est minifié.
"""

# TODO simplifier ? 

import math
import re
import unicodedata
from typing import Iterator, List, Dict, Tuple
from bs4 import BeautifulSoup, Tag

from ocapi.types import ArreteFile
from ocapi.utils.arretify_utils import list_top_sections
from ocapi.utils.documents import ContentType, make_document_factory
from langchain_core.documents import Document

ImageMap = Dict[str, str]  # mapping token -> original src

_ARRETIFY_SECTION_SELECTOR = "*[data-spec='section']"


def normalize_html_minify_fragment(html: str) -> str:
    """
    Minification légère et normalisation Unicode pour un fragment HTML.
    - supprime <script>/<style>
    - normalize Unicode
    - enlève espaces entre balises et runs d'espaces
    """
    s = str(html or "")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"(?is)<script.*?>.*?</script>", "", s)
    s = re.sub(r"(?is)<style.*?>.*?</style>", "", s)
    s = re.sub(r">\s+<", "><", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def split_blocs(
    minified_soup: BeautifulSoup, arrete_file: ArreteFile, target_per_block: int,
) -> Iterator[Document]:
    document_factory = make_document_factory(ContentType.HTML, parent=arrete_file.id)    

    ignored_sections : list[Tag] = []
    selected_sections: list[Tag] = []
    # TODO : adapter le selector pour la syntaxe arretify 
    for section in minified_soup.select(_ARRETIFY_SECTION_SELECTOR):
        if section in ignored_sections:
            continue
        if all(_is_arretify_section(child) or _is_arretify_section_title(child) for child in section.contents):
            continue
        elif len(section.find_all(_ARRETIFY_SECTION_SELECTOR)) == 0:
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

    minified = normalize_html_minify_fragment(str(arrete_file.soup))
    minified, img_map = _extract_and_strip_images(minified)
    soup_without_images = BeautifulSoup(minified, "html.parser")
    
    number_of_blocks = min(math.ceil(len(soup_without_images) / 70000), 5)
    target_per_block = math.ceil(len(soup_without_images) / number_of_blocks)

    blocks = (
        split_blocs(soup_without_images, target_per_block=target_per_block)
    )

    return blocks, img_map


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