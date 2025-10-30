"""
Ce fichier lit data/operations_brutes/*.json
But :
- normaliser le format des opérations (type, cible, ordre, source_file, block_index)
- pour chaque opération contenant new_content_ref (start/end markers) :
    -> appeler remplacer_new_content pour remplir new_content_html
    -> supprimer champs temporaires
- marquer op["status"]="a_revoir" si extraction échoue (contexte ajouté)
- écrire résultats finaux dans data/operations_nettoyees/<source>.clean.json
"""


#TODO a revoir. notamment quand on aura modifié les opérations. (plus tard)
#TODO remplacer les "a_revoir" tq des que ya autre chose qu'un abroge et pas de texte, a revoir, des qu'un texte mais respecte pas les marker, a rveoir. 
#TODO c quoi le statut c quoi l'ordre


from pathlib import Path
import json
import os
import re
import time
from typing import Optional, List, Dict, Any

from bs4 import BeautifulSoup
import re, html

def _find_marker(haystack: str, marker: str) -> int:
    """
    
    """
    if not marker: return -1
    i = haystack.find(marker)
    if i != -1: return i
    n = html.unescape(marker)
    pattern = re.sub(r"\s+", r"\\s+", re.escape(n))
    m = re.search(pattern, haystack, flags=re.IGNORECASE | re.DOTALL)
    return m.start() if m else -1

def _pick_section_html_for_source(analysis_html: str, source_article: Optional[str]) -> str:
    if not source_article:
        return analysis_html
    m = re.search(r'(\d+(?:\.\d+)*)', source_article)
    wanted = m.group(1) if m else source_article.strip()
    soup = BeautifulSoup(analysis_html, "html.parser")
    for sec in soup.find_all("section"):
        title_text = " ".join(sec.get_text(" ", strip=True).split())
        if re.search(rf'\b{re.escape(wanted)}\b', title_text, flags=re.IGNORECASE):
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

def remplacer_new_content(analysis_html: str, img_map: dict, source_article: Optional[str], start_marker: Optional[str], end_marker: Optional[str]) -> Optional[str]:
    if not start_marker:
        return None
    scope_html = _pick_section_html_for_source(analysis_html, source_article)
    working_html = scope_html
    start_idx = _find_marker(working_html, start_marker)
    if start_idx == -1:
        working_html = analysis_html
        start_idx = _find_marker(working_html, start_marker)
        if start_idx == -1:
            return None
    end_idx = -1
    if end_marker:
        end_idx = _find_marker(working_html, end_marker)
        if end_idx != -1:
            end_idx = end_idx + len(end_marker)
    if end_idx != -1:
        fragment = working_html[start_idx:end_idx]
        return _rehydrate_images(fragment, img_map).strip()
    soup_scope = BeautifulSoup(working_html, "html.parser")
    for tag_name in ["blockquote", "table", "p", "div", "section"]:
        for tag in soup_scope.find_all(tag_name):
            tag_html = str(tag)
            if _find_marker(tag_html, start_marker) != -1:
                return _rehydrate_images(tag_html, img_map).strip()
    window = 2000
    fragment = working_html[start_idx:start_idx + window]
    return _rehydrate_images(fragment, img_map).strip() if fragment else None

# --- utilitaires pour ce script ---
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # bench-ocapi
BRUTES_DIR = PROJECT_ROOT / "permis" / "data" / "0005804239" / "operations_brutes"
BLOCKS_DIR = PROJECT_ROOT / "permis" / "data" / "0005804239" /"arretes_blocs"
RAW_HTML_DIR = PROJECT_ROOT / "permis" / "data" / "0005804239" / "arretes_bruts" #TODO normalement pas besoin? pk ? 
OUT_DIR = PROJECT_ROOT / "permis" / "data" / "0005804239" / "operations_nettoyees"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERR read json {path}: {e}")
        return None

def _load_blocks_for_source(source_file: str) -> Dict[int, str]:
    """
    Retourne mapping block_index -> html pour le source_file si fichier .blocks.json existe.
    """
    base = Path(source_file).stem if source_file else None
    if not base:
        return {}
    blocks_path = BLOCKS_DIR / f"{base}.blocks.json"
    if not blocks_path.exists():
        return {}
    data = _read_json(blocks_path)
    blocks = {}
    if isinstance(data, list):
        for b in data:
            idx = b.get("index", None) if isinstance(b, dict) else None
            html = b.get("html", "") if isinstance(b, dict) else str(b)
            if idx is None:
                idx = len(blocks)
            blocks[int(idx)] = html
    return blocks

# --- nouveau : charger le mapping image tokens -> url original ---
def _load_imgmap_for_source(source_file: str) -> Dict[str, str]:
    """
    Cherche <base>.imgmap.json à côté de <base>.blocks.json dans BLOCKS_DIR.
    Retourne mapping token -> original_src (ex: "__IMG_0__" -> "https://...")
    """
    base = Path(source_file).stem if source_file else None
    if not base:
        return {}
    imgmap_path = BLOCKS_DIR / f"{base}.imgmap.json"
    if not imgmap_path.exists():
        return {}
    data = _read_json(imgmap_path)
    if isinstance(data, dict):
        return data
    return {}

