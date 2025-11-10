"""
Générer la structure des arrêtés (étape 1).

- Parcours les fichiers HTML dans le dossier d'entrée.
- Pour chaque AP utile (filtré par catalogue_ap.json) extrait un arbre de sections
  (sections arretify). Pour chaque nœud on conserve :
    uid, display_num, titre (data-title), type (data-type),
    html (inner jusqu'à la 1re sous-section), html_full (section complète),
    text (texte direct), children (liste récursive).
- Écrit un fichier JSON par arrêté dans data/<id>/arretes_structure/<doc_id>.json
- Met à jour catalogue_ap.json en ajoutant structure_path et structure_generated_at.

Usage:
  python generer_structure_AP.py --input ".\permis\data\0005804239\arretes_bruts"
"""

#TODO : MEGA IMPORTANT : si table of contents notamment pour autorisation, faire matcher structure avec table of contents. (en cours)
#TODO: pb avec le 2024 : structure pas detectée.... annnexe !!! prendre la structure des annexes aussi. (à faire!!)
#TODO: une erreur ???
from pathlib import Path
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Tag
import re
import json
import uuid
from datetime import datetime, timezone

PROJECT_PERMIS = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_PERMIS / "data" / "0005804239" / "arretes_bruts"
JOURNAUX_DIR = PROJECT_PERMIS / "data" / "0005804239" / "journaux"
JOURNAUX_DIR.mkdir(parents=True, exist_ok=True)

# dossier de sorties : un JSON par arrêté
STRUCTURES_DIR = PROJECT_PERMIS / "data" / "0005804239" / "arretes_structure"
STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)

_date_re = re.compile(r"(\d{4}-\d{2}-\d{2})", flags=re.IGNORECASE)
_article_num_re = re.compile(r"\barticle\.?\s*[:\-]?\s*(\d+[A-Za-z0-9\-]*)", flags=re.IGNORECASE)


