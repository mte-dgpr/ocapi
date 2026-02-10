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
Utilitaires pour les opérations d'entrée/sortie (input/output).
"""
import json
from pathlib import Path
from typing import Any, cast

from bs4 import BeautifulSoup

from ocapi.types import ArreteFile, Permis, parse_filename, validate_arretify_version
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def read_json(p: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(p.read_text(encoding="utf-8")))


class InputOutputError(Exception):
    """Exception levée en cas d'erreur sur les chemins input/output."""

    pass


def load_html_files(input_dir: Path) -> list[Path]:
    """
    Charge tous les fichiers HTML depuis un répertoire d'entrée.

    Args:
        input_dir: Répertoire contenant les fichiers HTML

    Returns:
        Liste triée des chemins vers les fichiers HTML trouvés

    Raises:
        InputOutputError: Si le répertoire n'existe pas, n'est pas un répertoire,
                         ou ne contient aucun fichier HTML
    """
    # Vérifier que le répertoire existe
    if not input_dir.exists():
        raise InputOutputError(f"Le répertoire d'entrée n'existe pas: {input_dir}")

    # Vérifier que c'est bien un répertoire
    if not input_dir.is_dir():
        raise InputOutputError(f"Le chemin spécifié n'est pas un répertoire: {input_dir}")

    # Charger les fichiers HTML
    html_files = sorted(input_dir.glob("*.html"))

    # Vérifier qu'il y a au moins un fichier
    if not html_files:
        raise InputOutputError(f"Aucun fichier HTML trouvé dans: {input_dir}")

    return html_files


def initialize_arrete_files(html_files: list[Path], aiot: str) -> list["ArreteFile"]:
    """
    Initialise les objets ArreteFile à partir d'une liste de fichiers HTML.
    """
    arrete_files: list[ArreteFile] = []

    for html_path in html_files:
        try:
            arrete_id, file_type = parse_filename(html_path.name)
        except ValueError as e:
            _LOGGER.warning(f"Fichier ignoré (format invalide): {html_path.name} - Raison: {e}")
            continue

        # Charger le contenu HTML
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Valider la version Arrêtify
        try:
            validate_arretify_version(soup, html_path.name)
        except ValueError as e:
            _LOGGER.warning(
                f"Fichier ignoré (version Arrêtify incompatible): {html_path.name} - Raison: {e}"
            )
            continue

        # Créer l'objet ArreteFile
        arrete = ArreteFile(
            id=arrete_id,
            aiot=aiot,
            filename=html_path.name,
            soup=soup,
            file_type=file_type,
        )
        arrete_files.append(arrete)
        file_type_str = file_type.value if file_type else "unknown"
        _LOGGER.info(f"Chargé: {html_path.name} (id={arrete_id}, type={file_type_str})")

    return arrete_files


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
    _LOGGER.info(f"Chargement des arrêtés depuis: {input_dir}")
    html_files = load_html_files(input_dir)
    _LOGGER.info(f"Chargement de {len(html_files)} fichiers HTML")
    arrete_files = initialize_arrete_files(html_files, aiot)
    _LOGGER.info(f"{len(arrete_files)} arrêté(s) chargé(s)")
    return arrete_files


def write_permis_output(permis: Permis, output_path: Path) -> None:
    """
    Écrit le permis consolidé dans un fichier de sortie.
    """
    try:
        # Créer le répertoire parent si nécessaire
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix in [".html", ".htm"]:
            # Sauvegarder en HTML
            output_path.write_text(permis.to_html(), encoding="utf-8")
        else:
            # Par défaut, sauvegarder en JSON
            output_path.write_text(permis.model_dump_json(indent=2), encoding="utf-8")

    except OSError as e:
        raise InputOutputError(f"Impossible d'écrire dans le fichier de sortie: {e}") from e


def write_json_output(data: Any, output_path: Path) -> None:
    """
    Écrit des données dans un fichier JSON.

    Args:
        data: Données à sauvegarder (dict, list, ou tout objet sérialisable en JSON)
        output_path: Chemin du fichier de sortie

    Raises:
        InputOutputError: Si l'écriture échoue
    """
    try:
        # Créer le répertoire parent si nécessaire
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Sauvegarder en JSON
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except OSError as e:
        raise InputOutputError(f"Impossible d'écrire le fichier JSON: {e}") from e
