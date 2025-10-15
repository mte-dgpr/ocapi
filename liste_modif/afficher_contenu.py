import json
from pathlib import Path

FICHIER_MODIFS = "modifications_detectees_arretes.json"

def afficher_contenu_modifs(fichier_json: str):
    data = json.loads(Path(fichier_json).read_text(encoding="utf-8"))

    for i, item in enumerate(data, start=1):
        print(f"\n=== Modification {i} ===")

        mod_type = (item.get("modification_type") or "").upper()
        arrete = item.get("target_arrete")
        article = item.get("target_article")
        html_path = item.get("analysis_html_file")

        print(f"Type: {mod_type}")
        print(f"Arrêté cible: {arrete}")
        print(f"Article: {article}")
        print(f"Fichier: {html_path}")

        # Cas REMOVE: pas de nouveau contenu à afficher
        if mod_type == "REMOVE":
            print("→ Opération REMOVE : pas de nouveau contenu (new_content_ref = null).")
            continue

        # Récupération sûre de new_content_ref (peut être None)
        ref = item.get("new_content_ref") or {}
        start = ref.get("start_index")
        end = ref.get("end_index")

        if not (isinstance(start, int) and isinstance(end, int)):
            print("⚠️  Indices manquants (new_content_ref absent ou incomplet).")
            continue

        if start < 0 or end < 0 or end < start:
            print(f"⚠️  Indices invalides: start={start}, end={end}.")
            continue

        if not html_path:
            print("⚠️  Chemin analysis_html_file manquant.")
            continue

        try:
            html_text = Path(html_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"❌ Fichier HTML introuvable : {html_path}")
            continue

        if end > len(html_text):
            print(f"⚠️  end_index ({end}) dépasse la taille du fichier ({len(html_text)}).")
            continue

        segment = html_text[start:end]

        # Affichage avec tronquage léger pour éviter les pavés
        print(f"Indices: {start} → {end} (longueur {len(segment)})")
        if len(segment) > 800:
            print(segment[:800] + " [...] (tronqué)")
        else:
            print(segment)

if __name__ == "__main__":
    afficher_contenu_modifs(FICHIER_MODIFS)