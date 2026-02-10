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

Usage:
    python -m ocapi.main <input_dir> [options]
    python ocapi/main.py <input_dir> [options]

Examples:
    python -m ocapi.main data/0005804239/arretes_html/
    python -m ocapi.main data/0005804239/arretes_html/ --output output/
    python -m ocapi.main data/0005804239/arretes_html/ --skip-first
    python -m ocapi.main data/0005804239/arretes_html/ --include 2024-09-27 2023-12-04
    python -m ocapi.main data/0005804239/arretes_html/ --no-rendering
"""

import argparse
import json
import sys
from pathlib import Path

from ocapi.config import settings
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_detection.step_detection import step_detection
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import ArreteFile, ArticleHistory, Operation, Permis
from ocapi.utils.io_utils import (
    InputOutputError,
    load_arrete_files,
    write_json_output,
    write_permis_output,
)
from ocapi.utils.logging_utils import get_logger, initialize_root_logger

_LOGGER = get_logger(__name__)


def run_pipeline(
    arrete_files: list[ArreteFile],
    output_dir: Path,
    skip_first: bool = False,
    enable_rendering: bool = True,
) -> tuple[list[Operation], ArticleHistory, list[ArreteFile], Permis | None]:
    """
    Exécute le pipeline OCAPI complet.

    Args:
        arrete_files: Liste des arrêtés à traiter
        output_dir: Répertoire de sortie pour les fichiers générés
        skip_first: Si True, ignore le premier arrêté (AP initial)
        enable_rendering: Si True, génère le permis consolidé (étape 4)

    Returns:
        Tuple (operations, history, arrete_files, permis)
    """
    _LOGGER.info(f"Démarrage du pipeline avec {len(arrete_files)} arrêté(s)")

    operations: list[Operation] = []
    modele = settings.pipeline.default_llm_model

    # ========================================
    # STEP 1-2 : CHUNKING + DETECTION
    # ========================================
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 1-2 : CHUNKING + DETECTION")
    _LOGGER.info("=" * 60)

    start_index = 1 if skip_first else 0
    for _i, arrete_file in enumerate(arrete_files[start_index:], start=start_index):
        _LOGGER.info(f"Traitement de l'arrêté {arrete_file.id}...")
        docs, img_map = step_chunking(arrete_file)
        _LOGGER.info(f"  → {len(docs)} documents chunkés")
        _LOGGER.debug(f"  → {len(img_map)} images mappées")

        detected_ops = step_detection(docs, arrete_file.id, modele, img_map)
        operations.extend(detected_ops)
        _LOGGER.info(f"  → {len(detected_ops)} opérations détectées")

    _LOGGER.info(f"Total : {len(operations)} opération(s) détectée(s)")
    # Sauvegarder les opérations
    operations_path = output_dir / "operations.json"
    operations_dict = [op.model_dump() for op in operations]
    write_json_output(operations_dict, operations_path)
    _LOGGER.info(f"💾 Opérations sauvegardées → {operations_path}\n")

    # ========================================
    # STEP 3 : RESOLUTION
    # ========================================
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 3 : RESOLUTION")
    _LOGGER.info("=" * 60)

    history, arrete_files = step_resolution(operations, arrete_files)
    if history:
        _LOGGER.info(f"{len(history)} articles avec historique")
    else:
        _LOGGER.info("0 article avec historique")

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
    _LOGGER.info(f"💾 Historique sauvegardé → {history_path}\n")

    # ========================================
    # STEP 4 : RENDERING (optionnel)
    # ========================================
    permis = None
    if enable_rendering:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 4 : RENDERING")
        _LOGGER.info("=" * 60)

        permis = step_rendering(history, operations, arrete_files)
        _LOGGER.info("Permis consolidé généré")

    _LOGGER.info("Pipeline terminé avec succès !")
    return operations, history, arrete_files, permis


def main(
    input_dir: Path,
    output_dir: Path | None = None,
    aiot: str | None = None,
    include_ids: list[str] | None = None,
    skip_first: bool = False,
    enable_rendering: bool = True,
) -> int:
    """
    Exécute le pipeline OCAPI complet de bout en bout.

    Args:
        input_dir: Répertoire contenant les fichiers HTML des arrêtés
        output_dir: Répertoire de sortie (si None, utilise input_dir/../ocapi_output)
        aiot: Identifiant AIOT (si None, déduit du chemin)
        include_ids: Liste des IDs d'arrêtés à inclure (si None, tous)
        skip_first: Si True, ignore le premier arrêté (AP initial)
        enable_rendering: Si True, génère le permis consolidé

    Returns:
        Code de sortie (0 = succès, 1 = erreur)
    """
    # Déterminer le répertoire de sortie
    if output_dir is None:
        output_dir = input_dir.parent / "ocapi_output"

    _LOGGER.info(f"Dossier d'entrée : {input_dir}")
    _LOGGER.info(f"Dossier de sortie : {output_dir}")

    # Déterminer l'AIOT
    if aiot is None:
        aiot = input_dir.parent.name
    _LOGGER.info(f"AIOT: {aiot}")
    _LOGGER.info(f"Modèle LLM: {settings.pipeline.default_llm_model}")

    # Charger les arrêtés
    try:
        arrete_files = load_arrete_files(input_dir, aiot)
    except InputOutputError as e:
        _LOGGER.error(f"Erreur: {e}")
        return 1

    if not arrete_files:
        _LOGGER.error("Aucun arrêté valide trouvé")
        return 1

    _LOGGER.info(f"{len(arrete_files)} arrêté(s) chargé(s)")

    # Filtrer les arrêtés si demandé
    if include_ids:
        arrete_ids_included = set(include_ids)
        _LOGGER.info(f"Filtrage sur: {arrete_ids_included}")
        arrete_files = [af for af in arrete_files if af.id in arrete_ids_included]
        _LOGGER.info(f"{len(arrete_files)} arrêté(s) après filtrage")

        if not arrete_files:
            _LOGGER.error("Aucun arrêté ne correspond aux IDs spécifiés")
            return 1

    # Créer le dossier de sortie
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Exécuter le pipeline
        operations, history, arrete_files, permis = run_pipeline(
            arrete_files,
            output_dir,
            skip_first=skip_first,
            enable_rendering=enable_rendering,
        )

        # Sauvegarder les opérations
        operations_path = output_dir / "operations.json"
        operations_dict = [op.model_dump(mode="json") for op in operations]
        with operations_path.open("w", encoding="utf-8") as f:
            json.dump(operations_dict, f, ensure_ascii=False, indent=2)
        _LOGGER.info(f"Opérations sauvegardées → {operations_path}")

        # Sauvegarder l'historique
        versions_dir = output_dir / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        versions_path = versions_dir / "history.json"

        # Convertir NodeId en string et ArticleHistory en format sérialisable
        history_serializable = {
            str(node_id): [
                {
                    "version": v["version"],
                    "content": v["content"],
                    "operation_id": v["operation_id"],
                }
                for v in versions
            ]
            for node_id, versions in history.items()
        }

        with versions_path.open("w", encoding="utf-8") as f:
            json.dump(history_serializable, f, ensure_ascii=False, indent=2)
        _LOGGER.info(f"Historique sauvegardé → {versions_path}")

        # Sauvegarder le permis si généré
        if permis:
            permis_path = output_dir / "permis_consolidé.html"
            write_permis_output(permis, permis_path)
            _LOGGER.info(f"Permis consolidé sauvegardé → {permis_path}")

        _LOGGER.info("Pipeline terminé avec succès !")
        return 0

    except Exception as e:
        _LOGGER.exception(f"Erreur lors de l'exécution du pipeline: {e}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="ocapi.main",
        description="OCAPI - Pipeline complet de traitement des arrêtés",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Traiter tous les arrêtés d'un répertoire
  python -m ocapi.main data/0005804239/arretes_html/

  # Spécifier un répertoire de sortie personnalisé
  python -m ocapi.main data/0005804239/arretes_html/ --output output/

  # Ignorer le premier arrêté (AP initial)
  python -m ocapi.main data/0005804239/arretes_html/ --skip-first

  # Filtrer sur des arrêtés spécifiques
  python -m ocapi.main data/0005804239/arretes_html/ --include 2024-09-27 2023-12-04

  # Désactiver le rendering (étapes 1-3 uniquement)
  python -m ocapi.main data/0005804239/arretes_html/ --no-rendering

  # Spécifier l'AIOT
  python -m ocapi.main data/0005804239/arretes_html/ --aiot 0005804239

  # Mode verbose
  python -m ocapi.main data/0005804239/arretes_html/ --verbose
        """,
    )

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Répertoire contenant les fichiers HTML des arrêtés",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Répertoire de sortie (défaut: <input_dir>/../ocapi_output)",
    )
    parser.add_argument(
        "--aiot",
        help="Identifiant AIOT (défaut: déduit du chemin parent)",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        metavar="ID",
        help="IDs des arrêtés à inclure (défaut: tous)",
    )
    parser.add_argument(
        "--skip-first",
        action="store_true",
        help="Ignorer le premier arrêté (AP initial)",
    )
    parser.add_argument(
        "--no-rendering",
        action="store_true",
        help="Désactiver la génération du permis consolidé (étape 4)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Active le mode verbose (niveau DEBUG)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Mode silencieux (affiche uniquement WARNING, ERROR, CRITICAL)",
    )

    args = parser.parse_args()

    # Déterminer le niveau de logging
    log_level = settings.logging.level
    if args.verbose:
        log_level = "DEBUG"
    elif args.quiet:
        log_level = "WARNING"

    # Initialiser le logger
    initialize_root_logger(
        level=log_level,
        log_file=settings.logging.log_file,
        max_bytes=settings.logging.max_bytes,
        backup_count=settings.logging.backup_count,
        use_timed_rotation=settings.logging.use_timed_rotation,
        console_output=settings.logging.console_output,
    )

    _LOGGER.debug(f"Logging initialisé au niveau {log_level}")

    # Exécuter le pipeline
    exit_code = main(
        input_dir=args.input_dir,
        output_dir=args.output,
        aiot=args.aiot,
        include_ids=args.include,
        skip_first=args.skip_first,
        enable_rendering=not args.no_rendering,
    )

    sys.exit(exit_code)
