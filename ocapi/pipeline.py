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
    enable_detection: bool = True,
    enable_rendering: bool = True,
    enable_llm: bool = True,
    operations: list[Operation] | None = None,
) -> tuple[list[Operation], ArticleHistory, list[ArreteFile], Permis | None]:
    """Run the full OCAPI pipeline.

    Parameters
    ----------
    arrete_files : list[ArreteFile]
        Arrêtés to process, sorted chronologically.
    start_date : str | None
        Detection start date (YYYY-MM-DD). Arrêtés with id <= this date are skipped
        during detection but remain available for resolution and rendering.
        Defaults to the id of the first arrêté.
    enable_detection : bool
        If True, run the detection step (steps 1-2).
    enable_rendering : bool
        If True, generate the consolidated permit (step 4).
    operations : list[Operation] | None
        Pre-loaded operations to use when enable_detection is False (snapshot mode).
        Callers load from disk via :func:`ocapi.utils.io_utils.load_operations` when needed.

    Returns
    -------
    tuple[list[Operation], ArticleHistory, list[ArreteFile], Permis | None]
        Tuple (operations, history, arrete_files, permis).
    """
    _LOGGER.info(f"Starting pipeline with {len(arrete_files)} arrêté(s)")
    if start_date is None and arrete_files:
        start_date = arrete_files[0].id
    if start_date:
        _LOGGER.info(f"Detection start date: {start_date}")

    ops: list[Operation] = operations if operations is not None else []

    if enable_detection:
        # ========================================
        # STEP 1-2: CHUNKING + DETECTION
        # ========================================
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 1-2: CHUNKING + DETECTION")
        _LOGGER.info("=" * 60)

        for _i, arrete_file in enumerate(arrete_files):
            if start_date and arrete_file.id <= start_date:
                _LOGGER.info(
                    f"Arrêté {arrete_file.id} dated on or before {start_date},"
                    " skipping operation detection"
                )
                continue
            _LOGGER.info(f"Processing arrêté {arrete_file.id}...")
            docs, img_map = step_chunking(arrete_file)
            _LOGGER.info(f"  → {len(docs)} documents chunked")
            _LOGGER.debug(f"  → {len(img_map)} images mapped")

            detected_ops = step_detection(docs, arrete_file.id, img_map)
            ops.extend(detected_ops)
            _LOGGER.info(f"  → {len(detected_ops)} operations detected")
    else:
        _LOGGER.info(f"Using {len(ops)} pre-loaded operation(s) (snapshot mode, no LLM)")

    _LOGGER.info(f"Total: {len(ops)} operation(s) detected")

    # ========================================
    # STEP 3: RESOLUTION
    # ========================================
    _LOGGER.info("=" * 60)
    _LOGGER.info("STEP 3: RESOLUTION")
    _LOGGER.info("=" * 60)

    history, arrete_files, ops = step_resolution(ops, arrete_files, enable_llm=enable_llm)
    if history:
        _LOGGER.info(f"{len(history)} articles with history")
    else:
        _LOGGER.info("0 articles with history")

    # ========================================
    # STEP 4: RENDERING (optional)
    # ========================================
    permis = None
    if enable_rendering:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 4: RENDERING")
        _LOGGER.info("=" * 60)

        permis = step_rendering(history, ops, arrete_files)
        _LOGGER.info("Consolidated permit generated")

    _LOGGER.info("Pipeline completed successfully!")
    return ops, history, arrete_files, permis
