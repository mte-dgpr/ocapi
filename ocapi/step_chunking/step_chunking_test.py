import unittest
from bs4 import BeautifulSoup

from ocapi.step_chunking.step_chunking import split_blocs, _extract_and_strip_images
from ocapi.types import ArreteFile
from langchain_core.documents import Document

from ocapi.utils.utils import _assert_html_equal, minify_html_fragment


class TestSplitBlocs(unittest.TestCase):

    def test_split_in_single_bloc(self):
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
        )
        blocs = list(split_blocs(arrete_file.soup, arrete_file, target_per_block=70000))
        assert len(blocs) == 1
        assert isinstance(blocs[0], Document)
        _assert_html_equal(
            blocs[0].page_content,
            """
        <section data-spec="section">Content of article 1.</section>
        <section data-spec="section">Content of article 2.</section>
        <section data-spec="section">Subsection content.</section>
        <section data-spec="section">Another subsection.</section>
        <section data-spec="section">Content of article 4.</section>
        """,
        )

    def test_split_in_multiple_blocs(self):
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
        )

        blocs = list(split_blocs(arrete_file.soup, arrete_file, target_per_block=125))
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

    def test_split_section_with_mixed_content(self):
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
        )
        blocs = list(split_blocs(arrete_file.soup, arrete_file, target_per_block=10))
        assert len(blocs) == 2
        _assert_html_equal(
            blocs[0].page_content,
            """<section data-spec="section"> Content part 1.
            <section data-spec="section">Nested section 1</section>
            <section data-spec="section">Nested section 2</section>""",
        )
        _assert_html_equal(
            blocs[1].page_content,
            """<section data-spec="section"><h2>Article 2</h2>Content part 2.</section>""",
        )


class TestExtractAndStripImages(unittest.TestCase):
    def test_extract_and_strip_images(self):

        html_content = """
        <p>Here is an image: <img src="http://example.com/image1.png" alt="Image 1"></p>
        <p>Another image: <img src="http://example.com/image2.jpg" alt="Image 2"></p>
        """
        modified_html, img_map = _extract_and_strip_images(minify_html_fragment(html_content))

        expected_modified_html = """
        <p>Here is an image: <img src="IMG_000" alt="Image 1"></p>
        <p>Another image: <img src="IMG_001" alt="Image 2"></p>
        """
        expected_img_map = {
            "IMG_000": "http://example.com/image1.png",
            "IMG_001": "http://example.com/image2.jpg",
        }

        _assert_html_equal(modified_html, minify_html_fragment(expected_modified_html))
        assert img_map == expected_img_map
