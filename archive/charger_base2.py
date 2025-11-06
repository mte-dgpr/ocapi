"""
Charger la "base" et extraire la totalité des prescriptions au niveau des articles/sections.
- détecte où commencent les prescriptions (corps vs annexe)
- pour chaque article/section extrait :
    - uid, display_num, title, html complet
Sortie : data/journaux/base_<dossier>.json
"""



#TODO: est ce quon est dans le bon cas là ? pour notre exemple titre prescriptions jsp quoi 
#TODO : gros pb avec start block index. 
# TODO: séparer "trouver ap autorisation" en une fonction au début. puis envoyer LLM? trouver le début des prescriptions. 
# ... puis faire la suite : détecter les sections (attention, comment gérer les sous parties ?) et leur contenu. 
#charger 2 bases, une fois comme ça, une fois par LLM. faire un deuxième script. 

from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from bs4 import BeautifulSoup, Tag
import re
import json
import uuid
from datetime import datetime, timezone

PROJECT_PERMIS = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_PERMIS / "data" / "0005804239" / "arretes_bruts"
JOURNAUX_DIR = PROJECT_PERMIS / "data" / "0005804239" / "journaux"
JOURNAUX_DIR.mkdir(parents=True, exist_ok=True)

ADMIN_KW = {"publication","exécution","notification","affichage","recours","abrogation","signature"}
TECH_KW  = {"prescription","exploitation","nuisance","déchet","eaux","bruit","contrôle","surveillance","maintenance","sécurité","limite","seuil","registre","rapport","mesures","pollution"}

ART_RE   = re.compile(r"\bArticle\s+(1er|\d+(?:\.\d+)*)\b", re.IGNORECASE)
ANNEXE_RE = re.compile(r"\bannexe(s)?\b", re.IGNORECASE)
PRES_RE = re.compile(r"\bprescriptions?\b", re.IGNORECASE)

def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()
    #TODO utiliser la meme fonction que pour creer les blocs (normalize truc)

def _iter_document_blocks(soup: BeautifulSoup) -> List[Tuple[str, str, Tag]]:
    """
    Parcourt le document en ordre et retourne une liste de blocs (type, texte, tag)
    type in {"heading","text","other"}
    """
    blocks: List[Tuple[str, str, Tag]] = []
    body = soup.body or soup
    for el in body.find_all(True):
        name = el.name.lower() if getattr(el, "name", None) else ""
        if re.match(r"^h[1-6]$", name):
            txt = _clean_text(el.get_text(" ", strip=True))
            if txt:
                blocks.append(("heading", txt, el))
        elif name in ("article","section"):
            txt = _clean_text(el.get_text(" ", strip=True))
            if txt:
                blocks.append(("section", txt, el))
        elif name in ("p","div","li","td"):
            txt = _clean_text(el.get_text(" ", strip=True))
            if txt:
                blocks.append(("text", txt, el))
        else:
            txt = _clean_text(el.get_text(" ", strip=True))
            if txt:
                blocks.append(("other", txt, el))
    return blocks

def _find_start_zone(soup: BeautifulSoup) -> Tuple[str, Optional[Tag], int]:
    """
    Retourne (rule_name, start_tag, index_in_blocks)
    règle prioritaire :
      1) heading contenant 'prescriptions'
      2) heading 'annexe' suivi d'articles ou 'prescriptions'
      3) scoring admin vs tech sur premiers articles
      4) fallback début du document
    """
    blocks = _iter_document_blocks(soup)
    full_text = " ".join(t for _,t,_ in blocks)

    # règle 1 : heading "Prescriptions"
    for i,(k,t,tag) in enumerate(blocks):
        if k == "heading" and PRES_RE.search(t):
            return ("titre-prescriptions", tag, i)

    # règle 2 : annexe contenant prescriptions / articles
    ann_idx = None
    for i,(k,t,tag) in enumerate(blocks):
        if k == "heading" and ANNEXE_RE.search(t):
            ann_idx = i
            break
    if ann_idx is not None:
        window = " ".join(txt for _,txt,_ in blocks[ann_idx:ann_idx+200])
        if PRES_RE.search(window) or ART_RE.search(window):
            return ("annexe-avec-prescriptions", blocks[ann_idx][2], ann_idx)

    # règle 3 : scorer les premiers Article
    art_matches = list(ART_RE.finditer(full_text))
    if art_matches:
        for m in art_matches[:15]:
            pos = m.start()
            ctx = full_text[max(0,pos-300): pos+500]
            admin_hits = sum(1 for w in ADMIN_KW if re.search(rf"\b{re.escape(w)}\b", ctx, re.IGNORECASE))
            tech_hits  = sum(1 for w in TECH_KW  if re.search(rf"\b{re.escape(w)}\b", ctx, re.IGNORECASE))
            if tech_hits >= max(1, admin_hits):
                acc = 0
                for i,(k,t,tag) in enumerate(blocks):
                    acc += len(t) + 1
                    if acc >= pos:
                        return ("premier-article-technique", tag if tag else None, i)
                break

    first_tag = blocks[0][2] if blocks else (soup.body or soup)
    return ("debut", first_tag, 0)

