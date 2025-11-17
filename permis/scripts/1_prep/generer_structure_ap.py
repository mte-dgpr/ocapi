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
  python permis/scripts/1_prep/generer_structure_ap.py
Options :
  --input DIR  ; dossier contenant les *.mapped.json
  --out DIR    ; dossier de sortie pour graphes (par défaut data/.../graphs)
"""

# TODO : tout supprimer !!!!!!!:'((((
# TODO : MEGA IMPORTANT : si table of contents notamment pour autorisation, faire matcher structure avec table of contents. (en cours)
# TODO: pb avec le 2024 : structure pas detectée.... annnexe !!! prendre la structure des annexes aussi. (à faire!!)
# TODO: une erreur ???
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


def _annotate_catalogue_with_structure(
    file_name: str, structure_relpath: str, generated_at_iso: str
):
    """
    Met à jour (ou crée) une entrée dans catalogue_ap.json pour indiquer où se trouve
    le fichier de structure et quand il a été généré.
    - structure_relpath : chemin relatif depuis JOURNAUX_DIR (ex: "arretes_structure/<doc_id>.json")
    - generated_at_iso : timestamp ISO UTC
    """
    # TODO : décider si cette fonction utile ou non.
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
        data.append(
            {
                "file": file_name,
                "category": "unknown",
                "structure_path": structure_relpath,
                "structure_generated_at": generated_at_iso,
                "notes": [],
            }
        )
    try:
        _write_json(catalogue_path, data)
    except Exception as e:
        print(f"Erreur écriture catalogue {catalogue_path}: {e}")


def _parse_toc_from_soup(soup: BeautifulSoup):
    """
    Détecte la table des matières dans le soup et retourne (toc_found, toc_tag, toc_entries).
    Comportement ligne-par-ligne : pour chaque <div> enfant du conteneur TOC,
    on repère le premier nombre (ex: "1" ou "1.1.2"), le mot immédiatement avant
    ce nombre est considéré comme le type (TITRE/CHAPITRE/Article si détectable),
    et tout ce qui suit est le titre. Retourne toc_entries num -> {"num","titre","type"}.
    """
    toc_tag = soup.find("div", class_=lambda c: c and "arretify-table_of_contents" in c)
    toc_entries: Dict[str, Dict[str, str]] = {}
    toc_found = False
    if toc_tag:
        toc_found = True
        # chaque entrée est attendue dans un <div> enfant — on les traite dans l'ordre
        children = [ch for ch in toc_tag.find_all(recursive=False) if isinstance(ch, Tag)]
        for ch in children:
            txt = ch.get_text(" ", strip=True)
            if not txt:
                continue
            

            # trouver le premier numéro (peut contenir des points, ex "1" ou "1.2.3")
            m_num = re.search(r"([0-9]+(?:\.[0-9]+)*)", txt)
            if not m_num:
                continue
            num = m_num.group(1)

            # portion avant le numéro -> dernier token alphabétique = étiquette possible
            before = txt[: m_num.start()].strip()
            last_token = None
            if before:
                toks = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ\-']+", before)
                if toks:
                    last_token = toks[-1].lower()

            # normaliser le type
            if last_token and "titre" in last_token:
                typ = "titre"
            elif last_token and "chap" in last_token:
                typ = "chapitre"
            elif last_token and last_token.startswith("art"):
                typ = "article"
            else:
                typ = "unknown"

            # portion après le numéro -> libellé (nettoyage séparateurs et pagination)
            after = txt[m_num.end() :].strip()
            after = re.sub(r"^[\s\-\–\—\:\.]+", "", after)  # retirer séparateurs initiaux
            after = re.sub(r"\.{2,}\s*\d+\s*$", "", after).strip()  # retirer "..... 5"
            title = after if after != "" else None

            # conserver la première occurrence pour un numéro donné
            if str(num) not in toc_entries:
                toc_entries[str(num)] = {"num": str(num), "titre": title, "type": typ}

    return toc_found, toc_tag, toc_entries


def _merge_toc_titles_into_tree(tree: List[Dict[str, Any]], index: Dict[str, Any], toc_entries: Dict[str, Dict[str, str]], doc_id: str):
    """
    Fusionner la TOC dans l'arbre :
    - pour chaque entrée TOC (num -> {num,titre,type}) :
      * si un nœud avec ce num existe dans index -> appliquer le titre si manquant ;
      * sinon créer un nœud synthétique pour ce num et y rattacher les nœuds existants
        dont display_num == num ou display_num.startswith(num + ".") :
        - si un parent (préfixe) existe, insérer comme enfant de ce parent ;
        - sinon insérer au niveau racine (après avoir retiré les nœuds déplacés).
    """
    if not toc_entries:
        return tree

    def sort_key_num(s: str):
        parts = [p for p in s.split(".") if p != ""]
        try:
            return [int(p) for p in parts]
        except Exception:
            return [int(re.sub(r"\D", "", p)) if re.search(r"\d", p) else 0 for p in parts]

    # helpers pour parcourir / trouver / modifier l'arbre
    def find_node_and_container_by_display(nodes: List[Dict[str, Any]], display_num: str, container=None):
        """
        Retourne (node, parent_node_or_None, container_list) où container_list est la liste
        (soit tree (roots) soit parent['children']) contenant ce node (utile pour suppression).
        """
        for n in nodes:
            if (n.get("display_num") or "") == display_num:
                return n, container, nodes
            res_node, res_parent, res_container = find_node_and_container_by_display(n.get("children", []), display_num, n)
            if res_node:
                return res_node, res_parent, res_container
        return None, None, None

    def remove_and_collect_by_prefix_recursive(container_list: List[Dict[str, Any]], prefix: str):
        """
        Parcourt récursivement container_list et retire (in-place) toutes les nodes dont
        display_num == prefix ou display_num.startswith(prefix + ".").
        Retourne la liste complète des noeuds retirés.
        """
        moved = []
        i = 0
        while i < len(container_list):
            n = container_list[i]
            dn = n.get("display_num") or ""
            if dn == prefix or dn.startswith(prefix + "."):
                moved.append(n)
                # retirer l'élément courant
                container_list.pop(i)
                # ne pas incrémenter i (nouvel élément à cette position)
                continue
            # sinon, descendre dans les enfants (on peut déplacer des enfants profonds)
            child_moved = remove_and_collect_by_prefix_recursive(n.get("children", []), prefix)
            if child_moved:
                # ajouter les enfants retirés à la liste moved
                moved.extend(child_moved)
            i += 1
        return moved

    # construire un mapping local des display_num -> uid en partant de index (si existant)
    local_by_number = dict(index.get("by_number", {}))

    # itérer toutes les entrées TOC triées numériquement
    for num in sorted(toc_entries.keys(), key=sort_key_num):
        num_str = str(num)
        entry = toc_entries.get(num_str) or {}
        label = entry.get("titre") if isinstance(entry, dict) else None
        typ = (entry.get("type") if isinstance(entry, dict) else "unknown") or "unknown"

        applied = False
        # 1) si index contient le numéro, tenter d'appliquer le titre au nœud existant
        if num_str in local_by_number:
            uid = local_by_number[num_str]
            node = None
            def find_by_uid(nodes):
                nonlocal node
                for n in nodes:
                    if n.get("uid") == uid:
                        node = n
                        return True
                    if find_by_uid(n.get("children", [])):
                        return True
                return False
            find_by_uid(tree)
            if node:
                if not node.get("titre") and label:
                    node["titre"] = label
                    print(f"merge: set title for existing uid {uid} -> {label!r}")
                applied = True
            else:
                # index stale : essayer de trouver par display_num directement
                found_node, found_parent, found_container = find_node_and_container_by_display(tree, num_str)
                if found_node:
                    if not found_node.get("titre") and label:
                        found_node["titre"] = label
                        print(f"merge: set title for display_num {num_str} -> {label!r}")
                    local_by_number[num_str] = found_node.get("uid")
                    applied = True

        else:
            # 2) essayer de trouver un nœud existant par display_num
            found_node, found_parent, found_container = find_node_and_container_by_display(tree, num_str)
            if found_node:
                if not found_node.get("titre") and label:
                    found_node["titre"] = label
                    print(f"merge: set title for display_num {num_str} -> {label!r}")
                local_by_number[num_str] = found_node.get("uid")
                applied = True

        # 3) si pas appliqué et c'est un TITRE, créer un nœud synthétique et reparenter les enfants correspondants
        if not applied and typ == "titre":
            new_uid = f"{doc_id}::{uuid.uuid4().hex[:8]}"
            new_node = {
                "uid": new_uid,
                "display_num": num_str,
                "titre": label,
                "type": "titre",
                "html": "",
                "text": label,
                "doc_id": doc_id,
                "parent_uid": None,
                "changes": [],
                "status": "active",
                "trace": ["synthetic_from_toc"],
                "children": [],
            }
            # déterminer parent potentiel (préfixe sans la dernière composante)
            if "." in num_str:
                parent_num = ".".join(num_str.split(".")[:-1])
            else:
                parent_num = None

            moved = []
            if parent_num:
                # essayer d'attacher sous parent si existant ; sinon agir sur racines
                parent_node, p_parent, p_container = find_node_and_container_by_display(tree, parent_num)
                if parent_node:
                    # retirer récursivement tous les nodes correspondant au préfixe dans parent_node.children
                    moved = remove_and_collect_by_prefix_recursive(parent_node["children"], num_str)
                    for m in moved:
                        m["parent_uid"] = new_uid
                        new_node["children"].append(m)
                    # insérer new_node dans parent_node.children (à la fin)
                    parent_node["children"].append(new_node)
                    new_node["parent_uid"] = parent_node.get("uid")
                else:
                    # pas de parent trouvé : reparenter depuis tout l'arbre racine
                    moved = remove_and_collect_by_prefix_recursive(tree, num_str)
                    for m in moved:
                        m["parent_uid"] = new_uid
                        new_node["children"].append(m)
                    tree.append(new_node)
            else:
                # top-level titre : reparenter depuis tout l'arbre racine
                moved = remove_and_collect_by_prefix_recursive(tree, num_str)
                for m in moved:
                    m["parent_uid"] = new_uid
                    new_node["children"].append(m)
                tree.append(new_node)

            moved_count = len(moved)
            local_by_number[num_str] = new_uid
            index["by_uid"][new_uid] = {"parent_uid": new_node.get("parent_uid"), "titre": new_node["titre"], "type": "titre"}
            index["by_number"][num_str] = new_uid
            print(f"extract_articles_from_html: created synthetic TITRE {num_str} (moved {moved_count} nodes) -> moved: {[m.get('display_num') for m in moved]}")

    return tree
# --- fin refactor TOC ---------------------------------------------------------------


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
    toc_found, toc_tag, toc_entries = _parse_toc_from_soup(soup)

    # debug/log: permite vérifier en sortie que la TOC a été trouvée et combien de TITRE parsés
    print(
        f"extract_articles_from_html: toc_found={toc_found} toc_entries={sorted(toc_entries.keys())}"
    )
    # tri numérique pour affichage lisible
    print(
        f"extract_articles_from_html: toc_found={toc_found} toc_entries={sorted(toc_entries.keys(), key=int) if toc_entries else []}"
    )

    def make_node(sec: Tag, parent_uid: Optional[str] = None) -> Dict[str, Any]:
        data_number = _clean(sec.get("data-number") or "")
        data_title = _clean(sec.get("data-title") or "")
        data_type = _clean(sec.get("data-type") or "")
        display = data_number or None

        # inner_html : contenu jusqu'à la première sous-section arretify (évite duplication)
        inner_parts = []
        for c in sec.contents:
            if (
                isinstance(c, Tag)
                and c.name == "section"
                and ("arretify-section" in (c.get("class") or []))
            ):
                break
            inner_parts.append(str(c))
        inner_html = "".join(inner_parts).strip()
        inner_text = _clean(BeautifulSoup(inner_html, "html.parser").get_text(" ", strip=True))

        uid = f"{doc_id}::{uuid.uuid4().hex[:8]}"

        # construire enfants directs
        children = []
        for child_sec in sec.find_all(
            "section", class_=lambda c: c and "arretify-section" in c, recursive=False
        ):
            children.append(make_node(child_sec, parent_uid=uid))

        return {
            "uid": uid,
            "display_num": display,
            "titre": data_title,
            "type": data_type,
            "html": inner_html,  # inner HTML jusqu'à la 1re sous-section
            "text": inner_text,
            "doc_id": doc_id,
            "parent_uid": parent_uid,  # <- lien vers le parent
            "changes": [],  # <- liste d'opérations appliquées à ce nœud
            "status": "active",
            "trace": [],  # (optionnel) courts événements locaux
            "children": children,
        }

    # trouver sections candidates — si TOC trouvé, ignorer celles avant la TOC dans le HTML original
    candidates = []
    all_secs = soup.find_all("section", class_=lambda c: c and "arretify-section" in c)
    if toc_found:
        # robust: prendre les sections qui apparaissent dans le DOM _après_ le tag TOC
        following_secs = []
        seen = set()
        for el in toc_tag.next_elements:
            if (
                isinstance(el, Tag)
                and el.name == "section"
                and ("arretify-section" in (el.get("class") or []))
            ):
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
        index["by_uid"][uid] = {
            "parent_uid": node.get("parent_uid"),
            "titre": node.get("titre"),
            "type": node.get("type"),
        }
        if num:
            index["by_number"][str(num)] = uid
        for c in node.get("children", []):
            walk_and_index(c)

    for root in tree:
        walk_and_index(root)

    # --- new: if TOC contained TITRE entries, ensure TITRE nodes exist and attach matching roots
    if toc_entries:
        tree = _merge_toc_titles_into_tree(tree, index, toc_entries, doc_id)

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
            "notes": [],
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
