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
from bs4 import BeautifulSoup

from ocapi.utils.arretify_utils import (
    blockquotes_to_alineas,
    extract_and_strip_images,
    extract_specs,
    strip_blockquotes,
    strip_page_separators,
)
from ocapi.utils.testing import assert_html_equal
from ocapi.utils.utils import minify_html_fragment


def test_extract_specs_returns_only_requested_data_spec() -> None:
    soup = BeautifulSoup(
        """
<html><body>
 <div data-spec="visa">visa 1</div>
 <div data-spec="motifs">motif 1</div>
 <p data-spec="visa">visa 2</p>
</body></html>
""",
        "html.parser",
    )

    visa_tags = extract_specs(soup, "visa")

    assert len(visa_tags) == 2
    assert [tag.get_text(strip=True) for tag in visa_tags] == ["visa 1", "visa 2"]


def test_extract_specs_returns_empty_list_when_missing_spec() -> None:
    soup = BeautifulSoup("<html><body><div>sans spec</div></body></html>", "html.parser")

    assert extract_specs(soup, "visa") == []


def test_extract_and_strip_images() -> None:
    """Verify that image src attributes are replaced by tokens and that the map is correct."""
    html_content = """
    <p>Here is an image: <img src="http://example.com/image1.png" alt="Image 1"></p>
    <p>Another image: <img src="http://example.com/image2.jpg" alt="Image 2"></p>
    """
    modified_html, img_map = extract_and_strip_images(minify_html_fragment(html_content))

    expected_modified_html = """
    <p>Here is an image: <img src="IMG_000" alt="Image 1"></p>
    <p>Another image: <img src="IMG_001" alt="Image 2"></p>
    """
    expected_img_map = {
        "IMG_000": "http://example.com/image1.png",
        "IMG_001": "http://example.com/image2.jpg",
    }

    assert_html_equal(modified_html, minify_html_fragment(expected_modified_html))
    assert img_map == expected_img_map


def test_strip_page_separators_removes_every_separator() -> None:
    html = (
        '<div data-spec="alinea">Début <a data-page_index="3" data-spec="page_separator"></a>'
        'suite</div><a data-page_index="4" data-spec="page_separator"></a><p>fin</p>'
    )

    actual = strip_page_separators(html)

    assert "page_separator" not in actual
    assert_html_equal(actual, '<div data-spec="alinea">Début suite</div><p>fin</p>')


def test_strip_page_separators_keeps_page_headers_and_footers() -> None:
    html = '<div data-spec="page_footer"><div>4/11</div></div><p>texte</p>'

    assert strip_page_separators(html) == html


def test_strip_page_separators_returns_input_unchanged_without_separator() -> None:
    html = "<p>a &amp; b<br>c</p>"

    assert strip_page_separators(html) == html


def test_strip_page_separators_leaves_surrounding_html_byte_identical() -> None:
    # No re-serialisation: attribute order and formatting of other tags are kept.
    html = (
        '<li data-spec="permit_source" data-date="2020-04-20">\n'
        '   <a data-page_index="3" data-spec="page_separator">\n   </a>\n'
        "   AP du 20 avril 2020<br>\n</li>"
    )

    actual = strip_page_separators(html)

    assert actual == (
        '<li data-spec="permit_source" data-date="2020-04-20">\n'
        "   \n"
        "   AP du 20 avril 2020<br>\n</li>"
    )


def test_strip_blockquotes_keeps_contents() -> None:
    html = (
        '<div data-spec="alinea"><blockquote data-tag_id="16"><p>Article 1.2.1</p>'
        "<table><tr><td>A</td></tr></table></blockquote></div>"
    )

    actual = strip_blockquotes(html)

    assert actual == (
        '<div data-spec="alinea"><p>Article 1.2.1</p>' "<table><tr><td>A</td></tr></table></div>"
    )


def test_strip_blockquotes_removes_unclosed_blockquote() -> None:
    html = (
        '<div data-spec="alinea"><blockquote>Article 2 cité</div>'
        '<section data-number="3"><p>Article 3</p></section>'
    )

    actual = strip_blockquotes(html)

    assert actual == (
        '<div data-spec="alinea">Article 2 cité</div>'
        '<section data-number="3"><p>Article 3</p></section>'
    )


def test_strip_blockquotes_removes_orphan_closing_tag() -> None:
    assert strip_blockquotes("<p>texte</p>\n</blockquote>\n<p>suite</p>") == (
        "<p>texte</p>\n\n<p>suite</p>"
    )


def test_strip_blockquotes_keeps_inline_quotes() -> None:
    html = "<p>les mots <q>eaux</q> sont remplacés</p>"

    assert strip_blockquotes(html) == html


def _alineas(soup: BeautifulSoup) -> list[tuple[str, str]]:
    return [
        (str(alinea["data-number"]), alinea.decode_contents())
        for alinea in soup.select('[data-spec="alinea"]')
    ]


