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


def find_marker(haystack: str, marker: str) -> int:
    """Return the start index of marker in haystack, or -1 if not found."""
    if not marker:
        return -1
    i = haystack.find(marker)
    if i != -1:
        return i
    n = html.unescape(marker)
    pattern = re.sub(r"\s+", r"\\s+", re.escape(n))
    m = re.search(pattern, haystack, flags=re.IGNORECASE | re.DOTALL)
    return m.start() if m else -1


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
