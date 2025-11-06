"""
Mappe les opérations (source_article / target_article) vers les uids des noeuds
générés par generer_structure_AP (fichiers .index.json dans arrete_structure/).

Amélioration : si target_arrete contient une date (ISO ou forme "08 décembre 2009"),
on retrouve automatiquement l'arrêté correspondant dans arrete_structures.
"""
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import json
import re

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRUCTURES_DIR = PROJECT_ROOT / "permis" / "data" / "0005804239" / "arretes_structure"
OUT_DIR = PROJECT_ROOT / "permis" / "data" / "0005804239" / "operations_mapped"
OUT_DIR.mkdir(parents=True, exist_ok=True)

#TODO simplifier le fichier ops. 


_MONTHS = {
    "janvier": "01", "fevrier": "02", "février": "02", "mars": "03", "avril": "04",
    "mai": "05", "juin": "06", "juillet": "07", "aout": "08", "août": "08",
    "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12", "décembre": "12"
}

def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _write_json(p: Path, obj: Any):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _normalize_str(s: Optional[str]) -> str:
    if not s:
        return ""
    t = re.sub(r"\s+", " ", s).strip().lower()
    t = re.sub(r"[^\w\s\-\.]", "", t)  # keep words, digits, dash, dot
    return t

def load_index_for_file(arrete_filename: str) -> Optional[Dict[str, Any]]:
    """
    Charge <doc_id>.index.json correspondant à arrete_filename (basename ou doc_id).
    """
    if not arrete_filename:
        return None
    doc_id = Path(arrete_filename).stem
    idx_path = STRUCTURES_DIR / f"{doc_id}.index.json"
    return _read_json(idx_path) if idx_path.exists() else None

def _parse_date_from_text(s: str) -> Optional[str]:
    """
    Tente d'extraire une date ISO (YYYY-MM-DD) ou une date FR (e.g. 08 décembre 2009) et retourne YYYY-MM-DD.
    """
    if not s:
        return None
    s = s.strip()
    # ISO
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    # jour mois année en français (ex: 8 décembre 2009 / 08 décembre 2009)
    m2 = re.search(r"(\d{1,2})\s+([A-Za-zéûôàèùêîâäëïç]+)\s+(\d{4})", s, flags=re.IGNORECASE)
    if m2:
        day = int(m2.group(1))
        month_raw = m2.group(2).lower()
        year = int(m2.group(3))
        month = _MONTHS.get(month_raw)
        if month:
            return f"{year:04d}-{month}-{day:02d}"
    return None

def _find_docid_by_date(date_iso: str) -> Optional[str]:
    """
    Cherche un doc_id dans STRUCTURES_DIR dont le doc_id commence par date_iso.
    Ex: date_iso="2009-12-08" -> match "2009-12-08_AP_mistral.index.json" -> doc_id "2009-12-08_AP_mistral"
    """
    if not date_iso:
        return None
    if not STRUCTURES_DIR.exists():
        return None
    for p in STRUCTURES_DIR.glob("*.index.json"):
        name = p.name
        if not name.endswith(".index.json"):
            continue
        doc_id = name[:-len(".index.json")]
        if doc_id.startswith(date_iso):
            return doc_id
    return None

def resolve_article_to_uid(arrete_filename: str, article_ref: Optional[str]) -> Tuple[Optional[str], str]:
    """
    Tente de résoudre article_ref (data-number, forme 'article 1' ou titre partiel) vers uid.
    Retourne (uid_or_none, reason).
    """
    if not article_ref:
        return None, "empty_ref"

    # si on a déjà un uid
    if "::" in str(article_ref):
        return str(article_ref), "already_uid"

    idx = load_index_for_file(arrete_filename)
    if not idx:
        return None, "no_index"

    # clé exacte (numéro)
    key_raw = str(article_ref).strip()
    if key_raw in idx.get("by_number", {}):
        return idx["by_number"][key_raw], "by_number"

    # extraction numérique ("article 1", "Article 1.2")
    m = re.search(r"(\d+(?:\.\d+)*)", key_raw)
    if m:
        num_key = m.group(1)
        if num_key in idx.get("by_number", {}):
            return idx["by_number"][num_key], "by_number_from_text"

    # titre substring
    needle = _normalize_str(article_ref)
    if not needle:
        return None, "empty_norm"
    for uid, meta in idx.get("by_uid", {}).items():
        titre = _normalize_str(meta.get("titre") or "")
        if titre and needle in titre:
            return uid, "title_match"

    return None, "not_found"

