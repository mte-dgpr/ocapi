#
# Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""
Point d'entrée principal pour exécuter le pipeline OCAPI.
Exécute chunking + detection + resolution (sans rendering).
python -m ocapi.main
"""

from pathlib import Path

from ocapi.config import settings
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_detection.step_detection import step_detection
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import Operation
from ocapi.utils.io_utils import load_arrete_files, write_json_output, write_permis_output

# TODO : enlever les blockquote ?


def main(input_dir: Path, output_dir: Path) -> None:
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
    aiot = input_dir.parent.name  # Utiliser le nom du dossier parent comme AIOT
    arrete_files = load_arrete_files(input_dir, aiot)

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
    modele = settings.pipeline.default_llm_model

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
    write_json_output(operations_dict, operations_path)
    print(f"💾 Opérations sauvegardées → {operations_path}\n")

    # ========================================
    # STEP 3 : RESOLUTION
    # ========================================
    print("=" * 60)
    print("STEP 3 : RESOLUTION")
    print("=" * 60)

    history, arrete_files = step_resolution(operations, arrete_files)
    if history:
        print(f"✓ {len(history)} articles avec historique\n")
    else:
        print("✓ 0 article avec historique\n")

    # Sauvegarder l'historique
    history_path = output_dir / "history.json"
    history_serializable = {
        str(node_id): [
            {"version": v["version"], "content": v["content"], "operation_id": v["operation_id"]}
            for v in versions
        ]
        for node_id, versions in history.items()
    }
    write_json_output(history_serializable, history_path)
    print(f"💾 Historique sauvegardé → {history_path}\n")

    # ========================================
    # STEP 4 : RENDERING
    # ========================================
    print("=" * 60)
    print("STEP 4 : RENDERING")
    print("=" * 60)

    permis = step_rendering(history, operations, arrete_files)
    permis_path = output_dir / "permis_consolidé.html"
    write_permis_output(permis, permis_path)
    print(f"💾 Permis consolidé sauvegardé → {permis_path}")
    print("\n✅ Pipeline terminé avec succès !")


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).parent.parent
    input_arretes_dir = PROJECT_ROOT / "data" / "0005804239" / "arretes_html"
    output_dir = PROJECT_ROOT / "data" / "0005804239" / "ocapi_output"

    main(input_arretes_dir, output_dir)