def _collect_articles_from_tag(start_tag: Optional[Tag], soup: BeautifulSoup, doc_id: str) -> List[Dict[str,Any]]:
    """
    A partir du start_tag (inclusif), recherche <article> ou <section> situés après.
    Si aucun, découpe par titres Hn à partir du start_tag.
    Retourne la liste d'articles extraits avec uid/display_num/title/html/doc_id.
    """
    #TODO : ne gère pas les articles imbriqués!!!

    results: List[Dict[str,Any]] = []

    body = soup.body or soup
    all_tags = list(body.find_all(True))
    start_idx = 0
    if start_tag is not None:
        try:
            start_idx = all_tags.index(start_tag)
        except ValueError:
            start_idx = 0

    # récupérer sections/articles après start_idx
    candidates = []
    for t in all_tags[start_idx:]:
        if getattr(t, "name", "").lower() in ("article","section"):
            candidates.append(t)

    if not candidates:
        # fallback: découpe par headings H1..H6 après start_idx
        headings = []
        for t in all_tags[start_idx:]:
            if re.match(r"^h[1-6]$", getattr(t, "name", "").lower()):
                headings.append(t)
        for i,h in enumerate(headings):
            level = int(h.name[1])
            frag_nodes = [h]
            for sib in h.next_siblings:
                if isinstance(sib, Tag) and re.match(r"^h[1-6]$", getattr(sib,"name","").lower()):
                    if int(sib.name[1]) <= level:
                        break
                frag_nodes.append(sib)
            html_fragment = "".join(str(n) for n in frag_nodes)
            heading_text = _clean_text(h.get_text(" ", strip=True))
            dm = ART_RE.search(heading_text)
            display = dm.group(1) if dm else None
            uid = f"{doc_id}::{uuid.uuid4().hex[:8]}"
            results.append({
                "uid": uid,
                "display_num": display,
                "title": heading_text,
                "html": html_fragment,
                "doc_id": doc_id,
                "path": [],
                "status": "active",
                "trace": []
            })
        return results

    # si on a des sections/articles candidates
    for sec in candidates:
        html_fragment = str(sec)
        heading_text = _clean_text(sec.get_text(" ", strip=True))
        dm = ART_RE.search(heading_text)
        display = dm.group(1) if dm else None
        uid = f"{doc_id}::{uuid.uuid4().hex[:8]}"
        results.append({
            "uid": uid,
            "display_num": display,
            "title": heading_text,
            "html": html_fragment,
            "doc_id": doc_id,
            "path": [],
            "status": "active",
            "trace": []
        })
    return results

def _read_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _find_autorisation_in_catalogue(cat_path: Path) -> Optional[str]:
    """
    Retourne le nom de fichier (champ 'file') de l'entrée dont category == 'autorisation'.
    Si plusieurs, renvoie la première trouvée. None si rien.
    """
    data = _read_json(cat_path)
    if not isinstance(data, list):
        return None
    for it in data:
        if isinstance(it, dict) and (it.get("category") or "").strip().lower() == "autorisation":
            return it.get("file")
    return None

def run(input_dir: Optional[Path] = None, out_path: Optional[Path] = None):
    """
    Traite uniquement l'AP marqué 'autorisation' dans le catalogue.
    - Si un catalogue est fourni (--catalogue) on l'utilise.
    - Sinon on cherche automatiquement un fichier catalogue*.json dans JOURNAUX_DIR.
    - Si aucune 'autorisation' n'est trouvée, on ne traite RIEN et le script s'arrête.
    """
    if input_dir is None:
        input_dir = DEFAULT_INPUT
    if out_path is None:
        out_path = JOURNAUX_DIR / f"base_{input_dir.name}.json"

    # trouver l'AP autorisation grâce au catalogue créé dans le dossier
    autorisation_file = None
    catalogue_path = JOURNAUX_DIR / "catalogue_ap.json"
    if not catalogue_path.exists():
        print("Aucun catalogue trouvé, pas d'AP autorisation détecté.")
        return
    autorisation_file = _find_autorisation_in_catalogue(catalogue_path)
    print(f"Catalogue auto chargé -> fichier autorisation detecté: {autorisation_file}")

    # ne traiter que le fichier autorisation (nom exactt)
    files = sorted(Path(input_dir).glob("*.html"))
    for file in files: 
        if file.name == autorisation_file:
            f = file
    documents: List[Dict[str,Any]] = []
    total_articles = 0
    txt = _read_text(f)
    soup = BeautifulSoup(txt, "html.parser")

    rule, start_tag, start_idx = _find_start_zone(soup) #à comprendre lol
    articles = _collect_articles_from_tag(start_tag, soup, f.stem)
    # déterminer si start dans annexe/prescriptions pour path
    path_label = None
    parent = start_tag
    while parent and getattr(parent, "name", None):
        t = _clean_text(parent.get_text(" ", strip=True))
        if ANNEXE_RE.search(t):
            path_label = "Annexe"
            break
        if PRES_RE.search(t):
            path_label = "Prescriptions"
            break
        parent = parent.parent
    for a in articles:
        a["path"] = [path_label] if path_label else []
    documents.append({
        "file": f.name,
        "doc_id": f.stem,
        "rule_chosen": rule,
        "start_block_index": start_idx,
        "n_articles_extracted": len(articles),
        "articles": articles
    })
    
    total_articles += len(articles)

    snapshot = {
        "source_dir": str(input_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents": documents
    }
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote base snapshot {out_path} ({len(documents)} documents, total articles: {total_articles})")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Charger base et extraire intégralement les prescriptions (articles complets)")
    p.add_argument("--input", "-i", help="dossier input .html (arretes_bruts)")
    p.add_argument("--out", "-o", help="fichier de sortie snapshot JSON")
    args = p.parse_args()
    run(input_dir=Path(args.input) if args.input else None,
        out_path=Path(args.out) if args.out else None)