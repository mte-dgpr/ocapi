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
Logic for extracting an operation's content (operand) from a parsed HTML block,
using start and end markers to locate the relevant text.
"""

from bs4 import BeautifulSoup

from ocapi.types import StatusCode
from ocapi.utils.arretify_utils import (
    rehydrate_images,
)
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.utils import find_marker

_LOGGER = get_logger(__name__)
ImageMap = dict[str, str]  # mapping from placeholder src to real src


def pick_arretify_section(
    html: str, source_article: str, operation_id: str | None = None
) -> str | None:
    """Extract the HTML of a specific Arrêtify section from an HTML block.

    Parameters
    ----------
    html : str
        Full HTML block to search in.
    source_article : str
        Article identifier to locate (e.g. "2.1", "APPENDIX", "APPENDIX:3.1").
    operation_id : str | None
        Optional operation ID for error messages.

    Returns
    -------
    str | None
        HTML string of the found section, or ``None`` if not found.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Case 1: "APPENDIX" — return the entire appendix footer
    if source_article == "APPENDIX":
        footer = soup.find("footer", attrs={"data-spec": "appendix"})
        if footer:
            return str(footer)
        _LOGGER.error(
            f"No appendix footer found when extracting operand"
            f"{f' for operation {operation_id}' if operation_id else ''}"
        )
        return None

    # Case 2: "APPENDIX:X" or "APPENDIX:X.Y.Z" — search inside the appendix footer
    if source_article.startswith("APPENDIX:"):
        appendix_number = source_article.split("APPENDIX:", 1)[1]
        footer = soup.find("footer", attrs={"data-spec": "appendix"})
        if footer:
            for section in footer.find_all("section", attrs={"data-spec": "section"}):
                data_number = section.get("data-number")
                if data_number == appendix_number:
                    return str(section)
        _LOGGER.error(
            f"Section {source_article} not found in appendix"
            f"{f' for operation {operation_id}' if operation_id else ''}"
        )
        return None

    # Case 3: Normal article (e.g. "2.1.3")
    for section in soup.find_all("section", attrs={"data-spec": "section"}):
        data_number = section.get("data-number")
        if data_number == source_article:
            return str(section)

    op_info = f" for operation {operation_id}" if operation_id else ""
    _LOGGER.error(f"Section {source_article} not found when extracting operand{op_info}")
    return None


def extract_operand_with_images(
    html_block: str,
    source_article: str,
    start_marker: str,
    end_marker: str,
    img_map: ImageMap,
    operation_id: str | None = None,
) -> tuple[str | None, StatusCode]:
    """Extract the operand HTML between two markers, restoring original image URLs.

    Parameters
    ----------
    html_block : str
        Full HTML block in which the operand is located.
    source_article : str
        Article identifier used to narrow the search to a specific section.
    start_marker : str
        Text marker indicating the start of the operand (inclusive).
    end_marker : str
        Text marker indicating the end of the operand (inclusive).
    img_map : ImageMap
        Mapping from placeholder token to original image URL.
    operation_id : str | None
        Optional operation ID for error messages.

    Returns
    -------
    tuple[str | None, StatusCode]
        A ``(operand, status_code)`` pair. On success, ``operand`` is the extracted
        HTML with images rehydrated and ``status_code`` is ``StatusCode.RESOLVED``.
        On failure, ``operand`` is ``None`` and ``status_code`` is
        ``StatusCode.ERROR_EXTRACTING_OPERAND``.
    """
    section = pick_arretify_section(html_block, source_article, operation_id)
    op_info = f" for operation {operation_id}" if operation_id else ""

    # Try the section first; fall back to the full HTML block if the marker isn't found there
    working_html: str = html_block
    start_idx = -1
    if section is not None:
        start_idx = find_marker(section, start_marker)
        if start_idx != -1:
            working_html = section

    if start_idx == -1:
        start_idx = find_marker(html_block, start_marker)
        working_html = html_block
        if start_idx == -1:
            _LOGGER.warning("Start marker not found%s", op_info)
            return None, StatusCode.ERROR_EXTRACTING_OPERAND

    end_idx = find_marker(working_html, end_marker)
    if end_idx != -1:
        html_fragment = working_html[start_idx : end_idx + len(end_marker)]
        html_fragment = rehydrate_images(html_fragment, img_map)
        return html_fragment, StatusCode.RESOLVED
    else:
        _LOGGER.warning("End marker not found%s", op_info)
        return None, StatusCode.ERROR_EXTRACTING_OPERAND
