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
from bs4 import BeautifulSoup

from ocapi.types import SubTargetType
from ocapi.utils.subtarget_utils import (
    insert_content_after_subtarget,
    parse_subtarget,
    replace_subtarget,
)


def test_simple_table_detection() -> None:
    result = parse_subtarget("le tableau")
    assert result.type == SubTargetType.TABLEAU


def test_complex_detection() -> None:
    result = parse_subtarget("quelque chose de très compliqué qui nécessite un LLM")
    assert result.type == SubTargetType.COMPLEX


def test_ordinal_extraction() -> None:
    result = parse_subtarget("la troisième ligne du tableau")
    result2 = parse_subtarget("le 2eme alinea")

    assert result.type == SubTargetType.LIGNE_TABLEAU
    assert result.position == 3
    assert result2.type == SubTargetType.ALINEA
    assert result2.position == 2


def test_replace_full_section() -> None:
    html = "<div><p>Paragraph 1.</p><p>Paragraph 2.</p></div>"
    soup = BeautifulSoup(html, "html.parser")
    subtarget = parse_subtarget("contenu entier")
    result = replace_subtarget(soup, subtarget, "<p>Nouveau contenu.</p>")
    assert result == soup


def test_replace_sentence() -> None:
    html = "<div>First sentence. Second sentence. Third sentence.</div>"
    soup = BeautifulSoup(html, "html.parser")
    subtarget = parse_subtarget("la 2ème phrase")
    result = replace_subtarget(soup, subtarget, "Deuxième phrase modifiée")
    assert str(result) == "<div>First sentence. Deuxième phrase modifiée. Third sentence.</div>"


def test_replace_table() -> None:
    html = "<div><table><tr><td>Cell 1</td></tr></table></div>"
    soup = BeautifulSoup(html, "html.parser")
    subtarget = parse_subtarget("le tableau")
    result = replace_subtarget(soup, subtarget, "<table><tr><td>Nouvelle Cellule</td></tr></table>")
    assert str(result) == "<div><table><tr><td>Nouvelle Cellule</td></tr></table></div>"


def test_replace_alinea() -> None:
    html = (
        "<div>"
        "<div class='arretify-alinea' data-number='1'>Alinea 1</div>"
        "<div class='arretify-alinea' data-number='2'>Alinea 2</div>"
        "</div>"
    )
    soup = BeautifulSoup(html, "html.parser")
    subtarget = parse_subtarget("le 2ème alinea")
    result = replace_subtarget(soup, subtarget, "Alinea modifié")
    assert result.get_text() == "Alinea 1Alinea modifié"


def test_insert_content_after_tableau() -> None:
    html = "<div><table><tr><td>Cell</td></tr></table></div>"
    soup = BeautifulSoup(html, "html.parser")
    subtarget = parse_subtarget("le tableau")
    result = insert_content_after_subtarget(soup, subtarget, "<p>Après tableau</p>")
    assert str(result) == (
        "<div><table><tr><td>Cell</td></tr></table><p>Après tableau</p></div>"
    )
