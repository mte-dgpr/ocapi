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
from ocapi.types import ArreteFile, ArreteId, parse_filename, validate_arretify_version
from ocapi.utils.io_utils import (
    InputOutputError,
    initialize_arrete_files,
    load_html_files,
    write_permis_output,
)


def load_arrete_files(input_dir: Path, aiot: str) -> list[ArreteFile]:
    """
    Charge tous les fichiers HTML d'arrêtés depuis un répertoire.

    Args:
        input_dir: Répertoire contenant les fichiers HTML
        aiot: Identifiant AIOT de l'installation

    Returns:
        Liste des ArreteFile chargés, triés par nom de fichier

    Raises:
        InputOutputError: Si le chargement échoue
    """
    html_files = load_html_files(input_dir)
    return initialize_arrete_files(html_files, aiot)


def cmd_run(args: argparse.Namespace) -> int:
    """Exécute le pipeline OCAPI sur les arrêtés."""
    input_dir = Path(args.input_dir)

    # Déterminer l'AIOT
    aiot = args.aiot or input_dir.parent.name
    print(f"AIOT: {aiot}")
    print(f"Modèle LLM: {settings.pipeline.default_llm_model}")
    print(f"Chargement des arrêtés depuis: {input_dir}")

    # Charger les arrêtés
    try:
        arrete_files = load_arrete_files(input_dir, aiot)
    except InputOutputError as e:
        print(f"Erreur: {e}", file=sys.stderr)
        return 1

    print(f"\n{len(arrete_files)} arrêté(s) chargé(s)")

    # Filtrer les arrêtés si demandé
    arrete_ids_included: set[ArreteId] = set()
    if args.include:
        arrete_ids_included = set(args.include)
        print(f"Filtrage sur: {arrete_ids_included}")

    # Exécuter le pipeline
    print("\nExécution du pipeline...")
    try:
        permis = run_pipeline(arrete_files)
        print("\nPipeline terminé avec succès.")

        # Sauvegarder le résultat si --output est spécifié
        if args.output:
            try:
                output_path = Path(args.output)
                write_permis_output(permis, output_path)
            except InputOutputError as e:
                print(f"Erreur: {e}", file=sys.stderr)
                return 1

        return 0

    except Exception as e:
        print(f"\nErreur lors de l'exécution du pipeline: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée principal du CLI."""
    parser = argparse.ArgumentParser(
        prog="ocapi",
        description="OCAPI - Pipeline de détection, résolution et rendu des arrêtés",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commandes disponibles")

    # Commande: run
    run_parser = subparsers.add_parser(
        "run",
        help="Exécuter le pipeline sur des arrêtés",
        description="Charge les arrêtés HTML et exécute le pipeline de traitement.",
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

    if args.command is None:
        parser.print_help()
        return 0

    # Appeler la fonction associée à la commande
    func = args.func
    result: int = func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