def _resolve_arrete_ref_to_docid(ref: Optional[str]) -> Optional[str]:
    """
    Si ref contient une date, retourne le doc_id correspondant dans STRUCTURES_DIR.
    Sinon retourne None.
    """
    if not ref:
        return None
    # si ref ressemble déjà à un filename/doc_id (commence par YYYY-)
    m_iso = re.match(r"(\d{4}-\d{2}-\d{2})", ref)
    if m_iso:
        date_iso = m_iso.group(1)
        found = _find_docid_by_date(date_iso)
        if found:
            return found
    # tenter d'extraire une date FR
    date_iso = _parse_date_from_text(ref)
    if date_iso:
        return _find_docid_by_date(date_iso)
    return None

def map_ops_object(ops_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pour chaque op on ajoute source_uid/target_uid/map_status/mapping_notes.
    """
    ops = ops_obj.get("operations", [])
    for op in ops:
        # source mapping
        src_file = op.get("source_file") or ops_obj.get("source_file")
        src_art = op.get("source_article") or op.get("article")
        uid, reason = resolve_article_to_uid(src_file, src_art)
        op["source_uid"] = uid
        op.setdefault("mapping_notes", []).append({"field": "source", "ref": src_art, "reason": reason, "source_file": src_file})

        # target mapping : tenter plusieurs champs possibles
        tgt_file_ref = op.get("target_file") or op.get("target_arrete") or op.get("target_source_file")
        # si target_file_ref est une description contenant une date, tenter de retrouver le doc_id
        resolved_docid = _resolve_arrete_ref_to_docid(tgt_file_ref) if isinstance(tgt_file_ref, str) else None
        if resolved_docid:
            tgt_file_for_lookup = resolved_docid  # pass doc_id to load_index_for_file (works with stem)
            op.setdefault("mapping_notes", []).append({"field": "target_arrete", "ref": tgt_file_ref, "reason": "resolved_by_date", "doc_id": resolved_docid})
        else:
            # si le champ est explicitement un filename, on l'utilise ; sinon, on essaie la même arrete que la source
            if isinstance(tgt_file_ref, str) and tgt_file_ref.strip():
                tgt_file_for_lookup = tgt_file_ref
            else:
                tgt_file_for_lookup = src_file

        tgt_ref = op.get("target_article") or op.get("target") or op.get("target_ref")
        tgt_uid, reason_t = resolve_article_to_uid(tgt_file_for_lookup, tgt_ref)
        op["target_uid"] = tgt_uid
        op.setdefault("mapping_notes", []).append({"field": "target", "ref": tgt_ref, "reason": reason_t, "target_file_used": tgt_file_for_lookup})

        # final status
        if (op.get("source_uid") or op.get("target_uid")):
            op["map_status"] = "mapped"
        else:
            op["map_status"] = "unmapped"
    return ops_obj

def map_ops_file(in_path: Path):
    """
    Lit un fichier .clean.json, produit .mapped.json dans operations_mapped/.
    """
    data = _read_json(in_path)
    if data is None:
        print("Impossible de lire", in_path)
        return
    mapped = map_ops_object(data)
    out_path = OUT_DIR / f"{in_path.stem}.mapped.json"
    _write_json(out_path, mapped)
    print(f"Wrote mapped operations: {out_path}")

if __name__ == "__main__":
    import sys
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not p or not p.exists():
        print("Usage: map_ops_to_tree.py <ops_clean.json>")
    else:
        map_ops_file(p)