def test_blockquotes_to_alineas_numbers_paragraphs_after_previous_alineas() -> None:
    soup = BeautifulSoup(
        '<section data-spec="section">'
        '<div data-number="1" data-spec="alinea">L\'article 1 est remplacé :</div>'
        '<div data-number="2" data-spec="alinea"><blockquote data-tag_id="16">'
        "<p>Article 1</p><p>Premier alinéa.</p>"
        "<table><tr><td><p>Cellule</p></td></tr></table>"
        "<p>Dernier alinéa.</p>"
        "</blockquote></div>"
        '<div data-number="3" data-spec="alinea">Après la citation.</div>'
        "</section>",
        "html.parser",
    )

    blockquotes_to_alineas(soup)

    assert soup.select("blockquote") == []
    assert _alineas(soup) == [
        ("1", "L'article 1 est remplacé :"),
        ("2", "Article 1"),
        ("3", "Premier alinéa."),
        ("4", "<table><tr><td><p>Cellule</p></td></tr></table>"),
        ("5", "Dernier alinéa."),
        ("6", "Après la citation."),
    ]


def test_blockquotes_to_alineas_keeps_surrounding_alinea_text() -> None:
    soup = BeautifulSoup(
        '<div data-number="1" data-spec="alinea">Avant :'
        "<blockquote><p>Cité</p></blockquote>après.</div>",
        "html.parser",
    )

    blockquotes_to_alineas(soup)

    assert _alineas(soup) == [("1", "Avant :"), ("2", "Cité"), ("3", "après.")]


def test_blockquotes_to_alineas_splits_inline_content_on_line_breaks() -> None:
    soup = BeautifulSoup(
        '<div data-number="1" data-spec="alinea"><blockquote>Ligne <b>un</b><br/>'
        'Ligne deux<div data-spec="page_footer"><div>2/5</div></div>'
        "</blockquote></div>",
        "html.parser",
    )

    blockquotes_to_alineas(soup)

    assert _alineas(soup) == [
        ("1", "Ligne <b>un</b>"),
        ("2", 'Ligne deux<div data-spec="page_footer"><div>2/5</div></div>'),
    ]


def test_blockquotes_to_alineas_unwraps_blockquote_outside_alinea() -> None:
    soup = BeautifulSoup(
        '<div data-number="1" data-spec="alinea"><table><tr><td>'
        "<blockquote>Cellule</blockquote></td></tr></table></div>",
        "html.parser",
    )

    blockquotes_to_alineas(soup)

    assert _alineas(soup) == [("1", "<table><tr><td>Cellule</td></tr></table>")]


def _article_ref(number: str) -> str:
    return (
        f'<a data-spec="section_reference" data-start_num="{number}" data-type="article">'
        f"Article {number}</a>"
    )


def test_blockquotes_to_alineas_restores_swallowed_articles() -> None:
    soup = BeautifulSoup(
        "<main>"
        '<section data-number="2" data-spec="section" data-title="Liste" data-type="article">'
        '<h2 data-level="0" data-spec="section_title">Article 2 : Liste</h2>'
        '<div data-number="1" data-spec="alinea">L\'article 1.2.1 est remplacé :</div>'
        '<div data-number="2" data-spec="alinea"><blockquote>'
        f"<p>{_article_ref('1.2.1')} Liste des installations</p>"
        "<p>Texte cité.</p>"
        f"<p>{_article_ref('3')} : Organisation</p>"
        "<p>Premier alinéa de l'article 3.</p>"
        "<p>Second alinéa de l'article 3.</p>"
        "</blockquote></div>"
        "</section>"
        '<section data-number="4" data-spec="section" data-type="article"></section>'
        "</main>",
        "html.parser",
    )

    blockquotes_to_alineas(soup)

    sections = soup.select('section[data-spec="section"]')
    assert [section["data-number"] for section in sections] == ["2", "3", "4"]
    article_2, article_3 = sections[0], sections[1]
    assert [a.get_text() for a in article_2.select('[data-spec="alinea"]')] == [
        "L'article 1.2.1 est remplacé :",
        "Article 1.2.1 Liste des installations",
        "Texte cité.",
    ]
    assert article_3.attrs == {
        "data-number": "3",
        "data-spec": "section",
        "data-title": "Organisation",
        "data-type": "article",
    }
    assert str(article_3.h2) == (
        '<h2 data-level="0" data-spec="section_title">Article 3 : Organisation</h2>'
    )
    assert _alineas(BeautifulSoup(str(article_3), "html.parser")) == [
        ("1", "Premier alinéa de l'article 3."),
        ("2", "Second alinéa de l'article 3."),
    ]


def test_blockquotes_to_alineas_keeps_non_contiguous_article_titles_as_alineas() -> None:
    soup = BeautifulSoup(
        '<section data-number="7" data-spec="section" data-type="article">'
        '<div data-number="1" data-spec="alinea"><blockquote>'
        f"<p>{_article_ref('2.1.4')} Horaires</p><p>{_article_ref('9')} Plus loin</p>"
        "</blockquote></div></section>",
        "html.parser",
    )

    blockquotes_to_alineas(soup)

    assert [s["data-number"] for s in soup.select('section[data-spec="section"]')] == ["7"]
    assert [number for number, _ in _alineas(soup)] == ["1", "2"]
