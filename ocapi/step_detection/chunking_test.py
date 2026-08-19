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
from langchain_core.documents import Document

from ocapi.step_detection.chunking import chunk_arrete, split_blocks
from ocapi.types import ArreteFile, FileType
from ocapi.utils.testing import assert_html_equal
from ocapi.utils.utils import minify_html_fragment


def test_split_in_single_bloc() -> None:
    """Verify that sections whose total size < target are grouped into a single block."""
    html_content = """
    <section data-spec="section">Content of article 1.</section>
    <section data-spec="section">Content of article 2.</section>
    <section data-spec="section">
        <h2 data-spec="section-title">Article 3</h2>
        <section data-spec="section">Subsection content.</section>
        <section data-spec="section">Another subsection.</section>
    </section>
    <section data-spec="section">Content of article 4.</section>
    """
    minified_html = minify_html_fragment(html_content)
    arrete_file = ArreteFile(
        id="arrete_1",
        aiot="aiot_1",
        filename="test.html",
        soup=BeautifulSoup(minified_html, "html.parser"),
        file_type=FileType.AUTRE,
    )
    blocs = list(split_blocks(arrete_file.soup, arrete_file, target_per_block=70000))
    assert len(blocs) == 1
    assert isinstance(blocs[0], Document)
    assert_html_equal(
        blocs[0].page_content,
        """
    <section data-spec="section">Content of article 1.</section>
    <section data-spec="section">Content of article 2.</section>
    <section data-spec="section">Subsection content.</section>
    <section data-spec="section">Another subsection.</section>
    <section data-spec="section">Content of article 4.</section>
    """,
    )


def test_split_in_multiple_blocs() -> None:
    """Verify that sections exceeding target_per_block are distributed across multiple blocks."""
    html_content = """
    <section data-spec="section">Content of article 1 with more text.</section>
    <section data-spec="section">Content of article 2 with more text.</section>
    <section data-spec="section">
        <h2 data-spec="section-title">Article 3</h2>
        <section data-spec="section">Subsection content with details.</section>
        <section data-spec="section">Another subsection with content.</section>
    </section>
    <section data-spec="section">Content of article 4 with more text.</section>
    <section data-spec="section">Content of article 5 with more text.</section>
    """
    minified_html = minify_html_fragment(html_content)
    arrete_file = ArreteFile(
        id="arrete_2",
        aiot="aiot_2",
        filename="test.html",
        soup=BeautifulSoup(minified_html, "html.parser"),
        file_type=FileType.AUTRE,
    )
    blocs = list(split_blocks(arrete_file.soup, arrete_file, target_per_block=125))
    assert len(blocs) == 3
    assert blocs[0].page_content == (
        '<section data-spec="section">Content of article 1 with more text.</section>'
        '<section data-spec="section">Content of article 2 with more text.</section>'
    )
    assert blocs[1].page_content == (
        '<section data-spec="section">Subsection content with details.</section>'
        '<section data-spec="section">Another subsection with content.</section>'
    )
    assert blocs[2].page_content == (
        '<section data-spec="section">Content of article 4 with more text.</section>'
        '<section data-spec="section">Content of article 5 with more text.</section>'
    )


def test_chunk_arrete_does_not_split_one_section_per_block() -> None:
    """Regression test: chunk_arrete must size blocks by character count, not by the
    BeautifulSoup object's child count (``len(a_soup)`` returns the number of direct
    children, not the number of characters).

    Before the fix, a document with many small sections but a modest total size (well
    under the 70 000-character target) was split into one block per section — e.g. for
    AIOT 0005800425 (AP du 2012-09-03, RECTICEL) this isolated the "chapeau" sentence
    naming the target arrêté (article 2) from the named articles that follow (articles
    3-13), so the LLM could no longer associate those articles with their target arrêté
    and silently dropped them instead of producing targeted operations.
    """
    html_content = "".join(
        f'<section data-spec="section" data-number="{i}">Article {i} content.</section>'
        for i in range(1, 20)
    )
    minified_html = minify_html_fragment(html_content)
    arrete_file = ArreteFile(
        id="arrete_4",
        aiot="aiot_4",
        filename="test.html",
        soup=BeautifulSoup(minified_html, "html.parser"),
        file_type=FileType.AUTRE,
    )

    blocks, _ = chunk_arrete(arrete_file)

    assert len(blocks) == 1
    for i in range(1, 20):
        assert f"Article {i} content." in blocks[0].page_content


def test_split_section_with_mixed_content() -> None:
    html_content = """
    <section data-spec="section">
        Content part 1.
        <section data-spec="section">Nested section 1</section>
        <section data-spec="section">Nested section 2</section>
    </section>
    <section data-spec="section"><h2>Article 2</h2>Content part 2.</section>
    """
    minified_html = minify_html_fragment(html_content)
    arrete_file = ArreteFile(
        id="arrete_3",
        aiot="aiot_3",
        filename="test.html",
        soup=BeautifulSoup(minified_html, "html.parser"),
        file_type=FileType.AUTRE,
    )
    blocs = list(split_blocks(arrete_file.soup, arrete_file, target_per_block=10))
    assert len(blocs) == 2
    assert_html_equal(
        blocs[0].page_content,
        """<section data-spec="section"> Content part 1.
        <section data-spec="section">Nested section 1</section>
        <section data-spec="section">Nested section 2</section>""",
    )
    assert_html_equal(
        blocs[1].page_content,
        """<section data-spec="section"><h2>Article 2</h2>Content part 2.</section>""",
    )
