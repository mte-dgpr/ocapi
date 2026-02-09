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

from bs4 import BeautifulSoup

from ocapi.config import settings
from ocapi.pipeline import run_pipeline
from ocapi.types import ArreteFile, ArreteId, parse_filename, validate_arretify_version
from ocapi.utils.logging_utils import get_logger, initialize_root_logger

logger = get_logger(__name__)


def load_arrete_files(input_dir: Path, aiot: str) -> list[ArreteFile]:
    """
    Charge tous les fichiers HTML d'arrêtés depuis un répertoire.

    Args:
        input_dir: Répertoire contenant les fichiers HTML
        aiot: Identifiant AIOT de l'installation

    Returns:
        Liste des ArreteFile chargés, triés par nom de fichier
    """
    arrete_files: list[ArreteFile] = []

    html_files = sorted(input_dir.glob("*.html"))
    if not html_files:
        logger.error(f"Aucun fichier HTML trouvé dans {input_dir}")
        return []

    for _ordered_index, html_path in enumerate(html_files):
        # Parser et valider le nom de fichier
        try:
            arrete_id, file_type = parse_filename(html_path.name)
        except ValueError as e:
            logger.warning(f"Fichier ignoré (format invalide): {html_path.name} - Raison: {e}")
            continue

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Valider la version Arrêtify
        try:
            validate_arretify_version(soup, html_path.name)
        except ValueError as e:
            logger.warning(
                f"Fichier ignoré (version Arrêtify incompatible): {html_path.name} - Raison: {e}"
            )
            continue

        arrete = ArreteFile(
            id=arrete_id,
            aiot=aiot,
            filename=html_path.name,
            soup=soup,
            file_type=file_type,
        )
        arrete_files.append(arrete)
        logger.info(f"Chargé: {html_path.name} (id={arrete_id}, type={file_type.value})")

    return arrete_files


def cmd_run(args: argparse.Namespace) -> int:
    """Exécute le pipeline OCAPI sur les arrêtés."""
    input_dir = Path(args.input_dir)

    if not input_dir.exists():
        logger.error(f"Le répertoire {input_dir} n'existe pas.")
        return 1

    if not input_dir.is_dir():
        logger.error(f"{input_dir} n'est pas un répertoire.")
        return 1

    # Déterminer l'AIOT
    aiot = args.aiot or input_dir.parent.name
    logger.info(f"AIOT: {aiot}")
    logger.info(f"Modèle LLM: {settings.pipeline.default_llm_model}")
    logger.info(f"Chargement des arrêtés depuis: {input_dir}")

    # Charger les arrêtés
    arrete_files = load_arrete_files(input_dir, aiot)
    if not arrete_files:
        return 1

    logger.info(f"{len(arrete_files)} arrêté(s) chargé(s)")

    # Filtrer les arrêtés si demandé
    if args.include:
        arrete_ids_included = set(args.include)
        logger.info(f"Filtrage sur: {arrete_ids_included}")
        arrete_files = [af for af in arrete_files if af.id in arrete_ids_included]
        logger.info(f"{len(arrete_files)} arrêté(s) après filtrage")

        if not arrete_files:
            logger.error("Aucun arrêté ne correspond aux IDs spécifiés")
            return 1

    # Exécuter le pipeline
    logger.info("Exécution du pipeline...")
    try:
        permis = run_pipeline(arrete_files)
        logger.info("Pipeline terminé avec succès.")

        # Sauvegarder le résultat si --output est spécifié
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(permis.model_dump_json(indent=2), encoding="utf-8")
            logger.info(f"Résultat sauvegardé dans: {output_path}")

        return 0

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du pipeline: {e}")
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
  
  # Sauvegarder le résultat dans un fichier JSON
  ocapi run data/0999.99999/arretes/ --output output/resultat.json
  
  # Combinaison: filtrage et sauvegarde
  ocapi run data/0999.99999/arretes/ --include 2024-09-27 --output resultat.json
  
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
        "-o",
        "--output",
        help="Fichier de sortie pour le résultat (JSON)",
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

    logger.debug(f"Logging initialisé au niveau {log_level}")

    if args.command is None:
        parser.print_help()
        return 0

    # Appeler la fonction associée à la commande
    func = args.func
    result: int = func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
