import unittest
from bs4 import BeautifulSoup

from ocapi.step_chunking.step_chunking import split_blocs
from ocapi.types import ArreteFile
from langchain_core.documents import Document   

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
        arrete_file = ArreteFile(
            id="arrete_1",
            aiot="aiot_1",
            filename="test.html",
            soup=BeautifulSoup(html_content, "html.parser")
        )
        blocs = list(split_blocs(arrete_file.soup, arrete_file, target_per_block=70000))
        assert len(blocs) == 1
        assert isinstance(blocs[0], Document)
        _assert_html_equal(blocs[0].page_content, """
        <section data-spec="section">Content of article 1.</section>
        <section data-spec="section">Content of article 2.</section>
        <section data-spec="section">Subsection content.</section>
        <section data-spec="section">Another subsection.</section>
        <section data-spec="section">Content of article 4.</section>
        """)

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
        arrete_file = ArreteFile(
            id="arrete_2",
            aiot="aiot_2",
            filename="test.html",
            soup=BeautifulSoup(html_content, "html.parser")
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
        arrete_file = ArreteFile(
            id="arrete_3",
            aiot="aiot_3",
            filename="test.html",
            soup=BeautifulSoup(html_content, "html.parser")
        )
        blocs = list(split_blocs(arrete_file.soup, arrete_file, target_per_block=10))
        assert len(blocs) == 2

        assert blocs[0].page_content == (
        """<section data-spec="section">
            Content part 1.
            <section data-spec="section">Nested section 1</section>
            <section data-spec="section">Nested section 2</section>
        </section>"""
        )
        assert blocs[1].page_content == (
        """<section data-spec="section"><h2>Article 2</h2>Content part 2.</section>"""
        )
     

def _assert_html_equal(html1: str, html2: str):
    soup1 = BeautifulSoup(html1, 'html.parser')
    soup2 = BeautifulSoup(html2, 'html.parser')
    assert soup1.prettify() == soup2.prettify()