def _normalize_operation(op: Dict[str, Any], default_src: str) -> Dict[str, Any]:
    """
    Normaliser noms de champs basiques et ajouter métadatas attendues.
    Probablement : fonction à supprimer.
    """
    # type / modification_type
    op = dict(op)  # copy
    op.setdefault("modification_type", op.get("type") or op.get("action") or op.get("modification_type"))
    op.setdefault("source_file", op.get("source_file") or default_src)
    # block index coercion
    bi = op.get("block_index", op.get("block"))
    try:
        if bi is not None:
            op["block_index"] = int(bi)
    except Exception:
        op["block_index"] = None
    # order / ordre
    op.setdefault("ordre", op.get("ordre") or op.get("order") or op.get("rank") or 0)
    # ensure source_article key exists
    op.setdefault("source_article", op.get("source_article") or op.get("article") or None)
    return op

def _cleanup_temp_fields(op: Dict[str, Any]):
    for k in ("new_content_ref", "new_content_html_preview", "raw_llm_text", "preview"):
        if k in op:
            op.pop(k, None)

def process_one_brut(path: Path):
    data = _read_json(path)
    if data is None:
        return
    
    ops_list = data.get("operations", [])
    # si les opérations n'ont pas de champ 'ordre', on utilise la position dans la liste
    for _i, raw in enumerate(ops_list):
        if isinstance(raw, dict):
            # ne pas écraser un ordre déjà fourni par le LLM
            if raw.get("ordre") is None and raw.get("order") is None and raw.get("rank") is None:
                raw["ordre"] = _i
    meta = {k: v for k, v in data.items() if k != "operations"}

    source_file = meta.get("source_file") or path.stem.replace(".ops", "") + ".html"
    blocks_map = _load_blocks_for_source(source_file)
    # charger img_map correspondant (tokens -> original src) si présent
    img_map_global = _load_imgmap_for_source(source_file)

    cleaned_ops = []
    for raw_op in ops_list:
        op = _normalize_operation(raw_op if isinstance(raw_op, dict) else {}, source_file) #maybe a suppr
        # extraction step if new_content_ref present
        new_ref = op.get("new_content_ref") or {}
        start_marker = None
        end_marker = None
        if isinstance(new_ref, dict):
            start_marker = new_ref.get("start_marker") or new_ref.get("start")
            end_marker = new_ref.get("end_marker") or new_ref.get("end")
        # determine HTML context: block html preferred
        html_context = None
        if op.get("block_html"): # checker comment ça marche ça 
            html_context = op.get("block_html")
        elif isinstance(blocks_map, dict) and op.get("block_index") in blocks_map:
            html_context = blocks_map.get(op.get("block_index"))
        elif raw_html_full := _read_raw_html(source_file):
            html_context = raw_html_full

        # try extraction when needed
        op["status"] = op.get("status") or "ok"
        if start_marker and op.get("modification_type", "").upper() != "DELETE":
            try:
                # utiliser img_map chargé depuis .imgmap.json (si existant),
                # sinon {} : remplacer_new_content gère le cas.
                img_map = img_map_global or {}
                new_html = None
                if html_context:
                    new_html = remplacer_new_content(html_context, img_map, op.get("source_article"), start_marker, end_marker)
                if new_html:
                    op["new_content_html"] = new_html
                    op["status"] = "ok"
                else:
                    op["new_content_html"] = None
                    op["status"] = "a_revoir"
                    op.setdefault("notes", []).append("extraction_failed: markers not found or ambiguous")
            except Exception as e:
                op["new_content_html"] = None
                op["status"] = "a_revoir"
                op.setdefault("notes", []).append(f"extraction_exception: {e}")
        else:
            # nothing to extract (DELETE or no markers) -- mais on peut réhydrater un éventuel block_html fourni par le LLM
            if op.get("block_html") and img_map_global:
                try:
                    op["block_html"] = _rehydrate_images(op["block_html"], img_map_global)
                except Exception:
                    pass
            op.setdefault("new_content_html", None)

        # cleanup temporaries
        _cleanup_temp_fields(op)

        # keep limited context for debug if a_revoir
        if op["status"] == "a_revoir":
            ctx = None
            if html_context:
                ctx = html_context[:2000]
            op.setdefault("context_excerpt", ctx)

        cleaned_ops.append(op)

    # write output
    out_name = path.stem
    out_path = OUT_DIR / f"{out_name}.clean.json"
    out_obj = {
        "source_file": source_file,
        "n_ops_in": len(ops_list),
        "n_ops_out": len(cleaned_ops),
        "processed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "operations": cleaned_ops
    }
    out_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote cleaned operations: {out_path} ({len(cleaned_ops)} ops)")

def run(input_dir: Optional[Path] = None):
    """
    Parcourt data/operations_brutes et nettoie chaque fichier.
    """
    if input_dir is None:
        input_dir = BRUTES_DIR
    files = sorted(Path(input_dir).glob("*.json"))
    if not files:
        print("Aucun fichier brut trouvé dans", input_dir)
        return
    for f in files:
        try:
            process_one_brut(f)
        except Exception as e:
            print("Erreur processing", f.name, e)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Nettoyer et enrichir operations brutes (extraction des markers)")
    p.add_argument("--input", "-i", help="dossier operations_brutes (par defaut data/operations_brutes)")
    args = p.parse_args()
    run(input_dir=Path(args.input) if args.input else None)


