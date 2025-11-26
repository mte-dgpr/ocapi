import unittest

from bs4 import BeautifulSoup
from permis.scripts.utils.subtarget_detection import replace_subtarget, parse_subtarget, SubTargetType



class TestSubtargetParsing(unittest.TestCase):
    def test_simple_tableau_detection(self):

        text = "le tableau"
        result = parse_subtarget(text)
        assert result.type == SubTargetType.TABLEAU

    def test_complex_detection(self):

        text = "quelque chose de très compliqué qui nécessite un LLM"
        result = parse_subtarget(text)
        assert result.type == SubTargetType.COMPLEX

    def test_ordinal_extraction(self):
        text = "la troisième ligne du tableau"
        text2 = "le 2eme alinea"
        result = parse_subtarget(text)
        result2 = parse_subtarget(text2)

        assert result.type == SubTargetType.LIGNE_TABLEAU
        assert result.position == 3
        assert result2.type == SubTargetType.ALINEA
        assert result2.position == 2

class TestReplaceSubtarget(unittest.TestCase):
    def test_replace_full_section(self):

        html = "<div><p>Paragraph 1.</p><p>Paragraph 2.</p></div>"
        soup = BeautifulSoup(html, 'html.parser')
        subtarget = parse_subtarget("contenu entier")
        operand = "<p>Nouveau contenu.</p>"
        result = replace_subtarget(soup, subtarget, operand)
        assert result == soup  # Should return the whole section

    def test_replace_phrase(self):

        html = "<div>First sentence. Second sentence. Third sentence.</div>"
        soup = BeautifulSoup(html, 'html.parser')
        subtarget = parse_subtarget("la 2ème phrase")
        operand = "Deuxième phrase modifiée"
        result = replace_subtarget(soup, subtarget, operand)
        assert str(result) == "<div>First sentence. Deuxième phrase modifiée. Third sentence.</div>"  # Should return the second sentence

    def test_replace_tableau(self):
        html = "<div><table><tr><td>Cell 1</td></tr></table></div>"
        soup = BeautifulSoup(html, 'html.parser')
        subtarget = parse_subtarget("le tableau")
        operand = "<table><tr><td>Nouvelle Cellule</td></tr></table>"
        result = replace_subtarget(soup, subtarget, operand)
        assert str(result) == "<div><table><tr><td>Nouvelle Cellule</td></tr></table></div>"  # Should return the modified table
    
    def test_replace_alinea(self):
        html = "<div><div class='arretify-alinea' data-number='1'>Alinea 1</div><div class='arretify-alinea' data-number='2'>Alinea 2</div></div>"
        soup = BeautifulSoup(html, 'html.parser')
        subtarget = parse_subtarget("le 2ème alinea")

        result = replace_subtarget(soup, subtarget, "Alinea modifié")
        assert result.get_text() == "Alinea 1Alinea modifié"  # Should return the second alinea
