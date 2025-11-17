import sys
import json
from pathlib import Path
import importlib.util
import re
from bs4 import BeautifulSoup, Tag

# charger le module existant
mod_path = Path(__file__).resolve().parents[0] / "scripts" / "1_prep" / "generer_structure_ap.py"
spec = importlib.util.spec_from_file_location("generer_structure_ap", str(mod_path))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

if len(sys.argv) >= 2:
    html_path = Path(sys.argv[1])
else:
    html_path = Path(r"c:\Users\marie.tcheng\Documents\consolidation\bench-ocapi\permis\data\0005804239\arretes_bruts\2009-12-08_AP_mistral.html")

if not html_path.exists():
    print("Fichier introuvable:", html_path)
    sys.exit(1)

text = html_path.read_text(encoding="utf-8")
soup = BeautifulSoup(text, "html.parser")
doc_id = html_path.stem

# 1) parse TOC
toc_found, toc_tag, toc_entries = mod._parse_toc_from_soup(soup)
print("TOC found:", toc_found)
print("TOC entries (count):", len(toc_entries))

# récupérer les lignes brutes du conteneur TOC (chaque enfant direct)
raw_lines = []
if toc_tag is not None:
    children = [ch for ch in toc_tag.find_all(recursive=False) if isinstance(ch, Tag)]
    for ch in children:
        txt = ch.get_text(" ", strip=True)
        if txt:
            raw_lines.append(txt)

# décider combien afficher : au plus 15, et pas plus que le nombre d'entrées détectées
to_show = min(15, len(toc_entries) if toc_entries is not None else 0, len(raw_lines))
print(f"Affichage des {to_show} premières lignes brutes du TOC (max 15, limité à toc_entries):")
for i in range(to_show):
    print(f"{i+1:02d}: {raw_lines[i]}")

# afficher résumé des entrées TOC (trim si trop nombreuses)
MAX_DISPLAY_ENTRIES = 15
print("\nTOC entries (trimmed):")
if len(toc_entries) <= MAX_DISPLAY_ENTRIES:
    print(json.dumps(toc_entries, ensure_ascii=False, indent=2))
else:
    # afficher seulement les premières clés
    small = {k: toc_entries[k] for k in list(toc_entries.keys())[:MAX_DISPLAY_ENTRIES]}
    print(f"(only first {MAX_DISPLAY_ENTRIES} entries shown out of {len(toc_entries)})")
    print(json.dumps(small, ensure_ascii=False, indent=2))

# 2) reconstruire l'arbre des sections comme extract_articles_from_html mais sans appeler la fusion
def _clean(s):
    if not s:
        return None
    import re
    return re.sub(r"\s+", " ", s).strip()

def make_node(sec, parent_uid=None):
    import re, uuid
    data_number = _clean(sec.get("data-number") or "")
    data_title = _clean(sec.get("data-title") or "")
    data_type = _clean(sec.get("data-type") or "")
    display = data_number or None

    inner_parts = []
    for c in sec.contents:
        if isinstance(c, Tag) and c.name == "section" and ("arretify-section" in (c.get("class") or [])):
            break
        inner_parts.append(str(c))
    inner_html = "".join(inner_parts).strip()
    inner_text = _clean(BeautifulSoup(inner_html, "html.parser").get_text(" ", strip=True))

    uid = f"{doc_id}::{uuid.uuid4().hex[:8]}"

    children = []
    for child_sec in sec.find_all("section", class_=lambda c: c and "arretify-section" in c, recursive=False):
        children.append(make_node(child_sec, parent_uid=uid))

    return {
        "uid": uid,
        "display_num": display,
        "titre": data_title,
        "type": data_type,
        "html": inner_html,
        "text": inner_text,
        "doc_id": doc_id,
        "parent_uid": parent_uid,
        "changes": [],
        "status": "active",
        "trace": [],
        "children": children,
    }

# sélectionner sections candidates (même logique que dans extract_articles_from_html)
candidates = []
all_secs = soup.find_all("section", class_=lambda c: c and "arretify-section" in c)
# toujours prendre toutes les sections top-level (évite de rater des 1.x)
for s in all_secs:
    if s.find_parent("section", class_=lambda c: c and "arretify-section" in c) is None:
        candidates.append(s)

if not candidates:
    candidates = all_secs

tree_before = [make_node(s) for s in candidates]

# construire index plat
index = {"by_number": {}, "by_uid": {}}
def walk_and_index(node):
    num = node.get("display_num")
    uid = node["uid"]
    index["by_uid"][uid] = {"parent_uid": node.get("parent_uid"), "titre": node.get("titre"), "type": node.get("type")}
    if num:
        index["by_number"][str(num)] = uid
    for c in node.get("children", []):
        walk_and_index(c)

for r in tree_before:
    walk_and_index(r)

print("\nTop-level roots before merge:", len(tree_before))
print("Index by_number sample (first 20):")
for i,k in enumerate(list(index["by_number"].items())[:20]):
    print(" ", k)

# 3) appeler la fonction de merge avec la TOC parsée
tree_after = mod._merge_toc_titles_into_tree(list(tree_before), dict(index), toc_entries, doc_id)

print("\nTop-level roots after merge:", len(tree_after))

# lister noeuds synthétiques ajoutés (trace contains synthetic_from_toc)
synths = []
def collect_synth(nodes):
    for n in nodes:
        if isinstance(n.get("trace"), list) and "synthetic_from_toc" in n.get("trace"):
            synths.append({"uid": n["uid"], "display_num": n.get("display_num"), "titre": n.get("titre"), "children_count": len(n.get("children", []))})
        collect_synth(n.get("children", []))
collect_synth(tree_after)

print("Synthetic TITRE nodes created:", len(synths))
if synths:
    print(json.dumps(synths, ensure_ascii=False, indent=2))

# afficher racines after : display_num/type/titre (limité à 50)
print("\nRoots after merge (display_num, type, titre) — up to 50:")
for r in tree_after[:50]:
    print(" -", r.get("display_num"), r.get("type"), r.get("titre"), "children:", len(r.get("children", [])))

# --- debug supplémentaire : lister display_num et rechercher préfixe '1' ---
def norm_num(s):
    if not s:
        return ""
    # remplacer NBSP, multiple spaces, trim
    return re.sub(r"\s+", "", s.replace("\u00A0", " ").strip())

all_nums = []
def collect_nums(nodes, path=None):
    if path is None:
        path = []
    for n in nodes:
        dn = n.get("display_num")
        nrm = norm_num(dn)
        path_str = ".".join(path + [dn or ""])
        all_nums.append((dn, nrm, n.get("uid"), path_str))
        collect_nums(n.get("children", []), path + [dn or ""])
collect_nums(tree_before)

print("\nTotal nodes with display_num (raw -> norm -> uid) sample (first 200):")
for i, t in enumerate(all_nums[:200]):
    print(f"{i:03d}: raw={t[0]!r} norm={t[1]!r} uid={t[2]} path={t[3]!r}")

# rechercher nodes correspondant au préfixe TOC '1' ou '1.'
prefix = "1"
matches = [t for t in all_nums if t[1].startswith(prefix)]
print(f"\nNodes whose normalized display_num startswith '{prefix}': {len(matches)}")
for m in matches:
    print(" - raw:", m[0], "norm:", m[1], "uid:", m[2], "path:", m[3])
# --- fin debug ---