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
Utilities for input/output operations.
"""
import json
from pathlib import Path
from typing import Any, cast

from bs4 import BeautifulSoup

from ocapi.exceptions import InputOutputError, InvalidFileFormatError
from ocapi.types import ArreteFile, Permis, parse_filename, validate_arretify_version
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)

# Re-export for backward compatibility
__all__ = [
    "InputOutputError",
    "load_html_files",
    "initialize_arrete_files",
    "load_arrete_files",
    "write_permis_output",
    "write_json_output",
    "read_json",
]


def read_json(p: Path) -> dict[str, Any]:
    """Read a JSON file and return its content as a dictionary.

    Parameters
    ----------
    p : Path
        Path to the JSON file.

    Returns
    -------
    dict[str, Any]
        Deserialised JSON content.
    """
    return cast(dict[str, Any], json.loads(p.read_text(encoding="utf-8")))


def load_html_files(input_dir: Path) -> list[Path]:
    """Load all HTML files from an input directory.

    Args:
        input_dir: Directory containing the HTML files.

    Returns:
        Sorted list of paths to the HTML files found.

    Raises:
        InputOutputError: If the directory does not exist, is not a directory,
                         or contains no HTML files.
    """
    if not input_dir.exists():
        raise InputOutputError(f"Input directory does not exist: {input_dir}")

    if not input_dir.is_dir():
        raise InputOutputError(f"Specified path is not a directory: {input_dir}")

    html_files = sorted(input_dir.glob("*.html"))

    if not html_files:
        raise InputOutputError(f"No HTML files found in: {input_dir}")

    return html_files


def initialize_arrete_files(html_files: list[Path], aiot: str) -> list["ArreteFile"]:
    """Initialise ArreteFile objects from a list of HTML files."""
    arrete_files: list[ArreteFile] = []

    for html_path in html_files:
        try:
            arrete_id, file_type = parse_filename(html_path.name)
        except InvalidFileFormatError as e:
            _LOGGER.warning(f"File skipped (invalid format): {html_path.name} - Reason: {e}")
            continue

        # Load HTML content
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Validate Arrêtify version
        try:
            validate_arretify_version(soup, html_path.name)
        except InvalidFileFormatError as e:
            _LOGGER.warning(
                f"File skipped (incompatible Arrêtify version): {html_path.name} - Reason: {e}"
            )
            continue

        # Create ArreteFile object
        arrete = ArreteFile(
            id=arrete_id,
            aiot=aiot,
            filename=html_path.name,
            soup=soup,
            file_type=file_type,
        )
        arrete_files.append(arrete)
        file_type_str = file_type.value if file_type else "unknown"
        _LOGGER.info(f"Loaded: {html_path.name} (id={arrete_id}, type={file_type_str})")

    return arrete_files


def load_arrete_files(input_dir: Path, aiot: str) -> list[ArreteFile]:
    """Load all HTML arrêté files from a directory.

    Parameters
    ----------
    input_dir : Path
        Directory containing the HTML files.
    aiot : str
        AIOT identifier of the installation.

    Returns
    -------
    list[ArreteFile]
        Loaded ArreteFile objects, sorted by filename.

    Raises
    ------
    InputOutputError
        If loading fails.
    """
    _LOGGER.info(f"Loading arrêtés from: {input_dir}")
    html_files = load_html_files(input_dir)
    _LOGGER.info(f"Loading {len(html_files)} HTML files")
    arrete_files = initialize_arrete_files(html_files, aiot)
    _LOGGER.info(f"{len(arrete_files)} arrêté(s) loaded")
    return arrete_files


def write_permis_output(permis: Permis, output_path: Path) -> None:
    """Write the consolidated permit to an output file."""
    try:
        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix in [".html", ".htm"]:
            # Save as HTML
            output_path.write_text(permis.to_html(), encoding="utf-8")
        else:
            # Default: save as JSON
            output_path.write_text(permis.model_dump_json(indent=2), encoding="utf-8")

    except OSError as e:
        raise InputOutputError(f"Cannot write to output file: {e}") from e


def write_json_output(data: Any, output_path: Path) -> None:
    """Write data to a JSON file.

    Parameters
    ----------
    data : Any
        Data to save (dict, list, or any JSON-serialisable object).
    output_path : Path
        Output file path.

    Raises
    ------
    InputOutputError
        If writing fails.
    """
    try:
        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except OSError as e:
        raise InputOutputError(f"Cannot write JSON file: {e}") from e
