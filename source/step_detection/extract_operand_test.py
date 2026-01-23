import unittest 

from ocapi.step_detection.extract_operand import extract_operand_with_images, pick_arretify_section
from ocapi.utils.utils import _assert_html_equal, minify_html_fragment


class TestPickArretifySection(unittest.TestCase):
    def test_pick_arretify_section(self):
        html = """
        <section data-spec="section" data-number="1.1">
            Ceci est le contenu de l'article 1.1.
        </section>
        <section data-spec="section" data-number="1.2">
            Ceci est le contenu de l'article 1.2.
        </section>
        """
        result = pick_arretify_section(
            html=minify_html_fragment(html),
            source_article="1.2"
        )
        expected = """
        <section data-spec="section" data-number="1.2">
            Ceci est le contenu de l'article 1.2.
        </section>
        """
        _assert_html_equal(result, minify_html_fragment(expected))

class TestExtractOperand(unittest.TestCase):
    def test_extract_operand_success(self):
        html = """
        <section data-spec="section" data-number="1.2">
            Voici le nouveau contenu operand de l'article. Inclut une image :
            <img src="image1.png" />
        </section>
        """
        minified_html = minify_html_fragment(html)
        
        start_marker = "Voici le nouveau "
        # Utiliser le HTML minifié pour le end_marker
        end_marker = '<img src="image1.png"/>'  # Sans espace avant />
        img_map = {"image1.png": "http://example.com/image1.png"}

        result = extract_operand_with_images(
            block_html=minified_html,
            source_article="1.2",
            start_marker=start_marker,
            end_marker=end_marker,
            img_map=img_map
        )

        assert "Voici le nouveau" in result
        assert "http://example.com/image1.png" in result
        _assert_html_equal (
            result,
            minify_html_fragment("""
                Voici le nouveau contenu operand de l'article. Inclut une image :
                <img src="http://example.com/image1.png"/>
            """)
        )

    def test_extract_operand_no_markers(self):
        html = """
        <section data-spec="section" data-number="L123-4">
            <p>This is the content of article L123-4.</p>
        </section>
        """
        start_marker = "<p>Non-existent start"
        end_marker = "</p>"

        with self.assertRaises(ValueError) as context:
            extract_operand_with_images(
                block_html=minify_html_fragment(html),
                source_article="L123-4",
                start_marker=start_marker,
                end_marker=end_marker,
                img_map={}
            )
        assert "Start marker not found" in str(context.exception)