def _read_json(path: Path) -> Optional[Any]:
    """Lire un JSON depuis path, retourner None en cas d'erreur."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, obj: Any):
    """Écrire un objet JSON sur le disque (encodage UTF-8)."""
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def is_utile(file: Path) -> bool:
    """
    Vérifie si le fichier doit être traité.
    - Si catalogue_ap.json contient une entrée pour ce fichier avec category == "inutile" -> False.
    - Si le catalogue est absent ou l'entrée introuvable -> True (par défaut utile).
    """
    catalogue_path = JOURNAUX_DIR / "catalogue_ap.json"
    data = _read_json(catalogue_path)
    if not isinstance(data, list):
        return True
    for it in data:
        if not isinstance(it, dict):
            continue
        if it.get("file") == file.name:
            return it.get("category") != "inutile"
    return True


def _annotate_catalogue_with_structure(file_name: str, structure_relpath: str, generated_at_iso: str):
    """
    Met à jour (ou crée) une entrée dans catalogue_ap.json pour indiquer où se trouve
    le fichier de structure et quand il a été généré.
    - structure_relpath : chemin relatif depuis JOURNAUX_DIR (ex: "arretes_structure/<doc_id>.json")
    - generated_at_iso : timestamp ISO UTC
    """
    catalogue_path = JOURNAUX_DIR / "catalogue_ap.json"
    data = _read_json(catalogue_path)
    if not isinstance(data, list):
        data = []

    found = False
    for it in data:
        if isinstance(it, dict) and it.get("file") == file_name:
            it["structure_path"] = structure_relpath
            it["structure_generated_at"] = generated_at_iso
            found = True
            break
    if not found:
        # entrée minimale si absent
        data.append({
            "file": file_name,
            "category": "unknown",
            "structure_path": structure_relpath,
            "structure_generated_at": generated_at_iso,
            "notes": []
        })
    try:
        _write_json(catalogue_path, data)
    except Exception as e:
        print(f"Erreur écriture catalogue {catalogue_path}: {e}")


def extract_articles_from_html(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """
    Construire l'arbre de sections pour un HTML d'arrêté.
    - Cherche les <section class="arretify-section"> de plus haut niveau.
    - Pour chaque section, crée un noeud contenant metadata + inner HTML (jusque 1re sous-section)
      et children (sous-sections directes).
    - Retourne la liste de nœuds racines.
    """
    def _clean(s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        return re.sub(r"\s+", " ", s).strip()

    soup = BeautifulSoup(text, "html.parser")

    # --- new: detect table of contents and record its position in the original text
    toc_tag = soup.find("div", class_=lambda c: c and "arretify-table_of_contents" in c)
    toc_lines = []
    toc_titles = {}  # number -> title text (for TITRE entries)
    toc_found = False
    if toc_tag:
        toc_found = True
        raw_lines = [ln.strip() for ln in toc_tag.get_text("\n").splitlines() if ln.strip()]
        for ln in raw_lines:
            m = re.match(r"(?i)^\s*TITRE\s*(\d+)\s*(?:[-–—]\s*(.*?))?(?:\s*\.{2,}\s*\d+)?\s*$", ln)
            if m:
                num = m.group(1)
                title = (m.group(2) or "").strip()
                if title == "":
                    title = re.sub(r"\.{2,}\s*\d+\s*$", "", ln).strip()
                toc_titles[str(num)] = title
        toc_lines = raw_lines
    # debug/log: permite vérifier en sortie que la TOC a été trouvée et combien de TITRE parsés
    print(f"extract_articles_from_html: toc_found={toc_found} toc_titles={sorted(toc_titles.keys())}")
    # tri numérique pour affichage lisible
    print(f"extract_articles_from_html: toc_found={toc_found} toc_titles={sorted(toc_titles.keys(), key=int) if toc_titles else []}")
 
    def make_node(sec: Tag, parent_uid: Optional[str] = None) -> Dict[str, Any]:
        data_number = _clean(sec.get("data-number") or "")
        data_title = _clean(sec.get("data-title") or "")
        data_type = _clean(sec.get("data-type") or "")
        display = data_number or None

        # inner_html : contenu jusqu'à la première sous-section arretify (évite duplication)
        inner_parts = []
        for c in sec.contents:
            if isinstance(c, Tag) and c.name == "section" and ("arretify-section" in (c.get("class") or [])):
                break
            inner_parts.append(str(c))
        inner_html = "".join(inner_parts).strip()
        inner_text = _clean(BeautifulSoup(inner_html, "html.parser").get_text(" ", strip=True))

        uid = f"{doc_id}::{uuid.uuid4().hex[:8]}"

        # construire enfants directs
        children = []
        for child_sec in sec.find_all("section", class_=lambda c: c and "arretify-section" in c, recursive=False):
            children.append(make_node(child_sec, parent_uid=uid))

        return {
            "uid": uid,
            "display_num": display,
            "titre": data_title,
            "type": data_type,
            "html": inner_html,      # inner HTML jusqu'à la 1re sous-section
            "text": inner_text,
            "doc_id": doc_id,
            "parent_uid": parent_uid,   # <- lien vers le parent
            "changes": [],              # <- liste d'opérations appliquées à ce nœud
            "status": "active",
            "trace": [],                # (optionnel) courts événements locaux
            "children": children
        }

    # trouver sections candidates — si TOC trouvé, ignorer celles avant la TOC dans le HTML original
    candidates = []
    all_secs = soup.find_all("section", class_=lambda c: c and "arretify-section" in c)
    if toc_found:
        # robust: prendre les sections qui apparaissent dans le DOM _après_ le tag TOC
        following_secs = []
        seen = set()
        for el in toc_tag.next_elements:
            if isinstance(el, Tag) and el.name == "section" and ("arretify-section" in (el.get("class") or [])):
                # éviter doublons
                if id(el) not in seen:
                    seen.add(id(el))
                    following_secs.append(el)
        for s in following_secs:
            if s.find_parent("section", class_=lambda c: c and "arretify-section" in c) is None:
                candidates.append(s)
        print(f"extract_articles_from_html: found {len(candidates)} top-level sections after TOC")
    else:
        for s in all_secs:
            if s.find_parent("section", class_=lambda c: c and "arretify-section" in c) is None:
                candidates.append(s)
 
    # fallback si aucune racine trouvée
    if not candidates:
        candidates = all_secs

    tree = [make_node(s) for s in candidates]

    # construire index plat pour ce doc : data-number -> uid, uid -> parent_uid, uid -> titre/type
    index = {"by_number": {}, "by_uid": {}}
    def walk_and_index(node):
        num = node.get("display_num")
        uid = node["uid"]
        index["by_uid"][uid] = {"parent_uid": node.get("parent_uid"), "titre": node.get("titre"), "type": node.get("type")}
        if num:
            index["by_number"][str(num)] = uid
        for c in node.get("children", []):
            walk_and_index(c)
    for root in tree:
        walk_and_index(root)

    # --- new: if TOC contained TITRE entries, ensure TITRE nodes exist and attach matching roots
    if toc_titles:
        # debug: quels numéros de racines existent avant réparentage
        present_numbers = sorted(list(index["by_number"].keys()), key=lambda x: int(x) if x.isdigit() else x)
        print(f"extract_articles_from_html: existing top-level display_nums before toc merge: {present_numbers}")
        # for deterministic order, iterate sorted keys (numérique)
        for num in sorted(toc_titles.keys(), key=lambda x: int(x)):
            num_str = str(num)
            # si un noeud existe déjà pour ce numéro mais n'est pas de type 'titre',
            # on crée un noeud TITRE synthétique et on reparentera les racines qui commencent par "num."
            need_synthetic = False
            if num_str in index["by_number"]:
                uid = index["by_number"][num_str]
                existing_type = index["by_uid"].get(uid, {}).get("type")
                existing_title = index["by_uid"].get(uid, {}).get("titre")
                # si le noeud existe mais n'est pas un titre, on veut créer le titre synthétique
                if existing_type != "titre":
                    need_synthetic = True
                else:
                    # si c'est déjà un titre mais sans titre textuel, on complète
                    if not existing_title:
                        # find node in tree and set titre
                        def set_title_in_tree(nodes):
                            for n in nodes:
                                if n["uid"] == uid:
                                    n["titre"] = toc_titles[num_str] or n.get("titre")
                                    return True
                                if set_title_in_tree(n.get("children", [])):
                                    return True
                            return False
                        set_title_in_tree(tree)
            else:
                need_synthetic = True

            if need_synthetic:
                new_uid = f"{doc_id}::{uuid.uuid4().hex[:8]}"
                new_node = {
                    "uid": new_uid,
                    "display_num": num_str,
                    "titre": toc_titles[num_str],
                    "type": "titre",
                    "html": "",
                    "text": toc_titles[num_str],
                    "doc_id": doc_id,
                    "parent_uid": None,
                    "changes": [],
                    "status": "active",
                    "trace": ["synthetic_from_toc"],
                    "children": []
                }
                remaining_roots = []
                moved_count = 0
                for r in tree:
                    rnum = (r.get("display_num") or "")
                    # reparent children that belong under this titre (1.*)
                    if rnum.startswith(num_str + ".") or rnum == num_str:
                        r["parent_uid"] = new_uid
                        new_node["children"].append(r)
                        moved_count += 1
                    else:
                        remaining_roots.append(r)
                # place new node where appropriate (append to keep order)
                remaining_roots.append(new_node)
                tree = remaining_roots
                index["by_uid"][new_uid] = {"parent_uid": None, "titre": new_node["titre"], "type": "titre"}
                index["by_number"][num_str] = new_uid
                print(f"extract_articles_from_html: created synthetic TITRE {num_str} (moved {moved_count} roots)")

    # écrire index à côté du fichier structure
    index_path = STRUCTURES_DIR / f"{doc_id}.index.json"
    _write_json(index_path, index)

    return tree


def run(input_dir: Optional[Path] = None):
    """
    Parcours les fichiers HTML du dossier input, génère un JSON de structure par arrêté
    et met à jour le catalogue (structure_path + structure_generated_at).
    """
    if input_dir is None:
        input_dir = DEFAULT_INPUT

    files = sorted(Path(input_dir).glob("*.html"))
    processed = 0
    skipped = 0
    errors = 0

    for f in files:
        if not is_utile(f):
            print(f"Skip inutile AP: {f.name}")
            skipped += 1
            continue

        try:
            txt = f.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Erreur lecture {f.name}: {e}")
            errors += 1
            continue

        doc_id = f.stem
        try:
            articles = extract_articles_from_html(txt, doc_id)
        except Exception as e:
            print(f"Erreur parsing {f.name}: {e}")
            errors += 1
            continue

        # document final : ne contient plus is_base_candidate (inutile ici)
        doc = {
            "file": f.name,
            "doc_id": doc_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_articles": len(articles),
            "articles": articles,
            "notes": []
        }

        out_file = STRUCTURES_DIR / f"{doc_id}.json"
        try:
            out_file.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            # annotation simple dans le catalogue : chemin relatif depuis JOURNAUX_DIR
            rel_path = str(Path("arretes_structure") / f"{doc_id}.json")
            gen_at = doc["generated_at"]
            _annotate_catalogue_with_structure(f.name, rel_path, gen_at)
            processed += 1
        except Exception as e:
            print(f"Erreur écriture {out_file}: {e}")
            errors += 1

    print(f"Done. processed={processed} skipped={skipped} errors={errors} total={len(files)}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Générer structure par AP (écrit un JSON par arrêté)")
    p.add_argument("--input", "-i", help="dossier input .html (arretes_bruts)")
    args = p.parse_args()
    run(input_dir=Path(args.input) if args.input else None)