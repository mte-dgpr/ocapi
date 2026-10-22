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
import re
from typing import Tuple, cast

from arretify.parsing_utils.numbering import are_levels_contiguous, str_to_levels
from arretify.semantic_tag_specs import (
    AlineaSpec,
    AppendixSpec,
    PageFooterSpec,
    PageHeaderSpec,
    PageSeparatorSpec,
    SectionReferenceSpec,
    SectionSpec,
    SectionTitleSpec,
)
from arretify.types import SectionType
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, PageElement

from ocapi.types import ImageMap

ARRETIFY_SECTION_DATA_SPEC = SectionSpec.spec_name
ARRETIFY_APPENDIX_DATA_SPEC = AppendixSpec.spec_name
ARRETIFY_PAGE_SEPARATOR_DATA_SPEC = PageSeparatorSpec.spec_name
ARRETIFY_ALINEA_DATA_SPEC = AlineaSpec.spec_name
ARRETIFY_SECTION_REFERENCE_DATA_SPEC = SectionReferenceSpec.spec_name
ARRETIFY_SECTION_TITLE_DATA_SPEC = SectionTitleSpec.spec_name
_PAGINATION_DATA_SPECS = {PageFooterSpec.spec_name, PageHeaderSpec.spec_name}
# Blockquote children that become an alinea on their own.
_BLOCK_TAG_NAMES = {"p", "table", "ul"}
# AppendixSpec.tag_name is typed as a union including a builder callable in
# arretify, but appendix is a static tag name in practice.
ARRETIFY_APPENDIX_DATA_TAG = cast(str, AppendixSpec.tag_name)

ARRETIFY_SECTION_SELECTOR = f'*[data-spec="{ARRETIFY_SECTION_DATA_SPEC}"]'

# Empty ``<a ... data-spec="page_separator"></a>``, whatever its attribute order.
_PAGE_SEPARATOR_RE = re.compile(
    rf"<a\b[^>]*\bdata-spec=([\"']){ARRETIFY_PAGE_SEPARATOR_DATA_SPEC}\1[^>]*>\s*</a>"
)

# Opening ``<blockquote ...>`` or closing ``</blockquote>`` tag, whatever its attributes.
_BLOCKQUOTE_TAG_RE = re.compile(r"</?blockquote\b[^>]*>", re.IGNORECASE)

# Punctuation between an article number and its title ("Article 3 : Titre").
_TITLE_SEPARATOR_RE = re.compile(r"^[\s.:\-–—]+")


def list_top_sections(soup: BeautifulSoup | Tag) -> list[Tag]:
    """Return top-level sections in the document (with no parent section)."""
    return [sec for sec in soup.find_all("section") if sec.find_parent("section") is None]


def extract_specs(soup: BeautifulSoup, spec: str) -> list[Tag]:
    """Extract all HTML elements matching an Arrêtify spec."""
    return [tag for tag in soup.select(f'[data-spec="{spec}"]') if isinstance(tag, Tag)]


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


def strip_page_separators(html: str) -> str:
    """Remove Arrêtify page separators from an HTML fragment."""
    return _PAGE_SEPARATOR_RE.sub("", html)


def strip_blockquotes(html: str) -> str:
    """Remove ``<blockquote>`` opening and closing tags, keeping their contents."""
    return _BLOCKQUOTE_TAG_RE.sub("", html)


def blockquotes_to_alineas(soup: BeautifulSoup) -> None:
    """Unwrap blockquotes, turning their paragraphs into numbered alineas."""
    # Deepest blockquotes first, so that nested ones are unwrapped in place.
    for blockquote in reversed(soup.find_all("blockquote")):
        alinea = blockquote.parent
        if not (isinstance(alinea, Tag) and _is_alinea(alinea)):
            blockquote.unwrap()
            continue
        alineas = _split_alinea_on_blockquote(soup, alinea, blockquote)
        _split_sections_on_titles(soup, alineas)


def _is_alinea(element: PageElement) -> bool:
    return isinstance(element, Tag) and element.get("data-spec") == ARRETIFY_ALINEA_DATA_SPEC


