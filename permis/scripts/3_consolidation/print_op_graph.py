from pathlib import Path
import argparse
import pickle
import re
import networkx as nx
from typing import Optional

DEFAULT_GPKL = (
    Path(__file__).resolve().parents[3]
    / "permis"
    / "data"
    / "0005804239"
    / "graphs"
    / "op_graph.gpickle"
)


def _load_graph(p: Path):
    with open(p, "rb") as fh:
        return pickle.load(fh)


def _year_from_doc(
    doc: Optional[str], node_name: Optional[str] = None, attrs: Optional[dict] = None
) -> Optional[str]:
    """
    Tente d'extraire une année (YYYY) à partir de plusieurs sources :
    - champ doc (souvent 'YYYY-MM-DD_...'),
    - node_name (clé du noeud),
    - attrs['uid'] ou attrs['doc'] si présents.
    Retourne 'YYYY' ou None.
    """
    candidates = []
    if doc:
        candidates.append(str(doc))
    if attrs:
        try:
            if attrs.get("doc"):
                candidates.append(str(attrs.get("doc")))
            if attrs.get("uid"):
                candidates.append(str(attrs.get("uid")))
        except Exception:
            pass
    if node_name:
        candidates.append(str(node_name))

    for c in candidates:
        # chercher YYYY-MM-DD puis YYYY anywhere
        m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", c)
        if m_iso:
            return m_iso.group(1)
        m_year = re.search(r"\b(19|20)\d{2}\b", c)
        if m_year:
            return m_year.group(0)
    return None


def _node_label(n, attrs):
    """
    Label affiché : (display_num | year)
    - display_num provient de attrs['ref'] ou attrs['uid'] ou la clé n.
    - year extrait via _year_from_doc (doc field / node name / uid).
    """
    ref = None
    if isinstance(attrs, dict):
        ref = attrs.get("ref") or attrs.get("uid")
    if not ref:
        ref = str(n)
    # raccourcir uid-like "doc::uid" pour l'affichage du ref
    if isinstance(ref, str) and "::" in ref:
        # si c'est du style doc::uid, on préfère afficher la partie après :: (numéro court)
        parts = ref.split("::")
        ref_display = parts[-1]
    else:
        ref_display = ref

    # doc candidate : attrs['doc'] sinon clé n split "::"[0]
    doc_candidate = None
    if isinstance(attrs, dict):
        doc_candidate = attrs.get("doc")
    if not doc_candidate and isinstance(n, str) and "::" in n:
        doc_candidate = n.split("::")[0]

    year = _year_from_doc(doc_candidate, node_name=n, attrs=attrs) or "????"
    return f"({ref_display} | {year})"


def _dfs_paths_from_root(G, root, max_depth=50):
    stack = [(root, [root])]
    while stack:
        node, path = stack.pop()
        succ = list(G.successors(node))
        if not succ:
            yield path
        else:
            for s in succ:
                if s in path:
                    continue
                if len(path) >= max_depth:
                    yield path
                else:
                    stack.append((s, path + [s]))


def pretty_print_graph(G: nx.DiGraph, top_n_components: int = 10, max_paths_per_comp: int = 50):
    comps = sorted(list(nx.weakly_connected_components(G)), key=lambda c: -len(c))
    for i, comp in enumerate(comps[:top_n_components], start=1):
        sub = G.subgraph(comp).copy()
        print(
            f"\nComponent {i} (size={sub.number_of_nodes()} nodes, edges={sub.number_of_edges()}):"
        )
        # find roots (in_degree == 0)
        roots = [n for n in sub.nodes() if sub.in_degree(n) == 0]
        if not roots:
            roots = list(sub.nodes())[:1]
        printed = 0
        for r in roots:
            for path in _dfs_paths_from_root(sub, r):
                labels = [_node_label(n, sub.nodes[n]) for n in path]
                print("  " + " --> ".join(labels))
                printed += 1
                if printed >= max_paths_per_comp:
                    print("  ... (paths truncated)")
                    break
            if printed >= max_paths_per_comp:
                break


def main():
    p = argparse.ArgumentParser(description="Pretty-print op graph paths (data-number | year)")
    p.add_argument("--graph", "-g", help="gpickle path", default=str(DEFAULT_GPKL))
    p.add_argument(
        "--top", type=int, default=10, help="nombre de composantes à afficher (par taille)"
    )
    p.add_argument("--max-paths", type=int, default=50, help="max chemins affichés par composante")
    args = p.parse_args()

    gp = Path(args.graph)
    if not gp.exists():
        print("Graph file not found:", gp)
        return
    G = _load_graph(gp)
    pretty_print_graph(G, top_n_components=args.top, max_paths_per_comp=args.max_paths)


if __name__ == "__main__":
    main()
