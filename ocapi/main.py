"""
Point d'entrée principal pour exécuter le pipeline OCAPI.
Exécute chunking + detection + resolution (sans rendering).
python -m ocapi.main
"""

import json
from pathlib import Path

from bs4 import BeautifulSoup

from ocapi.pipeline import run_pipeline
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_detection.step_detection import step_detection
from ocapi.types import ArreteFile, Operation
from ocapi.constants import DEFAULT_LLM_MODEL



# TODO : faire d'abord tous les appels LLM puis convertir en raw ops dans un second temps. comme ça on peut faire du batch et gérer les erreurs après.


def folder_to_list_of_ArreteFiles(folder_path: Path) -> list[ArreteFile]:
    """
    Charge tous les fichiers HTML d'un dossier et les convertit en ArreteFile.
    Attention, les arrete_id sont uniquement la date extraite du nom de fichier pour l'instant.
    """
    arrete_files = []
    html_files = sorted(folder_path.glob("*.html"))
    aiot = folder_path.name  # Utiliser le nom du dossier comme AIOT

    for html_path in html_files:
        arrete_file = arrete_to_ArreteFile(html_path)
        arrete_file.aiot = aiot
        arrete_files.append(arrete_file)
    
    return arrete_files


def arrete_to_ArreteFile(html_path: Path) -> ArreteFile:
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
        filename=filename,
        soup=soup,
    )


def temporary_main(input_dir: Path, output_dir: Path):
    """
    Point d'entrée temporaire pour exécuter le pipeline OCAPI.
    Exécute chunking + detection + resolution (sans rendering).
    """
    print(f"📂 Dossier d'entrée : {input_dir}")
    print(f"📂 Dossier de sortie : {output_dir}")
    html_files = sorted(input_dir.glob("*.html"))
    if not html_files:
        print("❌ Aucun fichier HTML trouvé")
        return
    
    print(f"Chargement de {len(html_files)} fichiers HTML")
    
    arrete_files = folder_to_list_of_ArreteFiles(input_dir)
    
    print("\n🚀 Démarrage du pipeline...\n")

    operations: list[Operation] = []
    modele = DEFAULT_LLM_MODEL
    
    # # Chemin du cache des opérations
    output_dir.mkdir(parents=True, exist_ok=True)
    operations_path = output_dir / "operations.json"
    
    # # Vérifier si on a déjà des opérations en cache
    # if operations_path.exists():
    #     logger.info("📦 Chargement des opérations depuis le cache...\n")
    #     with operations_path.open("r", encoding="utf-8") as f:
    #         operations_dict = json.load(f)
        
    #     # Reconstruire les objets Operation depuis le JSON
    #     operations = [Operation(**op_dict) for op_dict in operations_dict]
    #     logger.info(f"✓ {len(operations)} opérations chargées depuis {operations_path}\n")
    
    # else:
    # STEP 1: Chunking + Detection (avec appels API)
    print("=" * 60)
    print("STEP 1-2 : CHUNKING + DETECTION")
    print("=" * 60)
    
    for i, arrete_file in enumerate(arrete_files):
        if i == 0:
            continue  # Skip first file (AP initial)
        print(f"Traitement de l'arreté de {arrete_file.id}...")
        docs, img_map = step_chunking(arrete_file)
        print(f"  → {len(docs)} documents chunkés")
        print(f"  → {len(img_map)} images mappées")

        detected_ops = step_detection(docs, arrete_file.id, modele, img_map)
        operations.extend(detected_ops)
        print(f"  → {len(detected_ops)} opérations détectées")
    
    print(f"\n✓ Total : {len(operations)} opérations\n")
    
    # Sauvegarder les opérations pour la prochaine fois
    operations_dict = [op.model_dump() for op in operations]
    with operations_path.open("w", encoding="utf-8") as f:
        json.dump(operations_dict, f, ensure_ascii=False, indent=2)
    print(f"💾 Opérations sauvegardées → {operations_path}\n")

    # # STEP 2: Resolution
    # print("=" * 60)
    # print("STEP 3 : RESOLUTION")
    # print("=" * 60)
    
    # versions: list[ArticlesContentMap] = step_resolution(operations)
    # print(f"✓ {len(versions)} versions générées\n")
    
    # # Sauvegarder les versions
    # versions_dir = output_dir / "versions"
    # versions_dir.mkdir(parents=True, exist_ok=True)
    # versions_path = versions_dir / "versions.json"
    
    # # Convertir NodeId en string pour JSON
    # versions_serializable = []
    # for version in versions:
    #     version_dict = {str(node_id): content for node_id, content in version.items()}
    #     versions_serializable.append(version_dict)
    
    # with versions_path.open("w", encoding="utf-8") as f:
    #     json.dump(versions_serializable, f, ensure_ascii=False, indent=2)
    # logger.info(f"💾 Versions sauvegardées → {versions_path}\n")
    
    # logger.info("✅ Pipeline terminé avec succès !")


def main(input_dir: Path, output_dir: Path):
    print(f"📂 Dossier d'entrée : {input_dir}")
    print(f"📂 Dossier de sortie : {output_dir}")
    
    html_files = sorted(input_dir.glob("*.html"))
    if not html_files:
        print("❌ Aucun fichier HTML trouvé")
        return
    
    print(f"Chargement de {len(html_files)} fichiers HTML")
    arrete_files = folder_to_list_of_ArreteFiles(input_dir)
    print("\n🚀 Démarrage du pipeline...\n")
    run_pipeline(arrete_files, output_dir)

if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).parent.parent
    input_dir = PROJECT_ROOT / "data" / "0005804239" / "arretes_html"
    output_dir = PROJECT_ROOT / "data" / "0005804239" / "ocapi_output"
    temporary_main(input_dir, output_dir)
    