def _split_alinea_on_blockquote(soup: BeautifulSoup, alinea: Tag, blockquote: Tag) -> list[Tag]:
    """Replace ``alinea`` by one alinea per block of ``blockquote`` and return them."""
    groups: list[list[PageElement]] = [list(blockquote.previous_siblings)[::-1]]
    for child in list(blockquote.contents):
        if isinstance(child, Tag) and child.name in _BLOCK_TAG_NAMES:
            groups.append(list(child.contents) if child.name == "p" else [child])
            groups.append([])
        elif isinstance(child, Tag) and child.name == "br":
            groups.append([])
        elif isinstance(child, Tag) and child.get("data-spec") in _PAGINATION_DATA_SPECS:
            # Page headers/footers do not start an alinea of their own.
            next((g for g in reversed(groups) if _has_content(g)), groups[-1]).append(child)
        else:
            groups[-1].append(child)
    groups.append(list(blockquote.next_siblings))
    groups = [group for group in groups if _has_content(group)]
    if not groups:
        blockquote.unwrap()
        return [alinea]

    number = int(str(alinea.get("data-number", "1")))
    added = len(groups) - 1
    if added > 0:
        for sibling in alinea.next_siblings:
            if isinstance(sibling, Tag) and _is_alinea(sibling):
                sibling["data-number"] = str(int(str(sibling["data-number"])) + added)

    alinea.clear()
    for group in groups[:1]:
        alinea.extend([element.extract() for element in group])
    alineas = [alinea]
    for index, group in enumerate(groups[1:], start=1):
        new_alinea = soup.new_tag(
            "div",
            attrs={"data-number": str(number + index), "data-spec": ARRETIFY_ALINEA_DATA_SPEC},
        )
        new_alinea.extend([element.extract() for element in group])
        alineas[-1].insert_after(new_alinea)
        alineas.append(new_alinea)
    return alineas


def _split_sections_on_titles(soup: BeautifulSoup, alineas: list[Tag]) -> None:
    """Start a new section at each alinea titled by the next article of its section.

    Only sections at the same level as the current one are created: the title
    alinea becomes the section title, and every following element of the
    current section moves into the new section.
    """
    for alinea in alineas:
        section = alinea.parent
        if not (
            isinstance(section, Tag) and section.get("data-spec") == ARRETIFY_SECTION_DATA_SPEC
        ):
            continue
        reference = _leading_article_reference(alinea)
        if reference is None:
            continue
        section_levels = str_to_levels(str(section.get("data-number", "")))
        title_levels = str_to_levels(str(reference["data-start_num"]))
        if (
            section_levels is None
            or title_levels is None
            or len(title_levels) != len(section_levels)
            or not are_levels_contiguous(section_levels, title_levels)
        ):
            continue

        new_section = _make_section(soup, section, alinea, reference)
        for element in list(alinea.next_siblings):
            new_section.append(element.extract())
        alinea.decompose()
        section.insert_after(new_section)
        for number, child in enumerate(new_section.find_all(_is_alinea, recursive=False), 1):
            child["data-number"] = str(number)


def _leading_article_reference(alinea: Tag) -> Tag | None:
    """Return the article reference opening ``alinea``, if any."""
    first = next((child for child in alinea.contents if _has_content([child])), None)
    if (
        isinstance(first, Tag)
        and first.get("data-spec") == ARRETIFY_SECTION_REFERENCE_DATA_SPEC
        and first.get("data-type") == SectionType.ARTICLE.value
        and first.get("data-start_num")
    ):
        return first
    return None


def _make_section(soup: BeautifulSoup, section: Tag, alinea: Tag, reference: Tag) -> Tag:
    """Build an empty section like ``section``, titled by the text of ``alinea``."""
    title_text = " ".join(alinea.get_text(" ").split())
    after_reference = " ".join(
        element.get_text(" ") if isinstance(element, Tag) else str(element)
        for element in reference.next_siblings
    )
    title = _TITLE_SEPARATOR_RE.sub("", " ".join(after_reference.split()))

    attrs = {
        "data-number": str(reference["data-start_num"]),
        "data-spec": ARRETIFY_SECTION_DATA_SPEC,
    }
    if title:
        attrs["data-title"] = title
    attrs["data-type"] = str(section.get("data-type", SectionType.ARTICLE.value))
    new_section = soup.new_tag("section", attrs=attrs)

    current_title = section.select_one(f'[data-spec="{ARRETIFY_SECTION_TITLE_DATA_SPEC}"]')
    title_tag = soup.new_tag(
        current_title.name if isinstance(current_title, Tag) else "h2",
        attrs={
            "data-level": (
                str(current_title.get("data-level", "0")) if isinstance(current_title, Tag) else "0"
            ),
            "data-spec": ARRETIFY_SECTION_TITLE_DATA_SPEC,
        },
    )
    title_tag.string = title_text
    new_section.append(title_tag)
    return new_section


def _has_content(group: list[PageElement]) -> bool:
    return any(
        not (isinstance(element, NavigableString) and not element.strip()) for element in group
    )


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
    footer = soup.select_one(f'footer[data-spec="{ARRETIFY_APPENDIX_DATA_SPEC}"]')
    if footer is None:
        return main_html
    return main_html + str(footer)
