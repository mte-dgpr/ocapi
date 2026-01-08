"""
Point d'entrée principal pour exécuter le pipeline OCAPI.
Exécute chunking + detection + resolution (sans rendering).
python -m ocapi.main
"""

import json
from pathlib import Path

from bs4 import BeautifulSoup

from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.pipeline import run_pipeline
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_detection.step_detection import step_detection
from ocapi.types import ArreteFile, Operation
from ocapi.constants import DEFAULT_LLM_MODEL


# TODO : faire d'abord tous les appels LLM puis convertir en raw ops dans un second temps. comme ça on peut faire du batch et gérer les erreurs après.
# TODO : enlever les blockquote au début. 
# erreurs à gérer : appendice 2024. 
# 6.7 à ajouter : mettre sans objet
# parser END 


def folder_to_list_of_ArreteFiles(folder_path: Path) -> list[ArreteFile]:
    """
    Charge tous les fichiers HTML d'un dossier et les convertit en ArreteFile.
    Attention, les arrete_id sont uniquement la date extraite du nom de fichier pour l'instant.
    """
    arrete_files = []
    html_files = sorted(folder_path.glob("*.html"))
    aiot = folder_path.name  # Utiliser le nom du dossier comme AIOT

    for i, html_path in enumerate(html_files):
        arrete_file = arrete_to_ArreteFile(i, html_path)
        arrete_file.aiot = aiot
        arrete_files.append(arrete_file)
    
    return arrete_files


def arrete_to_ArreteFile(i:int, html_path: Path) -> ArreteFile:
    filename = html_path.stem 
    
    # Parser le nom : YYYY-MM-DD_Autresinfos.html
    parts = filename.split("_")
    if len(parts) < 2:
        raise ValueError(f"Format de fichier invalide : {filename}")
    date_str = parts[0]
    arrete_id = f"{date_str}"
    
    # Charger et parser le HTML
    html_content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")
    
    return ArreteFile(
        id=arrete_id,
        aiot="",  
        ordered_index=i,
        filename=filename,
        soup=soup,
    )


def main(input_dir: Path, output_dir: Path):
    """
    Exécute le pipeline OCAPI complet de bout en bout :
    1. Chunking + Detection (avec sauvegarde des opérations)
    2. Resolution (avec sauvegarde de l'historique)
    3. Rendering (génération du permis consolidé)
    """
    print(f"📂 Dossier d'entrée : {input_dir}")
    print(f"📂 Dossier de sortie : {output_dir}")
    
    # Vérifier les fichiers HTML
    html_files = sorted(input_dir.glob("*.html"))
    if not html_files:
        print("❌ Aucun fichier HTML trouvé")
        return
    
    print(f"Chargement de {len(html_files)} fichiers HTML")
    arrete_files = folder_to_list_of_ArreteFiles(input_dir)
    
    # Créer le dossier de sortie
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n🚀 Démarrage du pipeline...\n")
    
    # ========================================
    # STEP 1-2 : CHUNKING + DETECTION
    # ========================================
    print("=" * 60)
    print("STEP 1-2 : CHUNKING + DETECTION")
    print("=" * 60)
    
    operations: list[Operation] = []
    modele = DEFAULT_LLM_MODEL
    
    for i, arrete_file in enumerate(arrete_files):
        if i == 0:
            continue  # Skip first file (AP initial)
        print(f"Traitement de l'arrêté {arrete_file.id}...")
        docs, img_map = step_chunking(arrete_file)
        print(f"  → {len(docs)} documents chunkés")
        print(f"  → {len(img_map)} images mappées")

        detected_ops = step_detection(docs, arrete_file.id, modele, img_map)
        operations.extend(detected_ops)
        print(f"  → {len(detected_ops)} opérations détectées")
    
    print(f"\n✓ Total : {len(operations)} opérations\n")
    
    # Sauvegarder les opérations
    operations_path = output_dir / "operations.json"
    operations_dict = [op.model_dump() for op in operations]
    with operations_path.open("w", encoding="utf-8") as f:
        json.dump(operations_dict, f, ensure_ascii=False, indent=2)
    print(f"💾 Opérations sauvegardées → {operations_path}\n")
    
    # ========================================
    # STEP 3 : RESOLUTION
    # ========================================
    print("=" * 60)
    print("STEP 3 : RESOLUTION")
    print("=" * 60)
    
    history, arrete_files = step_resolution(operations, arrete_files)
    print(f"✓ {len(history)} articles avec historique\n")
    
    # Sauvegarder l'historique
    versions_dir = output_dir / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    versions_path = versions_dir / "history.json"
    
    # Convertir NodeId (tuple) en string pour JSON
    history_serializable = {}
    for (arrete_id, article_id), versions in history.items():
        key = f"{arrete_id}:{article_id}"
        history_serializable[key] = versions
    
    with versions_path.open("w", encoding="utf-8") as f:
        json.dump(history_serializable, f, ensure_ascii=False, indent=2)
    print(f"💾 Historique sauvegardé → {versions_path}\n")
    
    # ========================================
    # STEP 4 : RENDERING
    # ========================================
    print("=" * 60)
    print("STEP 4 : RENDERING")
    print("=" * 60)
    
    permis = step_rendering(history, operations, arrete_files)
    permis_path = output_dir / "permis_consolidé.html"
    with permis_path.open("w", encoding="utf-8") as f:
        f.write(permis.to_html())
    print(f"💾 Permis consolidé sauvegardé → {permis_path}")
    print("\n✅ Pipeline terminé avec succès !")

if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).parent.parent
    input_arretes_dir = PROJECT_ROOT / "data" / "0005804239" / "arretes_html"
    output_dir = PROJECT_ROOT / "data" / "0005804239" / "ocapi_output"
    
    main(input_arretes_dir, output_dir)
    