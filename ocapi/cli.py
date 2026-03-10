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
Interface en ligne de commande pour OCAPI.

Usage:
    ocapi run <input_dir> [--aiot AIOT] [--output OUTPUT]
    ocapi --help
"""

import argparse
import sys
from pathlib import Path

from ocapi.config import settings
from ocapi.pipeline import run_pipeline
from ocapi.utils.io_utils import (
    InputOutputError,
    load_arrete_files,
    write_json_output,
    write_permis_output,
)
from ocapi.utils.llm_utils import config_model_llm
from ocapi.utils.logging_utils import get_logger, initialize_root_logger

_LOGGER = get_logger(__name__)


def cmd_run(args: argparse.Namespace) -> int:
    """Exécute le pipeline OCAPI sur les arrêtés."""
    input_dir = Path(args.input_dir)

    # Déterminer le répertoire de sortie
    output_dir = Path(args.output) if args.output else input_dir.parent / "ocapi_output"
    _LOGGER.info(f"Dossier de sortie : {output_dir}")

    # Déterminer l'AIOT
    aiot = args.aiot or input_dir.parent.name
    _LOGGER.info(f"AIOT: {aiot}")
    _LOGGER.info(f"Modèle LLM: {config_model_llm().model_name}")

    # Charger les arrêtés
    try:
        arrete_files = load_arrete_files(input_dir, aiot)
    except InputOutputError as e:
        print(f"Erreur: {e}", file=sys.stderr)
        return 1

    # Filtrer les arrêtés si demandé
    if args.include:
        arrete_ids_included = set(args.include)
        _LOGGER.info(f"Filtrage sur: {arrete_ids_included}")
        arrete_files = [af for af in arrete_files if af.id in arrete_ids_included]
        _LOGGER.info(f"{len(arrete_files)} arrêté(s) après filtrage")

        if not arrete_files:
            _LOGGER.error("Aucun arrêté ne correspond aux IDs spécifiés")
            return 1

    # Créer le dossier de sortie
    output_dir.mkdir(parents=True, exist_ok=True)

    # Exécuter le pipeline
    _LOGGER.info("Exécution du pipeline...")
    try:
        start_date = getattr(args, "start_date", None)
        operations, history, _arrete_files, permis = run_pipeline(
            arrete_files, start_date=start_date
        )
        _LOGGER.info("Pipeline terminé avec succès.")

        # Sauvegarder les opérations
        operations_path = output_dir / "operations.json"
        operations_dict = [op.model_dump(mode="json") for op in operations]
        write_json_output(operations_dict, operations_path)
        _LOGGER.info(f"Opérations sauvegardées → {operations_path}")

        # Sauvegarder l'historique
        history_path = output_dir / "history.json"
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
        write_json_output(history_serializable, history_path)
        _LOGGER.info(f"Historique sauvegardé → {history_path}")

        # Sauvegarder le permis
        if permis:
            permis_path = output_dir / "permis.html"
            write_permis_output(permis, permis_path)
            _LOGGER.info(f"Permis consolidé sauvegardé → {permis_path}")

        return 0

    except Exception as e:
        _LOGGER.error(f"Erreur lors de l'exécution du pipeline: {e}")
        return 1


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée principal du CLI."""
    parser = argparse.ArgumentParser(
        prog="ocapi",
        description="OCAPI - Pipeline de détection, résolution et rendu des arrêtés",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Afficher l'aide générale
  ocapi --help

  # Afficher l'aide d'une commande
  ocapi run --help

  # Traiter tous les arrêtés d'un répertoire
  ocapi run data/0999.99999/arretes/

  # Traiter avec un AIOT spécifique
  ocapi run data/0999.99999/arretes/ --aiot 0999.99999

  # Sauvegarder le résultat dans un fichier
  ocapi run data/0999.99999/arretes/ --output resultat.json

  # Mode verbose pour le debug
  ocapi --verbose run data/0999.99999/arretes/

  # Mode silencieux
  ocapi --quiet run data/0999.99999/arretes/
        """,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    # Options globales de logging
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

    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Commande: run
    run_parser = subparsers.add_parser(
        "run",
        help="Exécuter le pipeline sur des arrêtés",
        description="Charge les arrêtés HTML et exécute le pipeline de traitement.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Traiter tous les arrêtés d'un répertoire
  ocapi run data/0999.99999/arretes/


  # Traiter avec un AIOT spécifique (par défaut: déduit du chemin parent)
  ocapi run data/0999.99999/arretes/ --aiot 0999.99999


  # Filtrer sur des arrêtés spécifiques (par leur date)
  ocapi run data/0999.99999/arretes/ --include 2024-09-27 2023-12-04


  # Sauvegarder les résultats dans un répertoire spécifique
  ocapi run data/0999.99999/arretes/ --output output/


  # Combinaison: filtrage et sauvegarde
  ocapi run data/0999.99999/arretes/ --include 2024-09-27 --output output/


  # Mode verbose pour voir les logs détaillés
  ocapi --verbose run data/0999.99999/arretes/


  # Mode silencieux (uniquement erreurs et avertissements)
  ocapi --quiet run data/0999.99999/arretes/
        """,
    )
    run_parser.add_argument(
        "input_dir",
        help="Répertoire contenant les fichiers HTML des arrêtés",
    )
    run_parser.add_argument(
        "--aiot",
        help="Identifiant AIOT (défaut: déduit du chemin)",
    )
    run_parser.add_argument(
        "--include",
        nargs="*",
        metavar="ID",
        help="IDs des arrêtés à inclure (défaut: tous)",
    )
    run_parser.add_argument(
        "--start-date",
        metavar="YYYY-MM-DD",
        help="Date de démarrage : seuls les arrêtés >= cette date passent par la détection",
    )
    run_parser.add_argument(
        "-o",
        "--output",
        help="Répertoire de sortie (défaut: <input_dir>/../ocapi_output)",
    )
    run_parser.set_defaults(func=cmd_run)

    # Parser les arguments
    args = parser.parse_args(argv)

    # Déterminer le niveau de logging selon les options CLI
    log_level = settings.logging.level
    if args.verbose:
        log_level = "DEBUG"
    elif args.quiet:
        log_level = "WARNING"

    # Initialiser le logger racine
    initialize_root_logger(
        level=log_level,
        log_file=settings.logging.log_file,
        max_bytes=settings.logging.max_bytes,
        backup_count=settings.logging.backup_count,
        use_timed_rotation=settings.logging.use_timed_rotation,
        console_output=settings.logging.console_output,
    )

    _LOGGER.debug(f"Logging initialisé au niveau {log_level}")

    if args.command is None:
        parser.print_help()
        return 0

    # Appeler la fonction associée à la commande
    func = args.func
    result: int = func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
