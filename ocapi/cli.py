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
Command-line interface for OCAPI.

Usage:
    ocapi run <input_dir> [--aiot AIOT] [--output OUTPUT]
    ocapi --help
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


def run_main(
    input_dir: Path,
    *,
    enable_detection: bool = True,
    enable_rendering: bool = True,
    include_ids: list[str] | None = None,
    aiot: str | None = None,
    output_dir: Path | None = None,
    start_date: str | None = None,
) -> int:
    """Run the OCAPI pipeline with explicit parameters.

    Parameters
    ----------
    input_dir : Path
        Directory containing the arrêté HTML files.
    enable_detection : bool
        If False, skip the detection step (steps 1–2).
    enable_rendering : bool
        If False, skip the rendering step (step 4).
    include_ids : list[str] | None
        Arrêté IDs to include; all arrêtés are included when None.
    aiot : str | None
        AIOT identifier; inferred from the parent directory when None.
        output_dir : Path | None
        Output directory. When specified all outputs are written into this
        single directory. When omitted the outputs are placed in three
        separate canonical directories two levels above ``input_dir``:
        ``<input_dir>/../../arretes_operations/<aiot>/``,
        ``<input_dir>/../../arretes_history/<aiot>/`` and
        ``<input_dir>/../../consolidated_permit/<aiot>/``.
    start_date : str | None
        Detection start date (YYYY-MM-DD).
    """
    resolved_aiot = aiot or input_dir.name
    _LOGGER.info(f"AIOT: {resolved_aiot}")
    _LOGGER.info(f"LLM model: {config_model_llm().model_name}")

    try:
        arrete_files = load_arrete_files(input_dir, resolved_aiot)
    except InputOutputError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if include_ids:
        included_set = set(include_ids)
        _LOGGER.info(f"Filtering on: {included_set}")
        arrete_files = [af for af in arrete_files if af.id in included_set]
        _LOGGER.info(f"{len(arrete_files)} arrêté(s) after filtering")

        if not arrete_files:
            _LOGGER.error("No arrêté matches the specified IDs")
            return 1

    _LOGGER.info("Running pipeline...")
    try:
        operations, history, _arrete_files, permis = run_pipeline(
            arrete_files,
            start_date=start_date,
            enable_detection=enable_detection,
            enable_rendering=enable_rendering,
        )
        _LOGGER.info("Pipeline completed successfully.")

        if output_dir:
            operations_dir = output_dir
            history_dir = output_dir
            permis_dir = output_dir
        else:
            base_dir = input_dir.parent.parent
            operations_dir = base_dir / "arretes_operations" / resolved_aiot
            history_dir = base_dir / "arretes_history" / resolved_aiot
            permis_dir = base_dir / "consolidated_permit" / resolved_aiot

        operations_path = operations_dir / "operations.json"
        operations_dict = [op.model_dump(mode="json") for op in operations]
        write_json_output(operations_dict, operations_path)
        _LOGGER.info(f"Operations saved → {operations_path}")

        history_path = history_dir / "history.json"
        history_serializable = {
            str(node_id): [
                {
                    "version": v["version"],
                    "content": v["content"],
                    "operation_id": v["operation_id"],
                    "status_code": v.get("status_code"),
                }
                for v in versions
            ]
            for node_id, versions in history.items()
        }
        write_json_output(history_serializable, history_path)
        _LOGGER.info(f"History saved → {history_path}")

        if permis:
            permis_path = permis_dir / "permis.html"
            write_permis_output(permis, permis_path)
            _LOGGER.info(f"Consolidated permit saved → {permis_path}")

        return 0

    except OcapiError as e:
        _LOGGER.error(f"OCAPI error: {e}")
        return 1
    except Exception as e:
        _LOGGER.exception(f"Unexpected error while running the pipeline: {e}")
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Parse CLI args and delegate to :func:`run_main`."""
    return run_main(
        input_dir=Path(args.input_dir),
        enable_detection=not getattr(args, "no_detection", False),
        enable_rendering=not getattr(args, "no_rendering", False),
        include_ids=args.include or None,
        aiot=args.aiot or None,
        output_dir=Path(args.output) if args.output else None,
        start_date=getattr(args, "start_date", None),
    )


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ocapi",
        description=(
            "OCAPI - Consolidation operations detection, resolution, and rendering pipeline"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show general help
  ocapi --help

  # Show command help
  ocapi run --help

  # Process all arrêtés in a directory
  ocapi run examples/arretes_html/0999.99999/

  # Process with a specific AIOT
  ocapi run examples/arretes_html/0999.99999/ --aiot 0999.99999

  # Save result to a file
  ocapi run examples/arretes_html/0999.99999/ --output result.json

  # Verbose mode for debugging
  ocapi --verbose run examples/arretes_html/0999.99999/

  # Quiet mode
  ocapi --quiet run examples/arretes_html/0999.99999/
        """,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
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

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser(
        "run",
        help="Run the pipeline on arrêtés",
        description="Load arrêté HTML files and run the processing pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all arrêtés in a directory
  ocapi run examples/arretes_html/0999.99999/

  # Process with a specific AIOT (default: inferred from parent directory)
  ocapi run examples/arretes_html/0999.99999/ --aiot 0999.99999

  # Filter on specific arrêtés (by date)
  ocapi run examples/arretes_html/0999.99999/ --include 2024-09-27 2023-12-04

  # Save results to a specific directory
  ocapi run examples/arretes_html/0999.99999/ --output output/

  # Combine: filter and save
  ocapi run examples/arretes_html/0999.99999/ --include 2024-09-27 --output output/

  # Verbose mode to see detailed logs
  ocapi --verbose run examples/arretes_html/0999.99999/

  # Quiet mode (errors and warnings only)
  ocapi --quiet run examples/arretes_html/0999.99999/
        """,
    )
    run_parser.add_argument(
        "input_dir",
        help="Directory containing the arrêté HTML files",
    )
    run_parser.add_argument(
        "--aiot",
        help="AIOT identifier (default: inferred from parent directory)",
    )
    run_parser.add_argument(
        "--include",
        nargs="*",
        metavar="ID",
        help="Arrêté IDs to include (default: all)",
    )
    run_parser.add_argument(
        "--start-date",
        metavar="YYYY-MM-DD",
        help="Start date: only arrêtés >= this date go through detection",
    )
    run_parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output directory. When specified all outputs go into this single directory. "
            "By default outputs are split across arretes_operations/, arretes_history/ "
            "and consolidated_permit/ directories relative to <input_dir>/."
        ),
    )
    run_parser.add_argument(
        "--no-detection",
        action="store_true",
        default=False,
        help="Skip the detection step (steps 1-2)",
    )
    run_parser.add_argument(
        "--no-rendering",
        action="store_true",
        default=False,
        help="Skip the rendering step (step 4)",
    )
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)

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

    if args.command is None:
        parser.print_help()
        return 0

    func = args.func
    result: int = func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
