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
from ocapi.main import main as run_main
from ocapi.utils.logging_utils import get_logger, initialize_root_logger

_LOGGER = get_logger(__name__)


def cmd_run(args: argparse.Namespace) -> int:
    """Exécute le pipeline OCAPI sur les arrêtés."""
    return run_main(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output) if args.output else None,
        aiot=args.aiot,
        include_ids=args.include,
        enable_detection=not getattr(args, "no_detection", False),
        enable_rendering=not getattr(args, "no_rendering", False),
    )


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
  ocapi run data/arretes_html/0999.99999/

  # Traiter avec un AIOT spécifique
  ocapi run data/arretes_html/0999.99999/ --aiot 0999.99999

  # Sauvegarder le résultat dans un fichier
  ocapi run data/arretes_html/0999.99999/ --output resultat.json

  # Mode verbose pour le debug
  ocapi --verbose run data/arretes_html/0999.99999/

  # Mode silencieux
  ocapi --quiet run data/arretes_html/0999.99999/
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
  # Pipeline complet (détection + résolution + rendering)
  ocapi run data/arretes_html/0999.99999/

  # Traiter avec un AIOT spécifique (par défaut: déduit du nom du répertoire)
  ocapi run data/arretes_html/0999.99999/ --aiot 0999.99999

  # Filtrer sur des arrêtés spécifiques (par leur date)
  ocapi run data/arretes_html/0999.99999/ --include 2024-09-27 2023-12-04

  # Spécifier un répertoire de sortie de base
  ocapi run data/arretes_html/0999.99999/ --output output/

  # Détection + résolution uniquement (sans rendering)
  ocapi run data/arretes_html/0999.99999/ --no-rendering

  # Résolution + rendering à partir d'opérations existantes (sans détection)
  ocapi run data/arretes_html/0999.99999/ --no-detection

  # Résolution uniquement à partir d'opérations existantes (sans rendering)
  ocapi run data/arretes_html/0999.99999/ --no-detection --no-rendering

  # Mode verbose pour voir les logs détaillés
  ocapi --verbose run data/arretes_html/0999.99999/

  # Mode silencieux (uniquement erreurs et avertissements)
  ocapi --quiet run data/arretes_html/0999.99999/
        """,
    )
    run_parser.add_argument(
        "input_dir",
        help="Répertoire contenant les fichiers HTML des arrêtés",
    )
    run_parser.add_argument(
        "--aiot",
        help="Identifiant AIOT (défaut: déduit du nom de input_dir)",
    )
    run_parser.add_argument(
        "--include",
        nargs="*",
        metavar="ID",
        help="IDs des arrêtés à inclure (défaut: tous)",
    )
    run_parser.add_argument(
        "-o",
        "--output",
        help="Répertoire de sortie de base (défaut: répertoire parent du parent de input_dir)",
    )
    run_parser.add_argument(
        "--no-detection",
        action="store_true",
        help=(
            "Désactiver la détection (étapes 1-2) et charger les opérations existantes. "
            "Lève une erreur si aucun fichier d'opérations n'est trouvé."
        ),
    )
    run_parser.add_argument(
        "--no-rendering",
        action="store_true",
        help="Désactiver la génération du permis consolidé (étape 4)",
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
