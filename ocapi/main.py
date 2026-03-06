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
    python -m ocapi.main data/arretes_html/0005804239/
    python -m ocapi.main data/arretes_html/0005804239/ --output output/
    python -m ocapi.main data/arretes_html/0005804239/ --start-date 2014-01-09
    python -m ocapi.main data/arretes_html/0005804239/ --include 2024-09-27 2023-12-04
    python -m ocapi.main data/arretes_html/0005804239/ --no-rendering
    python -m ocapi.main data/arretes_html/0005804239/ --no-detection
    python -m ocapi.main data/arretes_html/0005804239/ --no-detection --no-rendering
"""

import argparse
import sys
from pathlib import Path

from ocapi.config import settings
from ocapi.exceptions import OcapiError
from ocapi.pipeline import run_pipeline
from ocapi.utils.io_utils import InputOutputError, load_arrete_files
from ocapi.utils.llm_utils import config_model_llm
from ocapi.utils.logging_utils import get_logger, initialize_root_logger

_LOGGER = get_logger(__name__)


def main(
    input_dir: Path,
    output_dir: Path | None = None,
    aiot: str | None = None,
    include_ids: list[str] | None = None,
    start_date: str | None = None,
    enable_detection: bool = True,
    enable_rendering: bool = True,
) -> int:
    """
    Exécute le pipeline OCAPI selon les étapes sélectionnées.

    Args:
        input_dir: Répertoire contenant les fichiers HTML des arrêtés
        output_dir: Répertoire de base pour les sorties par étape
            (défaut: répertoire parent du parent de input_dir)
        aiot: Identifiant AIOT (si None, déduit du nom de input_dir)
        include_ids: Liste des IDs d'arrêtés à inclure (si None, tous)
        start_date: Date de démarrage (YYYY-MM-DD) pour la détection
        enable_detection: Si True, lance les étapes chunking + détection ;
            si False, charge les opérations depuis le répertoire de détection
        enable_rendering: Si True, génère le permis consolidé

    Returns:
        Code de sortie (0 = succès, 1 = erreur)
    """
    # Déterminer le répertoire de sortie de base
    if output_dir is None:
        output_dir = input_dir.parent.parent

    # Déterminer l'AIOT
    if aiot is None:
        aiot = input_dir.name

    _LOGGER.info(f"Dossier d'entrée : {input_dir}")
    _LOGGER.info(f"Dossier de sortie de base : {output_dir}")
    _LOGGER.info(f"AIOT: {aiot}")
    if enable_detection:
        _LOGGER.info(f"Modèle LLM: {config_model_llm().model_name}")

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

    try:
        run_pipeline(
            arrete_files,
            aiot=aiot,
            output_dir=output_dir,
            start_date=start_date,
            enable_detection=enable_detection,
            enable_rendering=enable_rendering,
        )
        return 0

    except OcapiError as e:
        _LOGGER.error(f"Erreur OCAPI: {e}")
        return 1
    except Exception as e:
        _LOGGER.exception(f"Erreur inattendue lors de l'exécution du pipeline: {e}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="ocapi.main",
        description="OCAPI - Pipeline complet de traitement des arrêtés",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pipeline complet (détection + résolution + rendering)
  python -m ocapi.main data/arretes_html/0005804239/

  # Spécifier un répertoire de sortie de base
  python -m ocapi.main data/arretes_html/0005804239/ --output output/

  # Démarrer la détection à partir d'une date
  python -m ocapi.main data/arretes_html/0005804239/ --start-date 2014-01-09

  # Filtrer sur des arrêtés spécifiques
  python -m ocapi.main data/arretes_html/0005804239/ --include 2024-09-27 2023-12-04

  # Détection + résolution uniquement (sans rendering)
  python -m ocapi.main data/arretes_html/0005804239/ --no-rendering

  # Résolution + rendering à partir d'opérations existantes (sans détection)
  python -m ocapi.main data/arretes_html/0005804239/ --no-detection

  # Résolution uniquement à partir d'opérations existantes (sans rendering)
  python -m ocapi.main data/arretes_html/0005804239/ --no-detection --no-rendering

  # Spécifier l'AIOT
  python -m ocapi.main data/arretes_html/0005804239/ --aiot 0005804239

  # Mode verbose
  python -m ocapi.main data/arretes_html/0005804239/ --verbose
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
        help="Répertoire de sortie de base (défaut: répertoire parent du parent de input_dir)",
    )
    parser.add_argument(
        "--aiot",
        help="Identifiant AIOT (défaut: déduit du nom de input_dir)",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        metavar="ID",
        help="IDs des arrêtés à inclure (défaut: tous)",
    )
    parser.add_argument(
        "--start-date",
        help="Date de démarrage (YYYY-MM-DD) pour la détection",
    )
    parser.add_argument(
        "--no-detection",
        action="store_true",
        help=(
            "Désactiver la détection (étapes 1-2) et charger les opérations existantes. "
            "Lève une erreur si aucun fichier d'opérations n'est trouvé."
        ),
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
        start_date=args.start_date,
        enable_detection=not args.no_detection,
        enable_rendering=not args.no_rendering,
    )

    sys.exit(exit_code)
