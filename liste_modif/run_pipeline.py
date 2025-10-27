import os, json, time
from pathlib import Path
from block_splitter import extract_arrete_blocs
from ask_llm import config_API, ask_llm_for_operation
from extract_new_content import remplacer_new_content
from bs4 import BeautifulSoup


def build_img_map_from_html(html_text: str) -> dict:
    soup = BeautifulSoup(html_text, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    img_map = {}
    counter = 0
    for img in soup.find_all("img"):
        src = img.get("src", "")
        counter += 1
        key = f"IMG_{counter:03d}"
        if src:
            img_map[key] = src
    return img_map

def process_folder(folder_path: str, modele: str = "", out_dir: str = "out_json"):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cfg = config_API(modele)
    for filepath in sorted(Path(folder_path).glob("*.html")):
        fname = filepath.name
        print("Traitement de :", fname)
        blocks = extract_arrete_blocs(str(filepath)) #TODO: sauvegarder les blocs quelque part pour l'instant (pouvoir tester extraction séparément après)
        print(f"Le fichier est envoyé en {len(blocks)} fois.")
        html_raw = Path(filepath).read_text(encoding="utf-8")
        img_map = build_img_map_from_html(html_raw)
        all_ops = []
        t0 = time.time()
        for i in range(len(blocks)):
            ops = ask_llm_for_operation(blocks[i], cfg)
            for op in ops:
                op["source_file"] = fname
                op["block_index"] = i 
                # extraire nouveau contenu si applicable (chercher UNIQUEMENT DANS LE BLOC)
                if op.get("modification_type") != "DELETE":
                    ref = op.get("new_content_ref") or {}
                    start_marker = ref.get("start_marker")
                    end_marker = ref.get("end_marker")
                    op["new_content_html"] = remplacer_new_content(blocks[i], img_map, op.get("source_article"), start_marker, end_marker)
                else:
                    op["new_content_html"] = None
                all_ops.append(op)
        elapsed = time.time() - t0
        out = {
            "source_file": fname,
            "total_chars": sum(len(b) for b in blocks),
            "n_blocks_sent": len(blocks),
            "processing_time_s": round(elapsed, 2),
            "operations": all_ops
        }
        out_path = Path(out_dir) / (Path(filepath).stem + ".json")
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Voir fichier {out_path} - {len(all_ops)} modifications détectées - temps écoulé {elapsed:.2f}s")

if __name__ == "__main__":
    dossier = input("Dossier html (chemin complet) : ").strip() or r"C:\Users\marie.tcheng\Documents\consolidation\bench-ocapi\exempleshtml"
    modele = input("Modèle (laisser vide pour Mistral) : ").strip()
    process_folder(dossier, modele=modele, out_dir="out_json")