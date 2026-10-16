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
import pytest

from ocapi.utils.utils import find_marker_span


def _found(haystack: str, marker: str, start: int = 0, text_only: bool = True) -> str | None:
    span = find_marker_span(haystack, marker, start=start, text_only=text_only)
    return haystack[span[0] : span[1]] if span else None


def test_find_marker_span_verbatim() -> None:
    assert find_marker_span("<p>Un texte</p>", "texte") == (6, 11)


def test_find_marker_span_ignores_whitespace() -> None:
    haystack = "<p>Débit   de\n 10 m³/h</p>"
    assert _found(haystack, "Débit de 10 m³/h", text_only=False) == "Débit   de\n 10 m³/h"


def test_find_marker_span_unescapes_marker() -> None:
    assert _found("<p>Débit < 10 m³/h</p>", "Débit &lt; 10 m³/h", text_only=False) == (
        "Débit < 10 m³/h"
    )


@pytest.mark.parametrize("marker", ["", "<p></p>", "</div><div>"])
def test_find_marker_span_without_text_returns_none(marker: str) -> None:
    assert find_marker_span("<div><p>Texte</p></div>", marker) is None


def test_find_marker_span_not_found_returns_none() -> None:
    assert find_marker_span("<p>Texte</p>", "Introuvable") is None


def test_find_marker_span_text_only_ignores_missing_tags() -> None:
    haystack = '<div><a data-spec="section_reference"> Article 3 </a> Organisation </div>'
    assert _found(haystack, "Article 3 Organisation") == haystack


def test_find_marker_span_text_only_ignores_invented_tags() -> None:
    haystack = "<div> Fin du texte </div>"
    assert _found(haystack, '</table></div><div data-number="13"> Fin du texte </div>') == (
        haystack
    )


def test_find_marker_span_text_only_can_be_disabled() -> None:
    haystack = '<div><a data-spec="section_reference"> Article 3 </a> Organisation </div>'
    assert find_marker_span(haystack, "Article 3 Organisation", text_only=False) is None


@pytest.mark.parametrize(
    "haystack",
    [
        "<p> a &amp;gt;&amp;gt; b </p>",
        "<p> a &gt;&gt; b </p>",
    ],
)
def test_find_marker_span_text_only_matches_any_escaping_level(haystack: str) -> None:
    assert _found(haystack, "<b>a</b> &gt;&gt; b") == haystack


def test_find_marker_span_text_only_does_not_match_tag_delimiters() -> None:
    haystack = '<div data-number="1"> a </div><div data-number="2"> &amp;gt;&amp;gt; </div>'
    assert _found(haystack, "<b>&gt;&gt;</b>") == '<div data-number="2"> &amp;gt;&amp;gt; </div>'


def test_find_marker_span_text_only_skips_matches_inside_tags() -> None:
    haystack = '<a title="article 3"> Voir l\'article 3 </a>'
    span = find_marker_span(haystack, "<b>article</b> 3")
    assert span is not None
    assert haystack[span[0] : span[1]] == "article 3"
    assert span[0] > haystack.index(">")


def test_find_marker_span_text_only_matches_escaped_ampersand_and_lower_than() -> None:
    haystack = "<p> R &amp;amp; D &amp;lt; 5 </p>"
    assert _found(haystack, "<i>R</i> &amp; D &lt; 5") == haystack


def test_find_marker_span_text_only_respects_start() -> None:
    haystack = "<p>Article 2</p><p>Texte</p><p>Article 2</p>"
    span = find_marker_span(haystack, "<b>Article</b> 2", start=10)
    assert span is not None
    assert haystack[span[0] :] == "<p>Article 2</p>"


def test_find_marker_span_text_only_does_not_close_outer_elements() -> None:
    haystack = '<section><div data-number="1"> Texte </div></section>'
    assert _found(haystack, "<i>Texte</i>") == '<div data-number="1"> Texte </div>'


def test_find_marker_span_text_only_skips_void_tags_when_closing() -> None:
    haystack = "<section><p> A <br/> B </p></section>"
    assert _found(haystack, "<i>A</i> B") == "<p> A <br/> B </p>"


def test_find_marker_span_text_only_is_case_insensitive() -> None:
    assert _found("<p>ARTICLE 3</p>", "<b>article</b> 3") == "<p>ARTICLE 3</p>"


@pytest.mark.parametrize(
    "haystack",
    [
        "<p>de l’ <a> arrêté </a> du 10 décembre 2008 , est reportée</p>",
        "<p>de l’arrêté du 10 décembre 2008, est reportée</p>",
    ],
)
def test_find_marker_span_text_only_tolerates_spaces_around_punctuation(haystack: str) -> None:
    span = find_marker_span(haystack, "<b>de</b> l’arrêté du 10 décembre 2008, est reportée")
    assert span is not None
    assert haystack[span[0] : span[1]] == haystack


def test_find_marker_span_text_only_does_not_split_words() -> None:
    assert find_marker_span("<p>arrêté</p>", "<b>arr</b> êté") is None
