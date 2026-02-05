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
        print(f"Aucun fichier HTML trouvé dans {input_dir}", file=sys.stderr)
        return []

    for _ordered_index, html_path in enumerate(html_files):
        # Parser et valider le nom de fichier
        try:
            arrete_id, file_type = parse_filename(html_path.name)
        except ValueError as e:
            print(f"⚠️  Fichier ignoré (format invalide): {html_path.name}", file=sys.stderr)
            print(f"   Raison: {e}", file=sys.stderr)
            continue

        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Valider la version Arrêtify
        try:
            validate_arretify_version(soup, html_path.name)
        except ValueError as e:
            print(
                f"⚠️  Fichier ignoré (version Arrêtify incompatible): {html_path.name}",
                file=sys.stderr,
            )
            print(f"   Raison: {e}", file=sys.stderr)
            continue

        arrete = ArreteFile(
            id=arrete_id,
            aiot=aiot,
            filename=html_path.name,
            soup=soup,
            file_type=file_type,
        )
        arrete_files.append(arrete)
        print(f"  Chargé: {html_path.name} (id={arrete_id}, type={file_type.value})")

    return arrete_files


def cmd_run(args: argparse.Namespace) -> int:
    """Exécute le pipeline OCAPI sur les arrêtés."""
    input_dir = Path(args.input_dir)

    if not input_dir.exists():
        print(f"Erreur: Le répertoire {input_dir} n'existe pas.", file=sys.stderr)
        return 1

    if not input_dir.is_dir():
        print(f"Erreur: {input_dir} n'est pas un répertoire.", file=sys.stderr)
        return 1

    # Déterminer l'AIOT
    aiot = args.aiot or input_dir.parent.name
    print(f"AIOT: {aiot}")
    print(f"Modèle LLM: {settings.pipeline.default_llm_model}")
    print(f"Chargement des arrêtés depuis: {input_dir}")

    # Charger les arrêtés
    arrete_files = load_arrete_files(input_dir, aiot)
    if not arrete_files:
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
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(permis.model_dump_json(indent=2), encoding="utf-8")
            print(f"Résultat sauvegardé dans: {output_path}")

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
