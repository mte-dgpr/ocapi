import json
import sys
from typing import Any

PATH_DEFAULT = r"c:\Users\marie.tcheng\Documents\consolidation\bench-ocapi\permis\data\0005804239\journaux\base.json"

def short(s: Any, n=60):
    if s is None: 
        return "None"
    t = str(s)
    return (t[:n] + "…") if len(t) > n else t

def node_desc(node: dict):
    # retourne description courte d'un "article"/"section"
    parts = []
    for k in ("uid","display_num","titre","type"):
        v = node.get(k)
        if v:
            parts.append(f"{k}={short(v,40)}")
    if "html" in node:
        parts.append(f"html_len={len(node.get('html') or '')}")
    if "html_full" in node:
        parts.append(f"html_full_len={len(node.get('html_full') or '')}")
    if "text" in node:
        parts.append(f"text_len={len(node.get('text') or '')}")
    return " | ".join(parts) if parts else "(no meta)"

def print_node(node: dict, indent: str, depth: int, max_depth: int):
    if depth > max_depth:
        print(indent + "…")
        return
    desc = node_desc(node)
    children = node.get("children") or []
    print(f"{indent}- {desc}  (children={len(children)})")
    for i, ch in enumerate(children):
        print_node(ch, indent + "    ", depth + 1, max_depth)

def print_document(doc: dict, max_depth: int):
    file = doc.get("file") or doc.get("doc_id") or "<doc?>"
    print(f"Document: {file}  (n_articles={doc.get('n_articles', '?')})")
    articles = doc.get("articles") or []
    for idx, art in enumerate(articles, 1):
        header = f" Article {idx}"
        if isinstance(art, dict):
            print(header + ":")
            print_node(art, "    ", 1, max_depth)
        else:
            print(f" {header}: (empty/non-dict)")

def main(path: str, max_depth: int = 6):
    try:
        with open(path, "r", encoding="utf-8") as f:
            j = json.load(f)
    except Exception as e:
        print("Erreur lecture JSON:", e)
        return
    docs = j.get("documents") or []
    print(f"Fichier: {path}")
    print(f"Documents: {len(docs)}")
    for doc in docs:
        print("-" * 60)
        print_document(doc, max_depth)

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else PATH_DEFAULT
    md = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    main(p, md)