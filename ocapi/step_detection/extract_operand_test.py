import unittest 

from ocapi.step_detection.extract_operand import extract_operand


class TestExtractOperand(unittest.TestCase):
    
    def test_extract_with_both_markers(self):
        """Test extraction avec start et end markers présents"""
        html = "<p>Avant</p><p>START texte à extraire END</p><p>Après</p>"
        result = extract_operand(html, None, "START", "END")
        assert result is not None
        assert "START" in result
        assert "END" in result
        assert "texte à extraire" in result
    
    def test_extract_with_only_start_marker(self):
        """Test extraction avec seulement start marker - doit trouver le tag englobant"""
        html = "<p>Avant</p><p>START texte à extraire</p><p>Après</p>"
        result = extract_operand(html, None, "START", None)
        assert result is not None
        assert "START" in result
        assert "texte à extraire" in result
    
    def test_no_start_marker_returns_none(self):
        """Test sans start marker - doit retourner None"""
        html = "<p>Du texte quelconque</p>"
        result = extract_operand(html, None, None, None)
        assert result is None
    
    def test_marker_not_found_returns_none(self):
        """Test quand le marker n'existe pas dans le HTML"""
        html = "<p>Du texte sans marker</p>"
        result = extract_operand(html, None, "INEXISTANT", None)
        assert result is None
    
    def test_extract_from_specific_section(self):
        """Test extraction depuis une section spécifique (source_article)"""
        html = """
        <section>Article 1.1 - Autre texte</section>
        <section>Article 1.2 - START contenu recherché END</section>
        <section>Article 1.3 - Encore autre chose</section>
        """
        result = extract_operand(html, "Article 1.2", "START", "END")
        assert result is not None
        assert "contenu recherché" in result


if __name__ == "__main__":
    unittest.main()
