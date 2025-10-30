"""
Ce fichier doit ouvrir un dossier d'AP qui concernent une ICPE, et classifier en déterminant le type d'AP dont il d'agit. 
Un AP peut être par exemple : 
- l'AP d'autorisation d'exploitation (l'AP initial, à identifier absolument)
- un AP complémentaire modifiant l'AP auto 
- un AP complémentaire autre à conserver en annexe (garanties financières, ...)
- un AP inutile à ne pas traiter (une mise en demeure ou abrogation de mise en demeure)

attention : potentiellement AP refonte. 
................ bon en fait !!!!!!!!!!!! on va skip cette étape pour l'instant. 
pour l'instant, AP auto considère que c le premier fichier. puis pr les autres qui sont pas connexes, et bah on les met juste en annexe à la fin. 
le graphe va aider à savoir qui est l'AP auto... la racine ??

Par exemple : 
lire data/arretes_propres/*.html
pour chaque AP, décider la catégorie : 'autorisation' | 'complementaire' | 'annexe' | 'inutiles'
règles initiales : mots-clés + heuristiques simples (titre, entête); produire un CSV/JSON de catalogage
sortie : data/journaux/catalogue_ap.json avec meta {file, date, category, confidence, notes}

"""
#TODO: garder metadonnees avec date de l'arrêté.... pas classifié du coup 
#TODO pour l'instant auto = le premier. 
#TODO si mise en demeure dan sle titre.... alors on le marque comme inutile. 
"""
Pré-traitement très simple des arrêtés :
- extrait la date depuis le nom de fichier AAAA-MM-JJ_...
- extrait le titre depuis <div class="arretify-arrete_title"> dans le HTML
- marque le plus ancien arrêté (selon date trouvée) comme "autorisation"
- pour les autres : si le titre contient "mise en demeure" => "inutile", et "garanties financières" => annexe, sinon "complementaire"
Sortie : data/journaux/catalogue_ap.json
"""
from pathlib import Path
import json
import re
import unicodedata
from datetime import datetime
from typing import Optional, List, Dict
from bs4 import BeautifulSoup

PROJECT_PERMIS = Path(__file__).resolve().parents[2]  # .../permis
INPUT_DIR = PROJECT_PERMIS / "data" / "0005804239" / "arretes_bruts"
OUT_DIR = PROJECT_PERMIS / "data" / "0005804239" / "journaux"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "catalogue_ap.json"

_date_re = re.compile(r'(\d{4}-\d{2}-\d{2})')
_title_class_re = re.compile(r"arretify[-_]arrete_title", flags=re.IGNORECASE)

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s

def extract_date_from_filename(name: str) -> Optional[str]:
    """
    Cherche AAAA-MM-JJ dans le nom et renvoie 'AAAA-MM-DD' (string) ou None.
    """
    m = _date_re.search(name)
    if not m:
        return None
    try:
        # validation simple
        d = datetime.fromisoformat(m.group(1)).date()
        return d.isoformat()
    except Exception:
        return None

def extract_title_from_html(path: Path) -> Optional[str]:
    try:
        txt = path.read_text(encoding="utf-8")
    except Exception:
        return None
    try:
        soup = BeautifulSoup(txt, "html.parser")
        # chercher div (ou tag) avec class qui contient arretify-arrete_title ou arretify_arrete_title
        title_tag = soup.find(attrs={"class": _title_class_re})
        if title_tag:
            title = title_tag.get_text(" ", strip=True)
            return title or None
    except Exception:
        return None
    return None

def run(input_dir: Optional[Path] = None, out_path: Optional[Path] = None):
    if input_dir is None:
        input_dir = INPUT_DIR
    if out_path is None:
        out_path = OUT_PATH

    files = sorted(input_dir.glob("*.html"))
    if not files:
        print("Aucun arrêté trouvé dans", input_dir)
        return

    items: List[Dict] = []
    for f in files:
        name = f.name
        date_str = extract_date_from_filename(name)
        title = extract_title_from_html(f)
        norm_title = normalize_text(title) if title else normalize_text(name)
        items.append({
            "file": name,
            "path": str(f),
            "date": date_str,
            "title": title,
            "norm_title": norm_title,
            "category": None,
            "notes": []
        })

    # trier : d'abord par date (les None en dernier), puis par nom
    def sort_key(it):
        return (it["date"] is None, it["date"] or "", it["file"])
    items = sorted(items, key=sort_key)

    # première règle simple : le premier (le plus ancien) devient 'autorisation'
    if items:
        items[0]["category"] = "autorisation"
        items[0]["confidence"] = "high"

    # règles rapides pour les autres (recherche dans le titre normalisé)
    for it in items[1:]:
        n = it["norm_title"]
        if "mise en demeure" in n or "mise-en-demeure" in n or "mise_en_demeure" in n:
            it["category"] = "inutile"
            it["confidence"] = "high"
        elif "garanties financières" in n or "garanties financieres" in n:
            it["category"] = "annexe"
            it["confidence"] = "high"
        else:
            it["category"] = "complementaire"
            it["confidence"] = "low"

    # sortie simplifiée
    out_list = []
    for it in items:
        out_list.append({
            "file": it["file"],
            "date": it["date"],
            "title": it.get("title"),
            "category": it["category"],
            "confidence": it.get("confidence"),
            "notes": it["notes"]
        })

    out_path.write_text(json.dumps(out_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote catalogue {out_path} ({len(out_list)} entrées)")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Pré-classification rapide des arrêtés (détection autorisation / inutiles)")
    p.add_argument("--input", "-i", help="dossier input (arretes_bruts)")
    p.add_argument("--out", "-o", help="fichier de sortie (catalogue_ap.json)")
    args = p.parse_args()
    in_dir = Path(args.input) if args.input else None
    out_file = Path(args.out) if args.out else None
    run(input_dir=in_dir, out_path=out_file)