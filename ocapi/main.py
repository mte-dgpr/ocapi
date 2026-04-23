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
"""
Main entry point for running the OCAPI pipeline.

Usage:
    python -m ocapi.main <input_dir> [options]
    python ocapi/main.py <input_dir> [options]

Examples:
    python -m ocapi.main snapshots/arretes_html/<AIOT>/
    python -m ocapi.main snapshots/arretes_html/<AIOT>/ --output output/
    python -m ocapi.main snapshots/arretes_html/<AIOT>/ --start-date 2014-01-09
    python -m ocapi.main snapshots/arretes_html/<AIOT>/ --include 2024-09-27 2023-12-04
    python -m ocapi.main snapshots/arretes_html/<AIOT>/ --no-rendering
"""

import argparse
import sys
from pathlib import Path

from ocapi.config import settings
from ocapi.exceptions import OcapiError
from ocapi.llm_utils import config_model_llm
from ocapi.pipeline import run_pipeline
from ocapi.step_rendering.step_rendering import permis_to_html
from ocapi.types import Operation
from ocapi.utils.io_utils import (
    InputOutputError,
    article_history_to_json_dict,
    load_document_contexts,
    load_operations,
    save_tagged_html_file,
    write_json_output,
    write_permis_output,
)
from ocapi.utils.logging_utils import get_logger, initialize_root_logger

_LOGGER = get_logger(__name__)


