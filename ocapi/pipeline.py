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
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_detection.step_detection import step_detection
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import ArreteFile, ArticleHistory, Operation, Permis
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def run_pipeline(
    arrete_files: list[ArreteFile],
    start_date: str | None = None,
    enable_rendering: bool = True,
) -> tuple[list[Operation], ArticleHistory, list[ArreteFile], Permis | None]:
    """
    Exécute le pipeline OCAPI complet.

    Args:
        arrete_files: Liste des arrêtés à traiter
        start_date: Date de démarrage (YYYY-MM-DD). Seuls les arrêtés >= cette date
            passent par la détection. Les arrêtés antérieurs restent disponibles
            pour la résolution et le rendering.
        enable_rendering: Si True, génère le permis consolidé (étape 4)

    Returns:
        Tuple (operations, history, arrete_files, permis)
    """
    _LOGGER.info(f"Démarrage du pipeline avec {len(arrete_files)} arrêté(s)")
    if start_date is None and arrete_files:
        start_date = arrete_files[0].id
    if start_date:
        _LOGGER.info(f"Date de démarrage de la détection : {start_date}")

    operations: list[Operation] = []

    # ========================================
    # STEP 1-2 : CHUNKING + DETECTION
    # ========================================
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 1-2 : CHUNKING + DETECTION")
    _LOGGER.info("=" * 60)

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
