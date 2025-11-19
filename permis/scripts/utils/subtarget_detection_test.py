import unittest
from permis.scripts.utils.subtarget_detection import detect_subtarget, SubTargetType



class TestSubtargetDetection(unittest.TestCase):
    def test_simple_tableau_detection(self):

        text = "le tableau"
        result = detect_subtarget(text)
        assert result.type == SubTargetType.TABLEAU

    def test_complex_detection(self):

        text = "quelque chose de très compliqué qui nécessite un LLM"
        result = detect_subtarget(text)
        assert result.type == SubTargetType.COMPLEX

    def test_ordinal_extraction(self):
        text = "la troisième ligne du tableau"
        text2 = "le 2eme paragraphe"
        result = detect_subtarget(text)
        result2 = detect_subtarget(text2)

        assert result.type == SubTargetType.LIGNE_TABLEAU
        assert result.position == 3
        assert result2.type == SubTargetType.PARAGRAPHE
        assert result2.position == 2
    