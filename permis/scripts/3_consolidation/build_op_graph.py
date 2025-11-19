"""
Construire un graphe de dépendances d'opérations à partir des fichiers
operations_mapped/*.mapped.json.

- noeud : article (préférer uid si présent, sinon fallback "doc::ref")
- arête : opération dirigée source -> target, attributs = op_id, type, source_file, target_file
- sortie : graphml + gpickle + résumé console

Usage (depuis la racine du repo) :
  python permis/scripts/3_consolidation/build_op_graph.py
Options :
  --input DIR  ; dossier contenant les *.mapped.json
  --out DIR    ; dossier de sortie pour graphes (par défaut data/.../graphs)
"""

# TODO: comment gérer les parents enfant dans le graphe au niveau des dépendances

# TODO: Comment gérer edges avec même src / target ? adapter en multigraph ?



from pathlib import Path
import json
import argparse
from typing import Optional, Dict, Any
import networkx as nx

from permis.scripts.constants import PROJECT_ROOT
from permis.scripts.utils.io_utils import read_json
from permis.scripts.types import OPERATION_EDGE_ATTRS, NodeId, Operation, OperationType
from permis.scripts.utils.utils import make_id, IdCounter

_OPERATION_ID_COUNTER = IdCounter()
DEFAULT_MAPPED_DIR = PROJECT_ROOT / "permis" / "data" / "0005804239" / "operations_mapped"
DEFAULT_OUT_DIR = PROJECT_ROOT / "permis" / "data" / "0005804239" / "graphs"
DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)


def add_node(G: nx.MultiDiGraph, node_id: NodeId):
    # TODO : ajouter le contenu si possible
    if not G.has_node(node_id):
        G.add_node(node_id)


def add_edge(G: nx.MultiDiGraph, operation: Operation):
    edge_data = operation.model_dump(include=OPERATION_EDGE_ATTRS)
    # TODO : ne fonctionne pas 
    G.add_edge(operation.source_uid, operation.target_uid, **edge_data)


def build_graph(ops: list[Operation]) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for op in ops:
        add_node(G, op.source_uid)
        add_node(G, op.target_uid)
        add_edge(G, op)
    return G


def convert_operations_raw_to_operations(raw_operations: list[Dict[str, Any]]) -> list[Operation]:
    operations = []
    for op in raw_operations:
        src_file = op.get("source_file")
        src_ref = op.get("source_article") or op.get("article")
        src_uid = op.get("source_uid")

        tgt_file = (
            op.get("target_file") or op.get("target_arrete") or op.get("target_source_file")
        )
        tgt_ref = op.get("target_article") or op.get("target") or op.get("target_ref")
        tgt_uid = op.get("target_uid")

        src_node = _node_key_from_op(src_file, src_ref, src_uid)
        tgt_node = _node_key_from_op(tgt_file, tgt_ref, tgt_uid)

        # TODO: checker que make_id c'est bien l'ordre chrono des operations.

        operation = Operation(
            id=make_id(_OPERATION_ID_COUNTER),
            source_uid=src_node,
            target_uid=tgt_node,
            op_type=OperationType(op["modification_type"]),
            operand=op.get("new_content_html", None),
            sub_target=op.get("target_element", None),
        )
        operations.append(operation)
    return operations


def build_graph_from_mapped_dir(mapped_dir: Path) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    files = sorted(mapped_dir.glob("*.mapped.json"))
    all_operations = []
    for f in files:
        data = read_json(f)
        ops = data.get("operations") or []
        operations = convert_operations_raw_to_operations(ops)
        all_operations.extend(operations)
    return build_graph(all_operations)


def _node_key_from_op(
    side_file: Optional[str], side_ref: Optional[str], side_uid: Optional[str]
) -> str:
    """Retourne l'identifiant du noeud à utiliser : uid si présent, sinon doc::ref."""
    if side_uid:
        return str(side_uid)
    doc = Path(side_file).stem if side_file else "unknown"
    ref = str(side_ref) if side_ref else "?"
    return f"{doc}::{ref}"


def summarize_and_write(G: nx.DiGraph, out_dir: Path, name_stem: str = "op_graph"):
    out_dir.mkdir(parents=True, exist_ok=True)
    graphml_path = out_dir / f"{name_stem}.graphml"

    # essayer d'écrire GraphML sur une version sanitizée
    wrote_graphml = False
    try:
        nx.write_graphml(G, graphml_path)
        wrote_graphml = True
    except Exception as e:
        print("warning: write_graphml failed:", e)
        wrote_graphml = False

    # résumé
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    weak_cc = list(nx.weakly_connected_components(G))
    comp_sizes = sorted([len(c) for c in weak_cc], reverse=True)
    n_comps = len(weak_cc)

    print(f"Graph written: nodes={n_nodes} edges={n_edges} components={n_comps}")
    if comp_sizes:
        top = comp_sizes[:10]
        print(f"Top component sizes (desc): {top} (total comps {n_comps})")
    print(
        f"graphml: {graphml_path if wrote_graphml else 'not_written'}"
    )
    return {"nodes": n_nodes, "edges": n_edges, "components": n_comps, "top_comp_sizes": comp_sizes}


def main(mapped_dir: Path, out_dir: Path):
    if not mapped_dir.exists():
        print("mapped_dir not found:", mapped_dir)
        return
    G = build_graph_from_mapped_dir(mapped_dir)
    stats = summarize_and_write(G, out_dir)
    # écrire un résumé JSON simple
    summary_path = out_dir / "op_graph_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print("Summary written to", summary_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Build operation dependency graph from operations_mapped"
    )
    p.add_argument("--input", "-i", help="mapped ops dir", default=str(DEFAULT_MAPPED_DIR))
    p.add_argument("--out", "-o", help="output graphs dir", default=str(DEFAULT_OUT_DIR))
    args = p.parse_args()
    main(Path(args.input), Path(args.out))
