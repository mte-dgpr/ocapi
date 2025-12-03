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
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup

from ocapi.utils.arretify_utils import list_top_sections
from langchain_core.documents import Document

ImageMap = Dict[str, str]  # mapping token -> original src

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
    soup: BeautifulSoup, target_per_block: int = 70000, max_blocks: int = 5
) -> List[Dict]:
    """
    Lit un fichier HTML d'arrêté et renvoie une liste de blocs (dicts {"index","html"}).
    Stratégie :
    - minifier le HTML
    - extraire candidats via sections (top-level)
    - si un candidat est bien plus grand que target_per_block : tenter d'éclater par sous-sections
    - fusion progressive pour obtenir <= max_blocks
    """

    # minify léger du document entier
    top_sections = list_top_sections(soup)

    # si candidat trop gros, essayer d'éclater par sections imbriquées (ou par plusieurs <section>)
    expanded = []
    for cand in top_sections:
        if len(cand) > target_per_block * 2:
            # si plusieurs sections dans le fragment -> utiliser ces sections
            subs = cand.find_all("section")
            if len(subs) > 1:
                expanded.extend(subs)

            else:
                # sinon, si ce fragment contient sous-sections directes, prendre ces sous-sections
                top = cand.find("section")
                if top:
                    child_secs = [s for s in top.find_all("section", recursive=False)]
                    if child_secs:
                        parts = [
                            normalize_html_minify_fragment(str(s)) for s in child_secs if str(s).strip()
                        ]
                        if len(parts) > 1:
                            expanded.extend(parts)
                            continue
        expanded.append(cand)
    top_sections = expanded

    total_len = sum(len(c) for c in top_sections)
    n_blocks = (
        min(max_blocks, max(1, math.ceil(total_len / target_per_block))) if total_len > 0 else 1
    )

    # si tout tient en un bloc -> renvoyer le document entier comme bloc unique
    if n_blocks == 1:
        return [{"index": 0, "html": str(soup)}]

    # fusion progressive pour atteindre n_blocks
    blocks: List[str] = []
    current = ""
    for i, cand in enumerate(top_sections):
        current += cand
        if (len(current) >= target_per_block and len(blocks) < n_blocks - 1) or (
            len(blocks) + 1 == n_blocks and i == len(top_sections) - 1
        ):
            blocks.append(current)
            current = ""
    if current:
        blocks.append(current)

    # sécurité : si aucune fusion -> tout mettre en un bloc
    if not blocks:
        return [{"index": 0, "html": str(soup)}]

    # normaliser en dicts
    normalized = [
        {"index": idx, "html": normalize_html_minify_fragment(b)} for idx, b in enumerate(blocks)
    ]
    return normalized


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
    raw : str, target_per_block: int = 40000, max_blocks: int = 10
)-> Tuple[list[Document], ImageMap]:
    # TODO: utiliser documents 
    # minify puis extraire/strip images
    minified = normalize_html_minify_fragment(raw)
    minified, img_map = _extract_and_strip_images(minified)

    # split sur le HTML modifié (avec tokens)
    blocks = (
        split_blocs(soup, target_per_block=target_per_block, max_blocks=max_blocks)
    )

    return blocks, img_map  