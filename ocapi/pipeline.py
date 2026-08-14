#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
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
from arretify.types import DocumentContext, protect_soup

from ocapi.step_detection.step_detection import _OPERATION_ID_COUNTER, step_detection
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.step_tagging import step_tagging
from ocapi.step_tagging.operations_filtering import filter_redundant_operations
from ocapi.types import ArreteFile, ArticleHistory, Operation, Permis
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.tagging_io import extract_operations_from_tagged_soup
from ocapi.utils.utils import make_id

_LOGGER = get_logger(__name__)


def run_pipeline(
    arrete_files: list[ArreteFile],
    start_date: str | None = None,
    enable_detection: bool = True,
    enable_rendering: bool = True,
    enable_llm: bool = True,
    operations: list[Operation] | None = None,
    document_contexts: list[DocumentContext] | None = None,
    enable_tagging: bool = True,
    enable_tagging_ops: bool = False,
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
        If True, run the detection step (step 2).
    enable_rendering : bool
        If True, generate the consolidated permit (step 4).
    operations : list[Operation] | None
        Pre-loaded operations to use when enable_detection is False (snapshot mode).
        Callers load from disk via :func:`ocapi.utils.io_utils.load_operations` when needed.
    document_contexts : list[DocumentContext] | None
        Arrêtify document contexts paired index-for-index with ``arrete_files``.
        Required when ``enable_tagging`` is True; obtained via
        :func:`ocapi.utils.io_utils.load_document_contexts`.
    enable_tagging : bool
        If True, run :func:`ocapi.step_tagging.step_tagging` on each document
        context before detection. No-op when ``document_contexts`` is None.
    enable_tagging_ops : bool
        If True, extract regex-tagged operations from the tagged HTML and merge
        them with detected operations before resolution.

    Returns
    -------
    tuple[list[Operation], ArticleHistory, list[ArreteFile], Permis | None]
        Tuple (operations, history, arrete_files, permis).
    """
    _LOGGER.info(f"Starting pipeline with {len(arrete_files)} arrêté(s)")
    # Restart operation ids from 1 for every pipeline run (each AIOT is independent).
    _OPERATION_ID_COUNTER.value = 0
    if start_date is None and arrete_files:
        start_date = arrete_files[0].id
    if start_date:
        _LOGGER.info(f"Detection start date: {start_date}")

    tagged_ops: list[Operation] = []
    candidate_ops: list[Operation] = []

    if enable_tagging and document_contexts is not None:
        if len(document_contexts) != len(arrete_files):
            raise ValueError(
                "document_contexts must align index-for-index with arrete_files "
                f"(got {len(document_contexts)} vs {len(arrete_files)})"
            )
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 1: TAGGING")
        _LOGGER.info("=" * 60)
        for arrete_file, document_context in zip(arrete_files, document_contexts):
            _LOGGER.info(f"Tagging operations in {arrete_file.id}...")
            step_tagging(document_context)
            arrete_file.soup = document_context.soup

    if enable_tagging_ops:
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 1B: TAGGING EXTRACTION")
        _LOGGER.info("=" * 60)
        for arrete_file in arrete_files:
            extracted_for_arrete = extract_operations_from_tagged_soup(
                protect_soup(arrete_file.soup),
                arrete_file.id,
                next_operation_id=lambda: make_id(_OPERATION_ID_COUNTER),
            )
            if extracted_for_arrete:
                _LOGGER.info(
                    f"  → {len(extracted_for_arrete)} operation(s) extracted from regex tagging "
                    f"for arrêté {arrete_file.id}"
                )
            tagged_ops.extend(extracted_for_arrete)
        _LOGGER.info(f"Tagging extraction total: {len(tagged_ops)} operation(s)")

    if enable_detection:
        # ========================================
        # STEP 2: DETECTION
        # ========================================
        _LOGGER.info("=" * 60)
        _LOGGER.info("STEP 2: DETECTION")
        _LOGGER.info("=" * 60)

        for arrete_file in arrete_files:
            if start_date and arrete_file.id <= start_date:
                _LOGGER.info(
                    f"Arrêté {arrete_file.id} dated on or before {start_date},"
                    " skipping operation detection"
                )
                continue
            _LOGGER.info(f"Processing arrêté {arrete_file.id}...")
            detected_ops = step_detection(arrete_file)
            candidate_ops.extend(detected_ops)
            _LOGGER.info(f"  → {len(detected_ops)} LLM operation(s) detected")
    else:
        candidate_ops = operations if operations is not None else []
        _LOGGER.info(
            f"Using {len(candidate_ops)} pre-loaded operation(s) as candidates "
            "(snapshot mode, no LLM)"
        )

    if enable_tagging_ops:
        # Merge regex-tagged operations with candidate operations in a single pass.
        # Design choice: if two operations point to the same source/target but one
        # sub-target is more precise than the other, keep the more precise one.
        # We assume the less precise variant often comes from detection limits,
        # while the precise variant carries stronger semantic targeting.
        ops = filter_redundant_operations(
            reference_ops=tagged_ops,
            candidate_ops=candidate_ops,
            context_id="pipeline",
            next_operation_id=lambda: make_id(_OPERATION_ID_COUNTER),
        )
    else:
        ops = candidate_ops

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
