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
from pathlib import Path

from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_detection.step_detection import step_detection
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import AiotId, ArreteFile, ArticleHistory, Operation, Permis
from ocapi.utils.io_utils import load_operations, save_history, save_operations, write_permis_output
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)

_DETECTION_SUBDIR = "arretes_operations"
_RESOLUTION_SUBDIR = "arretes_history"
_RENDERING_SUBDIR = "consolidated_permit"


def _detection_dir(output_dir: Path, aiot: AiotId) -> Path:
    return output_dir / _DETECTION_SUBDIR / aiot


def _resolution_dir(output_dir: Path, aiot: AiotId) -> Path:
    return output_dir / _RESOLUTION_SUBDIR / aiot


def _rendering_dir(output_dir: Path, aiot: AiotId) -> Path:
    return output_dir / _RENDERING_SUBDIR / aiot


def run_pipeline(
    arrete_files: list[ArreteFile],
    aiot: AiotId,
    output_dir: Path,
    start_date: str | None = None,
    enable_detection: bool = True,
    enable_rendering: bool = True,
) -> tuple[list[Operation], ArticleHistory, list[ArreteFile], Permis | None]:
    """
    Exécute le pipeline OCAPI en fonction des étapes sélectionnées.

    Args:
        arrete_files: Liste des arrêtés à traiter
        aiot: Identifiant AIOT de l'installation
        output_dir: Répertoire de base pour les sorties par étape
        start_date: Date de démarrage (YYYY-MM-DD). Seuls les arrêtés dont l'id
            est strictement supérieur à cette date sont traités en détection.
            Si None, tous les arrêtés sont traités sauf le premier.
        enable_detection: Si True, lance l'étape de chunking + détection (étapes 1-2) ;
            si False, charge les opérations depuis le répertoire de détection
        enable_rendering: Si True, génère le permis consolidé (étape 4)

    Returns:
        Tuple (operations, history, arrete_files, permis)

    Raises:
        InputOutputError: Si enable_detection est False et qu'aucun fichier d'opérations
            n'est trouvé dans le répertoire de détection
    """
    steps = []
    if enable_detection:
        steps.append("detection")
    steps.append("resolution")
    if enable_rendering:
        steps.append("rendering")

    _LOGGER.info(f"Démarrage du pipeline avec {len(arrete_files)} arrêté(s)")
    if start_date is None and arrete_files:
        start_date = arrete_files[0].id
    if start_date:
        _LOGGER.info(f"Date de démarrage de la détection : {start_date}")
    _LOGGER.info(f"Étapes : {' → '.join(steps)}")

    det_dir = _detection_dir(output_dir, aiot)
    res_dir = _resolution_dir(output_dir, aiot)
    ren_dir = _rendering_dir(output_dir, aiot)

    # ========================================
    # STEP 1-2 : CHUNKING + DETECTION
    # ========================================
    if "detection" in steps:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 1-2 : CHUNKING + DÉTECTION")
        _LOGGER.info("=" * 60)

        operations: list[Operation] = []
        for _i, arrete_file in enumerate(arrete_files):
            if start_date and arrete_file.id <= start_date:
                _LOGGER.info(
                    f"Arrêté {arrete_file.id} de date antérieure ou égale à {start_date},"
                    " pas de détection des opérations"
                )
                continue
            _LOGGER.info(f"Traitement de l'arrêté {arrete_file.id}...")
            docs, img_map = step_chunking(arrete_file)
            _LOGGER.info(f"  → {len(docs)} documents chunkés")
            _LOGGER.debug(f"  → {len(img_map)} images mappées")

            detected_ops = step_detection(docs, arrete_file.id, img_map)
            operations.extend(detected_ops)
            _LOGGER.info(f"  → {len(detected_ops)} opérations détectées")

        _LOGGER.info(f"Total : {len(operations)} opération(s) détectée(s)")

        save_operations(operations, det_dir)
        _LOGGER.info(f"Opérations sauvegardées → {det_dir / 'operations.json'}")
    else:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 1-2 : CHARGEMENT DES OPÉRATIONS EXISTANTES")
        _LOGGER.info("=" * 60)

        operations = load_operations(det_dir)
        _LOGGER.info(f"{len(operations)} opération(s) chargée(s) depuis {det_dir}")

    # ========================================
    # STEP 3 : RESOLUTION
    # ========================================
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 3 : RÉSOLUTION")
    _LOGGER.info("=" * 60)

    history, arrete_files = step_resolution(operations, arrete_files)
    if history:
        _LOGGER.info(f"{len(history)} articles avec historique")
    else:
        _LOGGER.info("0 article avec historique")

    save_history(history, res_dir)
    _LOGGER.info(f"Historique sauvegardé → {res_dir / 'history.json'}")

    # ========================================
    # STEP 4 : RENDERING (optionnel)
    # ========================================
    permis = None
    if "rendering" in steps:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 4 : RENDERING")
        _LOGGER.info("=" * 60)

        permis = step_rendering(history, operations, arrete_files)
        _LOGGER.info("Permis consolidé généré")

        permis_path = ren_dir / "permis_consolidé.html"
        write_permis_output(permis, permis_path)
        _LOGGER.info(f"Permis consolidé sauvegardé → {permis_path}")

    _LOGGER.info("Pipeline terminé avec succès !")
    return operations, history, arrete_files, permis
