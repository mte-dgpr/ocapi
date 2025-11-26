"""
Ce fichier doit
- lire data/arretes_bruts/*.html
- diviser chaque arrêté qui n'est pas marqué comme inutile en blocs pour préparer envoie LLM.
- écrire par AP un fichier JSON dans data/arretes_blocs/<nom>.blocks.json
Format attendu : liste de dicts {"index":i, "html": "..."} (normaliser la sortie si besoin). 
Le HTML est minifié.
"""

# TODO simplifier ? 

import json
import math
import re
import unicodedata
import argparse
import time
from pathlib import Path
from typing import List, Dict, Union, Optional, Tuple
from bs4 import BeautifulSoup

from permis.scripts.constants import PROJECT_ROOT
from permis.scripts.utils.io_utils import CATALOGUE_PATH

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


def _collect_candidates_from_body(soup: BeautifulSoup) -> List[str]:
    """
    Construire une liste de candidats à découper à partir du body :
    - privilégier les <section> de premier niveau
      (si une section est trop grosse, on tentera d'utiliser ses sous-sections pour éclater).
    - si aucune section trouvée, on utilise le document entier.
    """
    candidates: List[str] = []

    # 1) sections non imbriquées (top-level)
    top_sections = [sec for sec in soup.find_all("section") if sec.find_parent("section") is None]
    if top_sections:
        for sec in top_sections:
            sec_html = normalize_html_minify_fragment(str(sec))
            if sec_html and (not candidates or candidates[-1] != sec_html):
                candidates.append(sec_html)
        if candidates:
            return candidates

    # 2) pas de sections top-level : fallback -> document entier
    full = normalize_html_minify_fragment(str(soup))
    if full:
        candidates = [full]
    return candidates


def split_blocs(
    filepath: Union[str, Path], target_per_block: int = 70000, max_blocks: int = 5
) -> List[Dict]:
    """
    Lit un fichier HTML d'arrêté et renvoie une liste de blocs (dicts {"index","html"}).
    Stratégie :
    - minifier le HTML
    - extraire candidats via sections (top-level)
    - si un candidat est bien plus grand que target_per_block : tenter d'éclater par sous-sections
    - fusion progressive pour obtenir <= max_blocks
    """
    p = Path(filepath)
    raw = p.read_text(encoding="utf-8")

    # minify léger du document entier
    minified_doc = normalize_html_minify_fragment(raw)
    soup = BeautifulSoup(minified_doc, "html.parser")
    candidates = _collect_candidates_from_body(soup)

    # si candidat trop gros, essayer d'éclater par sections imbriquées (ou par plusieurs <section>)
    expanded = []
    for cand in candidates:
        if len(cand) > target_per_block * 2:
            soup_c = BeautifulSoup(cand, "html.parser")
            # si plusieurs sections dans le fragment -> utiliser ces sections
            subs = soup_c.find_all("section")
            if len(subs) > 1:
                parts = [normalize_html_minify_fragment(str(s)) for s in subs if str(s).strip()]
                if len(parts) > 1:
                    expanded.extend(parts)
                    continue
            # sinon, si ce fragment contient sous-sections directes, prendre ces sous-sections
            top = soup_c.find("section")
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
    candidates = expanded

    total_len = sum(len(c) for c in candidates)
    n_blocks = (
        min(max_blocks, max(1, math.ceil(total_len / target_per_block))) if total_len > 0 else 1
    )

    # si tout tient en un bloc -> renvoyer le document entier comme bloc unique
    if n_blocks == 1:
        return [{"index": 0, "html": minified_doc}]

    # fusion progressive pour atteindre n_blocks
    blocks: List[str] = []
    current = ""
    for i, cand in enumerate(candidates):
        current += cand
        if (len(current) >= target_per_block and len(blocks) < n_blocks - 1) or (
            len(blocks) + 1 == n_blocks and i == len(candidates) - 1
        ):
            blocks.append(current)
            current = ""
    if current:
        blocks.append(current)

    # sécurité : si aucune fusion -> tout mettre en un bloc
    if not blocks:
        return [{"index": 0, "html": minified_doc}]

    # normaliser en dicts
    normalized = [
        {"index": idx, "html": normalize_html_minify_fragment(b)} for idx, b in enumerate(blocks)
    ]
    return normalized


def _load_catalogue(path: Path = CATALOGUE_PATH) -> dict:
    """
    Charge le catalogue (liste d'objets) et retourne un mapping file -> category.
    Si le fichier est absent ou non lisible, renvoie {}.
    """
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return {}
        return {item.get("file"): item.get("category") for item in data if isinstance(item, dict)}
    except Exception:
        return {}


