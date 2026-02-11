#
# Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).
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
import unittest

from bs4 import BeautifulSoup

from ocapi.types import SubTargetType
from ocapi.utils.subtarget_utils import parse_subtarget, replace_subtarget


class TestSubtargetParsing(unittest.TestCase):
    def test_simple_tableau_detection(self) -> None:

        text = "le tableau"
        result = parse_subtarget(text)
        assert result.type == SubTargetType.TABLEAU

    def test_complex_detection(self) -> None:

        text = "quelque chose de très compliqué qui nécessite un LLM"
        result = parse_subtarget(text)
        assert result.type == SubTargetType.COMPLEX

    def test_ordinal_extraction(self) -> None:
        text = "la troisième ligne du tableau"
        text2 = "le 2eme alinea"
        result = parse_subtarget(text)
        result2 = parse_subtarget(text2)

        assert result.type == SubTargetType.LIGNE_TABLEAU
        assert result.position == 3
        assert result2.type == SubTargetType.ALINEA
        assert result2.position == 2


class TestReplaceSubtarget(unittest.TestCase):
    def test_replace_full_section(self) -> None:

        html = "<div><p>Paragraph 1.</p><p>Paragraph 2.</p></div>"
        soup = BeautifulSoup(html, "html.parser")
        subtarget = parse_subtarget("contenu entier")
        operand = "<p>Nouveau contenu.</p>"
        result = replace_subtarget(soup, subtarget, operand)
        assert result == soup  # Should return the whole section

    def test_replace_phrase(self) -> None:

        html = "<div>First sentence. Second sentence. Third sentence.</div>"
        soup = BeautifulSoup(html, "html.parser")
        subtarget = parse_subtarget("la 2ème phrase")
        operand = "Deuxième phrase modifiée"
        result = replace_subtarget(soup, subtarget, operand)
        assert (
            str(result) == "<div>First sentence. Deuxième phrase modifiée. Third sentence.</div>"
        )  # Should return the second sentence

    def test_replace_tableau(self) -> None:
        html = "<div><table><tr><td>Cell 1</td></tr></table></div>"
        soup = BeautifulSoup(html, "html.parser")
        subtarget = parse_subtarget("le tableau")
        operand = "<table><tr><td>Nouvelle Cellule</td></tr></table>"
        result = replace_subtarget(soup, subtarget, operand)
        assert (
            str(result) == "<div><table><tr><td>Nouvelle Cellule</td></tr></table></div>"
        )  # Should return the modified table

    def test_replace_alinea(self) -> None:
        html = (
            "<div>"
            "<div class='arretify-alinea' data-number='1'>Alinea 1</div>"
            "<div class='arretify-alinea' data-number='2'>Alinea 2</div>"
            "</div>"
        )
        soup = BeautifulSoup(html, "html.parser")
        subtarget = parse_subtarget("le 2ème alinea")

        result = replace_subtarget(soup, subtarget, "Alinea modifié")
        # Should return the second alinea
        assert result.get_text() == "Alinea 1Alinea modifié"
