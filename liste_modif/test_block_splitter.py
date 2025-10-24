import sys
import argparse
from pathlib import Path
import json
import traceback

# on importe la fonction existante (réutilisation maximum du code déjà présent)
from block_splitter import extract_arrete_blocs

def save_blocks(input_html: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        blocks = extract_arrete_blocs(str(input_html))
    except Exception as e:
        print("Erreur lors de l'exécution de extract_arrete_blocs :", e)
        traceback.print_exc()
        return 1

    # normalize return: si la fonction renvoie une string -> un seul bloc
    if isinstance(blocks, str):
        blocks = [blocks]
    # si None ou autre -> forcer vide
    if blocks is None:
        blocks = []

    print(f"{len(blocks)} block(s) obtenus pour {input_html.name}")

    for i, b in enumerate(blocks):
        try:
            content = b if isinstance(b, str) else str(b)
        except Exception:
            content = repr(b)
        out_path = out_dir / f"{input_html.stem}_block_{i:02d}.html"
        out_path.write_text(content, encoding="utf-8")
        print(f"  écrit {out_path} (taille {len(content)} bytes)")

    # aussi sauvegarder un index.json pour diagnostic
    index = {
        "source": str(input_html),
        "n_blocks": len(blocks),
        "blocks_meta": [{"index": i, "chars": len(b) if isinstance(b, str) else None} for i, b in enumerate(blocks)]
    }
    (out_dir / f"{input_html.stem}_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Index sauvegardé.")
    return 0

def main():
    p = argparse.ArgumentParser(description="Test block_splitter: sauvegarde les blocs HTML en fichiers séparés.")
    p.add_argument("input_dir", nargs="?", help="Dossier contenant les fichiers .html à tester", default=r"C:\Users\marie.tcheng\Documents\consolidation\bench-ocapi\exempleshtml")
    p.add_argument("--out", "-o", help="Dossier de sortie", default=r"C:\Users\marie.tcheng\Documents\consolidation\bench-ocapi\test-block-splitter")
    args = p.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print("Dossier introuvable :", input_dir)
        return 2

    out_base = Path(args.out)
    out_base.mkdir(parents=True, exist_ok=True)

    # parcourir tous les .html du dossier et sauvegarder les blocs pour chaque fichier
    for f in sorted(input_dir.glob("*.html")):
        print("Traitement :", f.name)
        out_dir = out_base / f.stem
        save_blocks(f, out_dir)
    return 0

if __name__ == "__main__":
    sys.exit(main())