def _extract_and_strip_images(html: str) -> Tuple[str, Dict[str, str]]:
    """
    Remplace les src des <img> par des tokens __IMG_n__ et retourne (html_modifié, img_map).
    img_map : { "__IMG_n__": original_src }
    """
    soup = BeautifulSoup(html, "html.parser")
    img_map: Dict[str, str] = {}
    for i, img in enumerate(soup.find_all("img")):
        src = img.get("src") or img.get("data-src") or ""
        key = f"IMG_{i:03d}"
        if src:
            img_map[key] = src
        # remplacer src par token (garde la balise pour le LLM mais réduit la charge)
        img["src"] = key
    return str(soup), img_map


def process_file(
    src_path: Path, out_dir: Path, target_per_block: int = 40000, max_blocks: int = 10
):
    name = src_path.stem
    try:
        raw = src_path.read_text(encoding="utf-8")
        # minify puis extraire/strip images
        minified = normalize_html_minify_fragment(raw)
        minified, img_map = _extract_and_strip_images(minified)

        # split sur le HTML modifié (avec tokens)
        blocks = (
            split_blocs(src_path, target_per_block=target_per_block, max_blocks=max_blocks)
        )
        # si split_blocs attend un filepath, fallback : on reconstruit blocs ici
    except Exception as e:
        print(f"ERROR: extract_arrete_blocs failed for {src_path.name}: {e}")
        # fallback : tout en un bloc minifié et images strip
        full = normalize_html_minify_fragment(src_path.read_text(encoding="utf-8"))
        full, img_map = _extract_and_strip_images(full)
        blocks = [{"index": 0, "html": full}]

    # écrire mapping images (si non vide)
    if img_map:
        imgmap_path = out_dir / f"{name}.imgmap.json"
        imgmap_path.write_text(json.dumps(img_map, ensure_ascii=False, indent=2), encoding="utf-8")

    out_path = out_dir / f"{name}.blocks.json"
    out_path.write_text(json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(blocks)} blocks) imgmap:{bool(img_map)}")
    return out_path


def run(
    input_dir: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    target_per_block: int = 70000,
    max_blocks: int = 5,
):
    """
    Parcourt input_dir/*.html et écrit out_dir/<name>.blocks.json
    Ne traite que les arrêtés qui NE sont PAS marqués "inutile" dans le catalogue (data/journaux/catalogue_ap.json).
    Si le catalogue est absent, traite tous les fichiers.
    Default input_dir: PROJECT_PERMIS/data/arretes_bruts
    Default out_dir:   PROJECT_PERMIS/data/arretes_blocs
    """
    if input_dir is None:
        input_dir = PROJECT_PERMIS / "data" / "0005804239" / "arretes_bruts"
    if out_dir is None:
        out_dir = PROJECT_PERMIS / "data" / "0005804239" / "arretes_blocs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # charger catalogue rapide (file -> category)
    catalogue = _load_catalogue()
    if catalogue:
        print(
            f"Catalogue chargé ({len(catalogue)} entrées). Les fichiers marqués 'inutile' seront sautés."
        )
    else:
        print("Aucun catalogue trouvé ou fichier invalide : tous les arrêtés seront traités.")

    files = sorted(Path(input_dir).glob("*.html"))
    if not files:
        print("Aucun fichier HTML trouvé dans", input_dir)
        return

    t0 = time.time()
    processed = 0
    skipped = 0
    for f in files:
        fname = f.name
        # si catalogue présent et catégorie == 'inutile', on skip
        cat = catalogue.get(fname)
        if cat and cat.lower() in ("inutile", "autorisation"):
            skipped += 1
            print(f"Skip ({cat}) : {fname}")
            continue
        try:
            process_file(f, out_dir, target_per_block=target_per_block, max_blocks=max_blocks)
            processed += 1
        except Exception as e:
            print("Erreur processing", f.name, e)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.2f}s - processed: {processed}, skipped: {skipped}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Découper les arrêtés en blocs (minify + split)")
    p.add_argument("--input", "-i", help="dossier input HTML (arretes_bruts)")
    p.add_argument("--out", "-o", help="dossier de sortie (arretes_blocs)")
    p.add_argument("--target", "-t", type=int, default=40000, help="taille cible en chars par bloc")
    p.add_argument("--max", type=int, default=10, help="nombre max de blocs")
    args = p.parse_args()

    in_dir = Path(args.input) if args.input else None
    out_dir = Path(args.out) if args.out else None
    run(input_dir=in_dir, out_dir=out_dir, target_per_block=args.target, max_blocks=args.max)