def main(
    input_dir: Path,
    output_dir: Path | None = None,
    aiot: str | None = None,
    include_ids: list[str] | None = None,
    start_date: str | None = None,
    enable_rendering: bool = True,
    enable_tagging: bool = True,
    operations_from: Path | None = None,
    principal_id: str | None = None,
    tagged_output_dir: Path | None = None,
) -> int:
    """Run the complete OCAPI pipeline end to end.

    Args:
        input_dir: Directory containing the arrêté HTML files.
        output_dir: Output directory. When specified all outputs are written
            into this single directory. When omitted the outputs are placed in
            ``<input_dir>/../../arretes_consolidation/<aiot>/``.
        aiot: AIOT identifier (defaults to the input directory name).
        include_ids: List of arrêté IDs to include (defaults to all).
        start_date: Detection start date (YYYY-MM-DD).
        enable_rendering: If True, generate the consolidated permit.
        enable_tagging: If False, skip ``step_tagging`` and the tagged HTML output.
            Pre-existing Arrêtify tags in the input HTML are used as-is.
        operations_from: If set, loads ``operations.json`` from that directory; skips detection.
        principal_id: Date (YYYY-MM-DD) of the arrêté to flag as principal.
            Returns an error when no loaded arrêté matches that date.
        tagged_output_dir: Output directory for HTMLs emitted after ``step_tagging``.
            When None the outputs are placed in ``<input_dir>/../../arretes_tagged/<aiot>/``.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    _LOGGER.info(f"Input directory: {input_dir}")

    # Determine AIOT
    if aiot is None:
        aiot = input_dir.name
    _LOGGER.info(f"AIOT: {aiot}")
    _LOGGER.info(f"LLM model: {config_model_llm().model_name}")

    # Load arrêtés
    try:
        pairs = load_document_contexts(input_dir, aiot)
    except InputOutputError as e:
        _LOGGER.error(f"Error: {e}")
        return 1

    if not pairs:
        _LOGGER.error("No valid arrêté found")
        return 1

    _LOGGER.info(f"{len(pairs)} arrêté(s) loaded")

    # Filter arrêtés if requested
    if include_ids:
        arrete_ids_included = set(include_ids)
        _LOGGER.info(f"Filtering on: {arrete_ids_included}")
        pairs = [(af, dc) for af, dc in pairs if af.id in arrete_ids_included]
        _LOGGER.info(f"{len(pairs)} arrêté(s) after filtering")

        if not pairs:
            _LOGGER.error("No arrêté matches the specified IDs")
            return 1

    arrete_files = [af for af, _ in pairs]
    document_contexts = [dc for _, dc in pairs]

    if principal_id is not None:
        matches = [af for af in arrete_files if af.id == principal_id]
        if not matches:
            _LOGGER.error(f"No arrêté found for --principal-id {principal_id}")
            return 1
        for af in matches:
            af.principal = True
        _LOGGER.info(f"Principal arrêté: {principal_id}")

    # Determine output paths
    if output_dir:
        consolidation_dir = output_dir
    else:
        base_dir = input_dir.parent.parent
        consolidation_dir = base_dir / "arretes_consolidation" / aiot

    if tagged_output_dir:
        tagged_dir = tagged_output_dir
    else:
        tagged_dir = input_dir.parent.parent / "arretes_tagged" / aiot

    preloaded_ops: list[Operation] | None = None
    if operations_from is not None:
        try:
            preloaded_ops = load_operations(operations_from)
        except InputOutputError as e:
            _LOGGER.error(f"Error: {e}")
            return 1
        _LOGGER.info(f"Loaded {len(preloaded_ops)} operation(s) from {operations_from}")

    enable_detection = operations_from is None

    try:
        # Run the pipeline
        operations, history, arrete_files, permis = run_pipeline(
            arrete_files,
            start_date=start_date,
            enable_detection=enable_detection,
            enable_rendering=enable_rendering,
            enable_tagging=enable_tagging,
            operations=preloaded_ops,
            document_contexts=document_contexts,
        )

        # Save tagged HTMLs
        if enable_tagging:
            for arrete_file, document_context in zip(arrete_files, document_contexts):
                save_tagged_html_file(document_context, tagged_dir / arrete_file.filename)
            _LOGGER.info(f"Tagged HTML saved → {tagged_dir}")

        # Save operations
        operations_path = consolidation_dir / "operations.json"
        operations_dict = [op.model_dump(mode="json") for op in operations]
        write_json_output(operations_dict, operations_path)
        _LOGGER.info(f"Operations saved → {operations_path}")

        # Save history
        history_path = consolidation_dir / "history.json"
        write_json_output(article_history_to_json_dict(history), history_path)
        _LOGGER.info(f"History saved → {history_path}")

        # Save permit if generated
        if permis:
            permis_path = consolidation_dir / "permis.html"
            write_permis_output(permis_to_html(permis), permis_path)
            _LOGGER.info(f"Consolidated permit saved → {permis_path}")

        _LOGGER.info("Pipeline completed successfully!")
        return 0

    except OcapiError as e:
        _LOGGER.error(f"OCAPI error: {e}")
        return 1
    except Exception as e:
        _LOGGER.exception(f"Unexpected error while running the pipeline: {e}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="ocapi.main",
        description=(
            "OCAPI - Consolidation operations detection, resolution, and rendering pipeline"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all arrêtés in a directory
  python -m ocapi.main snapshots/arretes_html/<AIOT>/

  # Specify a custom output directory
  python -m ocapi.main snapshots/arretes_html/<AIOT>/ --output output/

  # Start detection from a given date
  python -m ocapi.main snapshots/arretes_html/<AIOT>/ --start-date 2014-01-09

  # Filter on specific arrêtés
  python -m ocapi.main snapshots/arretes_html/<AIOT>/ --include 2024-09-27 2023-12-04

  # Disable rendering (steps 1-3 only)
  python -m ocapi.main snapshots/arretes_html/<AIOT>/ --no-rendering

  # Specify AIOT
  python -m ocapi.main snapshots/arretes_html/<AIOT>/ --aiot <AIOT>

  # Verbose mode
  python -m ocapi.main snapshots/arretes_html/<AIOT>/ --verbose
        """,
    )

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing the arrêté HTML files",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Output directory. When specified all outputs go into this single directory. "
            "By default outputs go into arretes_consolidation/ relative to <input_dir>/."
        ),
    )
    parser.add_argument(
        "--aiot",
        help="AIOT identifier (default: inferred from parent directory name)",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        metavar="ID",
        help="Arrêté IDs to include (default: all)",
    )
    parser.add_argument(
        "--start-date",
        metavar="YYYY-MM-DD",
        help="Start date: only arrêtés >= this date go through detection",
    )
    parser.add_argument(
        "--operations-from",
        type=Path,
        metavar="DIR",
        help="Directory containing operations.json (skips detection; snapshot mode, no LLM)",
    )
    parser.add_argument(
        "--principal-id",
        metavar="YYYY-MM-DD",
        help="Date of the arrêté to flag as principal (must match a loaded arrêté)",
    )
    parser.add_argument(
        "--tagged-output",
        type=Path,
        metavar="DIR",
        help=(
            "Output directory for HTMLs emitted after step_tagging. "
            "Defaults to arretes_tagged/<aiot>/ relative to <input_dir>/../../."
        ),
    )
    parser.add_argument(
        "--no-rendering",
        action="store_true",
        help="Skip consolidated permit generation (step 4)",
    )
    parser.add_argument(
        "--no-tagging",
        action="store_true",
        help=(
            "Skip step_tagging and the tagged HTML output. Pre-existing "
            "Arrêtify tags in the input HTML are still read as-is."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose mode (DEBUG level)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet mode (shows WARNING, ERROR, CRITICAL only)",
    )

    args = parser.parse_args()

    log_level = settings.logging.level
    if args.verbose:
        log_level = "DEBUG"
    elif args.quiet:
        log_level = "WARNING"

    initialize_root_logger(
        level=log_level,
        log_file=settings.logging.log_file,
        max_bytes=settings.logging.max_bytes,
        backup_count=settings.logging.backup_count,
        use_timed_rotation=settings.logging.use_timed_rotation,
        console_output=settings.logging.console_output,
    )

    _LOGGER.debug(f"Logging initialised at level {log_level}")

    operations_from = getattr(args, "operations_from", None)
    tagged_output = getattr(args, "tagged_output", None)

    exit_code = main(
        input_dir=args.input_dir,
        output_dir=args.output,
        aiot=args.aiot,
        include_ids=args.include,
        start_date=args.start_date,
        enable_rendering=not args.no_rendering,
        enable_tagging=not args.no_tagging,
        operations_from=operations_from,
        principal_id=args.principal_id,
        tagged_output_dir=tagged_output,
    )

    sys.exit(exit_code)
