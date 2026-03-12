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
Split an arrêté (``ArreteFile``) into blocks (= list of ``Document``) and an image map.
Each block (= ``Document``) corresponds to a size-limited excerpt of the original HTML.
"""

import math
from typing import Iterator, Tuple

from bs4 import BeautifulSoup, Tag
from langchain_core.documents import Document

from ocapi.types import ArreteFile, ImageMap
from ocapi.utils.documents import ContentType, make_document_factory
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.utils import minify_html_fragment

_LOGGER = get_logger(__name__)

_ARRETIFY_SECTION_SELECTOR = '*[data-spec="section"]'


def split_blocks(
    minified_soup: BeautifulSoup, arrete_file: ArreteFile, target_per_block: int
) -> Iterator[Document]:
    """Split an Arrêtify soup into size-controlled blocks.

    Selects leaf-level sections (without sub-sections) and groups them
    into blocks whose total size does not exceed ``target_per_block`` characters.

    Parameters
    ----------
    minified_soup : BeautifulSoup
        Minified Arrêtify HTML soup (images already replaced by tokens).
    arrete_file : ArreteFile
        Source arrêté, used to annotate the produced documents.
    target_per_block : int
        Maximum target size of a block (in number of HTML characters).

    Yields
    ------
    Document
        HTML block annotated with the source arrêté identifier.
    """
    document_factory = make_document_factory(ContentType.HTML, parent=arrete_file.id)

    ignored_sections: list[Tag] = []
    selected_sections: list[Tag] = []

    for section in minified_soup.select(_ARRETIFY_SECTION_SELECTOR):
        if section in ignored_sections:
            continue
        if all(
            (_is_arretify_section(child) or _is_arretify_section_title(child))
            for child in section.contents
        ):
            continue

        child_sections = section.select(_ARRETIFY_SECTION_SELECTOR)
        selected_sections.append(section)
        if child_sections:
            ignored_sections.extend(child_sections)

    current_block: list[str] = []
    current_size = 0
    while selected_sections:
        current_block.append(str(selected_sections.pop(0)))
        current_size += len(current_block[-1])
        if current_size >= target_per_block:
            yield document_factory("".join(current_block), None)
            current_block = []
            current_size = 0
    if current_block:
        yield document_factory("".join(current_block), None)


def _extract_and_strip_images(html: str) -> Tuple[str, ImageMap]:
    """Replace <img> src attributes with IMG_n tokens and return (modified_html, img_map).

    img_map: { "IMG_n": original_src }
    """
    soup = BeautifulSoup(html, "html.parser")
    img_map: ImageMap = {}
    for i, img in enumerate(soup.find_all("img")):
        src = str(img.get("src") or img.get("data-src") or "")
        key = f"IMG_{i:03d}"
        if src:
            img_map[key] = src
        # Replace src with token (keeps the tag for the LLM but reduces payload size)
        img["src"] = key
    return str(soup), img_map


def step_chunking(arrete_file: ArreteFile) -> Tuple[list[Document], ImageMap]:
    """Split an HTML arrêté into blocks ready for LLM detection.

    Minifies the HTML, extracts images (replaced by tokens), then splits
    Arrêtify sections into blocks of at most ~70 000 characters.

    Parameters
    ----------
    arrete_file : ArreteFile
        Arrêté to split.

    Returns
    -------
    list[Document]
        HTML blocks ready to be sent to the LLM.
    ImageMap
        ``{token: original_url}`` mapping for rehydrating images.
    """
    minified = minify_html_fragment(str(arrete_file.soup))
    minified, img_map = _extract_and_strip_images(minified)
    soup_without_images = BeautifulSoup(minified, "html.parser")

    number_of_blocks = min(math.ceil(len(soup_without_images) / 70000), 5)
    target_per_block = math.ceil(len(soup_without_images) / number_of_blocks)

    blocks = list(
        split_blocks(
            soup_without_images,
            arrete_file=arrete_file,
            target_per_block=target_per_block,
        )
    )

    _LOGGER.info(f"Chunking: {len(blocks)} block(s) created, {len(img_map)} image(s)")
    return blocks, img_map


def _is_arretify_section(tag: object) -> bool:
    if not isinstance(tag, Tag):
        return False
    if tag.get("data-spec") == "section":
        return True
    return False


def _is_arretify_section_title(tag: object) -> bool:
    if not isinstance(tag, Tag):
        return False
    if tag.get("data-spec") == "section-title":
        return True
    return False
