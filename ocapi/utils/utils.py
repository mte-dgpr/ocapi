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
import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from ocapi.types import Content


def to_int_or_default(value: Any, default: int, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def to_bool_or_default(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


@dataclass
class IdCounter:
    value: int = 0


def make_id(counter: IdCounter) -> str:
    counter.value += 1
    return str(counter.value)


def strip_accents(text: str) -> str:
    """Remove diacritical marks (é→e, à→a, …)."""
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")


def normalize_section_title(text: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(text)).strip().lower()


def minify_html_fragment(html: str) -> str:
    """Light minification and Unicode normalisation for an HTML fragment.

    - removes <script>/<style> tags
    - normalises Unicode
    - strips whitespace between tags and collapses whitespace runs
    """
    s = str(html or "")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"(?is)<script.*?>.*?</script>", "", s)
    s = re.sub(r"(?is)<style.*?>.*?</style>", "", s)
    s = re.sub(r">\s+<", "><", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def html_checksum(soup: BeautifulSoup) -> str:
    """Return an MD5 hex digest of the serialised HTML."""
    return hashlib.md5(str(soup).encode("utf-8")).hexdigest()


_HTML_TAG_PATTERN_S = r"<[^>]*>"
_TEXT_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]")
# Whitespace and tags between two tokens of a marker word (optional) and
# between two words of a marker (required).
_TEXT_TOKEN_GAP_PATTERN_S = rf"(?:\s|{_HTML_TAG_PATTERN_S})*"
_TEXT_WORD_GAP_PATTERN_S = rf"(?:\s|{_HTML_TAG_PATTERN_S})+"
# Characters escaped in HTML text, matched whatever their escaping level (OCR
# output is sometimes escaped twice, e.g. ``&amp;gt;``). A bare ``<`` or ``>``
# in the haystack is a tag delimiter, never text.
_ESCAPABLE_CHAR_PATTERNS = {
    "&": r"&(?:amp;)*",
    "<": r"&(?:amp;)*lt;",
    ">": r"&(?:amp;)*gt;",
}
# Opening tags right before a text-only match, excluding the document structure
# (a marker starting at the first words of a section does not include the section).
_LEADING_OPENING_TAGS_PATTERN = re.compile(
    r"(?:<(?!/|!|(?:section|main|header|footer|body|html)\b)[^>]*>\s*)+$", re.IGNORECASE
)
_CLOSING_TAG_PATTERN = re.compile(r"\s*</([a-zA-Z0-9]+)\s*>")
_ANY_TAG_PATTERN = re.compile(r"<(/?)([a-zA-Z0-9]+)\b[^>]*?(/?)>")
_VOID_TAG_NAMES = {"br", "img", "hr", "input", "meta", "link", "col", "wbr"}


def find_marker_span(
    haystack: str, marker: str, start: int = 0, text_only: bool = True
) -> tuple[int, int] | None:
    """Return the ``(start, end)`` span of marker in haystack at or after `start`.

    Markers come from the LLM and are not always exact copies of the HTML.
    They are looked up, in this order:

    1. verbatim;
    2. ignoring whitespace differences and HTML escaping;
    3. if ``text_only`` is set, on their text only, ignoring the tags of both
       the marker and the haystack (the LLM often drops or invents tags such
       as references or alinea wrappers). The span is then widened to the
       opening tags right before the text and to the closing tags of the
       elements opened within it, so that it does not cut an element in half.

    Returns ``None`` when the marker is not found.
    """
    if not marker:
        return None
    i = haystack.find(marker, start)
    if i != -1:
        return i, i + len(marker)
    pattern = r"\s+".join(re.escape(word) for word in html.unescape(marker).split())
    m = re.compile(pattern, flags=re.IGNORECASE | re.DOTALL).search(haystack, start)
    if m:
        return m.span()
    if not text_only:
        return None
    return _find_marker_text_span(haystack, marker, start)


def _find_marker_text_span(haystack: str, marker: str, start: int) -> tuple[int, int] | None:
    words = html.unescape(re.sub(_HTML_TAG_PATTERN_S, " ", marker)).split()
    if not words:
        return None
    # Punctuation is a token of its own: Arrêtify puts spaces around its tags,
    # so "l'arrêté" or "2008," in the marker may read "l' arrêté" or "2008 ,".
    pattern = re.compile(
        _TEXT_WORD_GAP_PATTERN_S.join(
            _TEXT_TOKEN_GAP_PATTERN_S.join(
                "".join(_ESCAPABLE_CHAR_PATTERNS.get(char, re.escape(char)) for char in token)
                for token in _TEXT_TOKEN_PATTERN.findall(word)
            )
            for word in words
        ),
        flags=re.IGNORECASE,
    )
    m = pattern.search(haystack, start)
    # Skip matches starting inside a tag (e.g. a word found in an attribute value).
    while m and haystack.rfind("<", 0, m.start()) > haystack.rfind(">", 0, m.start()):
        m = pattern.search(haystack, m.start() + 1)
    if not m:
        return None
    span_start, span_end = m.span()
    leading = _LEADING_OPENING_TAGS_PATTERN.search(haystack, start, span_start)
    if leading:
        span_start = leading.start()
    # Only close the elements opened within the span.
    open_tags = _unclosed_tag_names(haystack[span_start:span_end])
    while open_tags:
        closing = _CLOSING_TAG_PATTERN.match(haystack, span_end)
        if not closing or closing.group(1).lower() != open_tags[-1]:
            break
        open_tags.pop()
        span_end = closing.end()
    return span_start, span_end


def _unclosed_tag_names(fragment: str) -> list[str]:
    """Return the names of the elements opened but not closed in ``fragment``."""
    stack: list[str] = []
    for m in _ANY_TAG_PATTERN.finditer(fragment):
        is_closing, name, is_self_closing = m.group(1), m.group(2).lower(), m.group(3)
        if is_self_closing or name in _VOID_TAG_NAMES:
            continue
        if not is_closing:
            stack.append(name)
        elif name in stack:
            del stack[len(stack) - 1 - stack[::-1].index(name) :]
    return stack


def ensure_soup(soup_input: Content | BeautifulSoup) -> BeautifulSoup:
    return (
        soup_input
        if isinstance(soup_input, BeautifulSoup)
        else BeautifulSoup(soup_input, "html.parser")
    )


def normalize_title_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def strip_none_values(obj: Any) -> Any:
    """Recursively drop ``None`` values so snapshot JSON matches across Pydantic versions."""
    if isinstance(obj, dict):
        return {k: strip_none_values(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [strip_none_values(x) for x in obj]
    return obj
