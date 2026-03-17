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
Main entry point for running the OCAPI pipeline.

Usage:
    python -m ocapi.main <input_dir> [options]
    python ocapi/main.py <input_dir> [options]

Examples:
    python -m ocapi.main data/0005804239/arretes_html/
    python -m ocapi.main data/0005804239/arretes_html/ --output output/
    python -m ocapi.main data/0005804239/arretes_html/ --start-date 2014-01-09
    python -m ocapi.main data/0005804239/arretes_html/ --include 2024-09-27 2023-12-04
    python -m ocapi.main data/0005804239/arretes_html/ --no-rendering
"""

import argparse
import sys
from pathlib import Path

from ocapi.config import settings
from ocapi.exceptions import OcapiError
from ocapi.pipeline import run_pipeline
from ocapi.utils.io_utils import (
    InputOutputError,
    load_arrete_files,
    write_json_output,
    write_permis_output,
)
from ocapi.utils.llm_utils import config_model_llm
from ocapi.utils.logging_utils import get_logger, initialize_root_logger

_LOGGER = get_logger(__name__)


def main(
    input_dir: Path,
    output_dir: Path | None = None,
    aiot: str | None = None,
    include_ids: list[str] | None = None,
    start_date: str | None = None,
    enable_rendering: bool = True,
) -> int:
    """Run the complete OCAPI pipeline end to end.

    Args:
        input_dir: Directory containing the arrêté HTML files.
        output_dir: Output directory. When specified all outputs are written
            into this single directory. When omitted the outputs are placed in
            three separate canonical directories two levels above ``input_dir``:
            ``<input_dir>/../../arretes_operations/<aiot>/``,
            ``<input_dir>/../../arretes_history/<aiot>/`` and
            ``<input_dir>/../../consolidated_permit/<aiot>/``.
        aiot: AIOT identifier (defaults to the input directory name).
        include_ids: List of arrêté IDs to include (defaults to all).
        start_date: Detection start date (YYYY-MM-DD).
        enable_rendering: If True, generate the consolidated permit.

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
        arrete_files = load_arrete_files(input_dir, aiot)
    except InputOutputError as e:
        _LOGGER.error(f"Error: {e}")
        return 1

    if not arrete_files:
        _LOGGER.error("No valid arrêté found")
        return 1

    _LOGGER.info(f"{len(arrete_files)} arrêté(s) loaded")

    # Filter arrêtés if requested
    if include_ids:
        arrete_ids_included = set(include_ids)
        _LOGGER.info(f"Filtering on: {arrete_ids_included}")
        arrete_files = [af for af in arrete_files if af.id in arrete_ids_included]
        _LOGGER.info(f"{len(arrete_files)} arrêté(s) after filtering")

        if not arrete_files:
            _LOGGER.error("No arrêté matches the specified IDs")
            return 1

    # Determine output paths
    if output_dir:
        operations_dir = output_dir
        history_dir = output_dir
        permis_dir = output_dir
    else:
        base_dir = input_dir.parent.parent
        operations_dir = base_dir / "arretes_operations" / aiot
        history_dir = base_dir / "arretes_history" / aiot
        permis_dir = base_dir / "consolidated_permit" / aiot

    try:
        # Run the pipeline
        operations, history, arrete_files, permis = run_pipeline(
            arrete_files,
            start_date=start_date,
            enable_rendering=enable_rendering,
        )

        # Save operations
        operations_path = operations_dir / "operations.json"
        operations_dict = [op.model_dump(mode="json") for op in operations]
        write_json_output(operations_dict, operations_path)
        _LOGGER.info(f"Operations saved → {operations_path}")

        # Save history
        history_path = history_dir / "history.json"

        # Convert NodeId to string and ArticleHistory to serialisable format
        history_serializable = {
            str(node_id): [
                {
                    "version": v["version"],
                    "content": v["content"],
                    "operation_id": v["operation_id"],
                }
                for v in versions
            ]
            for node_id, versions in history.items()
        }

        write_json_output(history_serializable, history_path)
        _LOGGER.info(f"History saved → {history_path}")

        # Save permit if generated
        if permis:
            permis_path = permis_dir / "permis.html"
            write_permis_output(permis, permis_path)
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
  python -m ocapi.main data/0005804239/arretes_html/

  # Specify a custom output directory
  python -m ocapi.main data/0005804239/arretes_html/ --output output/

  # Start detection from a given date
  python -m ocapi.main data/0005804239/arretes_html/ --start-date 2014-01-09

  # Filter on specific arrêtés
  python -m ocapi.main data/0005804239/arretes_html/ --include 2024-09-27 2023-12-04

  # Disable rendering (steps 1-3 only)
  python -m ocapi.main data/0005804239/arretes_html/ --no-rendering

  # Specify AIOT
  python -m ocapi.main data/0005804239/arretes_html/ --aiot 0005804239

  # Verbose mode
  python -m ocapi.main data/0005804239/arretes_html/ --verbose
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
            "By default outputs are split across arretes_operations/, arretes_history/ "
            "and consolidated_permit/ directories relative to <input_dir>/."
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
        "--no-rendering",
        action="store_true",
        help="Disable consolidated permit generation (step 4)",
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

    exit_code = main(
        input_dir=args.input_dir,
        output_dir=args.output,
        aiot=args.aiot,
        include_ids=args.include,
        start_date=args.start_date,
        enable_rendering=not args.no_rendering,
    )

    sys.exit(exit_code)
