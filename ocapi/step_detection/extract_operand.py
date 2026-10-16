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
Logic for extracting an operation's content (operand) from a parsed HTML block,
using start and end markers to locate the relevant text.
"""

from bs4 import BeautifulSoup, Tag

from ocapi.utils.arretify_utils import (
    ARRETIFY_APPENDIX_DATA_SPEC,
    ARRETIFY_SECTION_DATA_SPEC,
    rehydrate_images,
)
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.utils import find_marker_span

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
        footer = soup.find("footer", attrs={"data-spec": ARRETIFY_APPENDIX_DATA_SPEC})
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
        footer = soup.find("footer", attrs={"data-spec": ARRETIFY_APPENDIX_DATA_SPEC})
        if isinstance(footer, Tag):
            for section in footer.find_all(
                "section", attrs={"data-spec": ARRETIFY_SECTION_DATA_SPEC}
            ):
                data_number = section.get("data-number")
                if data_number == appendix_number:
                    return str(section)
        _LOGGER.error(
            f"Section {source_article} not found in appendix"
            f"{f' for operation {operation_id}' if operation_id else ''}"
        )
        return None

    # Case 3: Normal article (e.g. "2.1.3")
    for section in soup.find_all("section", attrs={"data-spec": ARRETIFY_SECTION_DATA_SPEC}):
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
) -> str | None:
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
    str | None
        The extracted HTML with images rehydrated, or ``None`` when either the
        start or end marker cannot be located.
    """
    section = pick_arretify_section(html_block, source_article, operation_id)
    op_info = f" for operation {operation_id}" if operation_id else ""

    # Try the section first, then the full HTML block; an exact match anywhere is
    # preferred over a text-only match, which is only tried as a last resort.
    candidates = [html for html in (section, html_block) if html is not None]
    located = next(
        (
            (html, span[0])
            for text_only in (False, True)
            for html in candidates
            if (span := find_marker_span(html, start_marker, text_only=text_only)) is not None
        ),
        None,
    )
    if located is None:
        _LOGGER.warning("Start marker not found%s", op_info)
        return None
    working_html, start_idx = located

    end_span = find_marker_span(working_html, end_marker, start=start_idx)
    if end_span is not None:
        html_fragment = working_html[start_idx : end_span[1]]
        return rehydrate_images(html_fragment, img_map)
    _LOGGER.warning("End marker not found%s", op_info)
    return None
