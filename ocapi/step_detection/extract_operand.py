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
Ce fichier contient la logique pour extraire le contenu (operand) d'une opération
à partir d'un bloc HTML analysé, en utilisant des marqueurs de début et de fin.
"""

import html
import re

from bs4 import BeautifulSoup

ImageMap = dict[str, str]  # mapping from placeholder src to real src


def _find_marker(haystack: str, marker: str) -> int:
    """ """
    if not marker:
        return -1
    i = haystack.find(marker)
    if i != -1:
        return i
    n = html.unescape(marker)
    pattern = re.sub(r"\s+", r"\\s+", re.escape(n))
    m = re.search(pattern, haystack, flags=re.IGNORECASE | re.DOTALL)
    return m.start() if m else -1


def pick_arretify_section(html: str, source_article: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Cas 1 : "APPENDIX" : retourner tout le footer appendix
    if source_article == "APPENDIX":
        footer = soup.find("footer", attrs={"data-spec": "appendix"})
        if footer:
            return str(footer)
        raise ValueError("No appendix footer found")

    # Cas 2 : "APPENDIX:X" ou "APPENDIX:X.Y.Z" → chercher dans le footer appendix
    if source_article.startswith("APPENDIX:"):
        appendix_number = source_article.split("APPENDIX:", 1)[1]
        footer = soup.find("footer", attrs={"data-spec": "appendix"})
        if footer:
            for section in footer.find_all("section", attrs={"data-spec": "section"}):
                data_number = section.get("data-number")
                if data_number == appendix_number:
                    return str(section)
            raise ValueError(f"No section with data-number={appendix_number} found in appendix")

    # Cas 3 : Article normal (ex: "2.1.3")
    for section in soup.find_all("section", attrs={"data-spec": "section"}):
        data_number = section.get("data-number")
        if data_number == source_article:
            return str(section)
    print("Section not found for source_article:", source_article)
    return "ERROR_EXTRACTING_CONTENT"


def _rehydrate_images(fragment_html: str, img_map: dict[str, str]) -> str:
    if not img_map:
        return fragment_html
    soup = BeautifulSoup(fragment_html, "html.parser")
    for img in soup.find_all("img"):
        src_attr = img.get("src")
        src = str(src_attr) if src_attr is not None else None
        if src and src in img_map:
            img["src"] = img_map[src]
    return str(soup)


def extract_operand_with_images(
    block_html: str, source_article: str, start_marker: str, end_marker: str, img_map: ImageMap
) -> str:

    section = pick_arretify_section(block_html, source_article)
    working_html = section
    start_idx = _find_marker(working_html, start_marker)
    if start_idx == -1:
        working_html = block_html
        start_idx = _find_marker(working_html, start_marker)
        if start_idx == -1:
            return "ERROR_EXTRACTING_CONTENT"

    end_idx = _find_marker(working_html, end_marker)
    if end_idx != -1:
        fragment = working_html[start_idx : end_idx + len(end_marker)]
        fragment = _rehydrate_images(fragment, img_map)
        return fragment
    else:
        return "ERROR_EXTRACTING_CONTENT"
