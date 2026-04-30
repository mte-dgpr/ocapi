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
from typing import Tuple, cast

from arretify.semantic_tag_specs import AppendixSpec, SectionSpec
from bs4 import BeautifulSoup, Tag

from ocapi.types import ImageMap

ARRETIFY_SECTION_DATA_SPEC = SectionSpec.spec_name
ARRETIFY_APPENDIX_DATA_SPEC = AppendixSpec.spec_name
# AppendixSpec.tag_name is typed as a union including a builder callable in
# arretify, but appendix is a static tag name in practice.
ARRETIFY_APPENDIX_DATA_TAG = cast(str, AppendixSpec.tag_name)

ARRETIFY_SECTION_SELECTOR = f'*[data-spec="{ARRETIFY_SECTION_DATA_SPEC}"]'


def list_top_sections(soup: BeautifulSoup | Tag) -> list[Tag]:
    """Return top-level sections in the document (with no parent section)."""
    return [sec for sec in soup.find_all("section") if sec.find_parent("section") is None]


def extract_specs(soup: BeautifulSoup, spec: str) -> list[Tag]:
    """Extract all HTML elements matching an Arrêtify spec."""
    return [tag for tag in soup.find_all(attrs={"data-spec": spec}) if isinstance(tag, Tag)]


def extract_first_spec_html(soup: BeautifulSoup, spec: str) -> str:
    """Return the HTML of the first element matching the given Arrêtify spec.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed HTML document.
    spec : str
        Value of the ``data-spec`` attribute to look for (e.g. ``"visa"``, ``"motifs"``).

    Returns
    -------
    str
        Serialised HTML of the first matching element, or empty string if absent.
    """
    tags = extract_specs(soup, spec)
    if not tags:
        return ""
    return str(tags[0])


def extract_first_spec_text(soup: BeautifulSoup, spec: str) -> str:
    """Return the plain text of the first element matching the given Arrêtify spec.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed HTML document.
    spec : str
        Value of the ``data-spec`` attribute to look for.

    Returns
    -------
    str
        Extracted text with normalised whitespace, or empty string if absent.
    """
    tags = extract_specs(soup, spec)
    if not tags:
        return ""
    return str(tags[0].get_text(" ", strip=True))


def extract_and_strip_images(html: str) -> Tuple[str, ImageMap]:
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
        img["src"] = key
    return str(soup), img_map


def is_arretify_section(tag: object) -> bool:
    if not isinstance(tag, Tag):
        return False
    if tag.get("data-spec") == ARRETIFY_SECTION_DATA_SPEC:
        return True
    return False


def is_arretify_section_title(tag: object) -> bool:
    if not isinstance(tag, Tag):
        return False
    if tag.get("data-spec") == "section-title":
        return True
    return False


def rehydrate_images(html_fragment: str, img_map: ImageMap) -> str:
    """Replace image placeholder tokens with their original URLs."""
    if not img_map:
        return html_fragment
    soup = BeautifulSoup(html_fragment, "html.parser")
    for img in soup.find_all("img"):
        src_attr = img.get("src")
        src = str(src_attr) if src_attr is not None else None
        if src and src in img_map:
            img["src"] = img_map[src]
    return str(soup)


def extract_main(soup: BeautifulSoup) -> str:
    """Return the HTML of the ``<main>`` tag from the document.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed HTML document.

    Returns
    -------
    str
        Serialised HTML of the ``<main>`` tag, or empty string if absent.
    """
    main = soup.find("main")
    if main is None:
        return ""
    return str(main)


def extract_main_and_appendix(soup: BeautifulSoup) -> str:
    """Return the HTML of the ``<main>`` tag concatenated with the appendix ``<footer>``.

    The appendix footer (``<footer data-spec="appendix">``) is appended only
    when present.
    """
    main_html = extract_main(soup)
    footer = soup.find("footer", attrs={"data-spec": ARRETIFY_APPENDIX_DATA_SPEC})
    if footer is None:
        return main_html
    return main_html + str(footer)
