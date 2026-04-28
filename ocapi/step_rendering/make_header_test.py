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
import pytest
from bs4 import BeautifulSoup

from ocapi.step_rendering.make_header import (
    make_permit_header,
    make_permit_motif,
    make_permit_sources,
    make_permit_visa,
)
from ocapi.types import FileType
from ocapi.utils.testing import make_arrete


def test_make_permit_header_contains_permit_specs_and_ordering() -> None:
    arrete_2021 = make_arrete(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="arrete_2021",
        html="""
<html><body data-arretify_version="0.2.0">
 <div data-spec="arrete_title"><h1>Titre 2021</h1></div>
 <div data-spec="visa">VISA UNIQUE 1</div>
 <div data-spec="visa">VISA UNIQUE 2</div>
 <div data-spec="motifs">MOTIF 2021</div>
</body></html>
""",
    )
    arrete_2020 = make_arrete(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="arrete_2020",
        html="""
<html><body data-arretify_version="0.2.0">
 <div data-spec="arrete_title"><h1>Titre 2020</h1></div>
 <div data-spec="visa">VISA UNIQUE 1</div>
 <div data-spec="motifs">MOTIF 2020</div>
</body></html>
""",
    )

    html = make_permit_header([arrete_2021, arrete_2020])
    rendered_soup = BeautifulSoup(html, "html.parser")
    permit_visa = rendered_soup.select_one('[data-spec="permit_visa"]')
    permit_title = rendered_soup.select_one('[data-spec="permit_title"]')

    assert 'data-spec="permit_title"' in html
    assert 'data-spec="permit_sources"' in html
    assert 'data-spec="permit_visa"' in html
    assert 'data-spec="permit_motif"' in html
    assert permit_visa is not None
    assert permit_title is not None
    assert permit_visa.get_text(" ", strip=True).count("VISA UNIQUE 1") == 2
    assert permit_title.get_text(" ", strip=True).count("0001") == 1
    assert html.index('data-date="2020-01-01"') < html.index('data-date="2021-01-01"')


def test_make_permit_sources_marks_abrogated_arretes() -> None:
    """Abrogated arrêtés must carry the (ABROGE) mention."""
    active = make_arrete(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_initial",
        html="""
<html><body data-arretify_version="0.2.0">
 <div data-spec="arrete_title"><h1>AP Initial</h1></div>
</body></html>
""",
        status=True,
    )
    abroge = make_arrete(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="ap_abroge",
        html="""
<html><body data-arretify_version="0.2.0">
 <div data-spec="arrete_title"><h1>AP Abrogé</h1></div>
</body></html>
""",
        status=False,
    )

    html = make_permit_sources([active, abroge])
    soup = BeautifulSoup(html, "html.parser")

    sources = soup.find_all("li", attrs={"data-spec": "permit_source"})
    assert len(sources) == 2

    active_source = soup.find("li", attrs={"data-status": "active"})
    abroge_source = soup.find("li", attrs={"data-status": "abroge"})
    assert active_source is not None
    assert abroge_source is not None
    assert "(ABROGE)" not in active_source.get_text()
    assert "(ABROGE)" in abroge_source.get_text()


def test_make_permit_header_includes_abrogated_arrete_with_visas_and_motifs() -> None:
    """Abrogated arrêté (refonte) must appear in header with ABROGE, its visas and motifs."""
    ap_2020_abroge = make_arrete(
        arrete_id="2020-04-20",
        aiot="0001",
        filename="ap_2020",
        html="""
<html><body data-arretify_version="0.2.0">
 <div data-spec="arrete_title"><h1>AP 2020</h1></div>
 <div data-spec="visa">VISA ARRETE 2020</div>
 <div data-spec="motifs">CONSIDERANT ARRETE 2020</div>
</body></html>
""",
        status=False,
    )
    ap_2021_refonte = make_arrete(
        arrete_id="2021-09-24",
        aiot="0001",
        filename="ap_2021",
        html="""
<html><body data-arretify_version="0.2.0">
 <div data-spec="arrete_title"><h1>AP 2021 Refonte</h1></div>
 <div data-spec="visa">VISA ARRETE 2021</div>
 <div data-spec="motifs">CONSIDERANT ARRETE 2021</div>
</body></html>
""",
        status=True,
    )

    html = make_permit_header([ap_2020_abroge, ap_2021_refonte])
    soup = BeautifulSoup(html, "html.parser")

    sources = soup.find_all("li", attrs={"data-spec": "permit_source"})
    assert len(sources) == 2
    abroge_source = soup.find("li", attrs={"data-status": "abroge"})
    assert abroge_source is not None
    assert "(ABROGE)" in abroge_source.get_text()
    assert "2020-04-20" in abroge_source.get_text()

    assert "VISA ARRETE 2020" in html
    assert "VISA ARRETE 2021" in html
    assert "CONSIDERANT ARRETE 2020" in html
    assert "CONSIDERANT ARRETE 2021" in html


def test_make_permit_visa_is_collapsible() -> None:
    """Consolidated visas must be inside a <details> element."""
    arrete = make_arrete(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="arrete",
        html="""
<html><body data-arretify_version="0.2.0">
 <div data-spec="visa">VISA 1</div>
</body></html>
""",
    )

    html = make_permit_visa([arrete])
    soup = BeautifulSoup(html, "html.parser")
    details = soup.find("details")
    assert details is not None
    assert "Visas consolidés" in details.get_text()
    assert "VISA 1" in details.get_text()


def test_make_permit_motif_is_collapsible() -> None:
    """Consolidated motifs must be inside a <details> element."""
    arrete = make_arrete(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="arrete",
        html="""
<html><body data-arretify_version="0.2.0">
 <div data-spec="arrete_title"><h1>Titre</h1></div>
 <div data-spec="motifs">MOTIF 1</div>
</body></html>
""",
    )

    html = make_permit_motif([arrete])
    soup = BeautifulSoup(html, "html.parser")
    details = soup.find("details")
    assert details is not None
    assert "Considérants" in details.get_text()
    assert "MOTIF 1" in details.get_text()


def test_make_permit_header_raises_when_multiple_aiot_detected() -> None:
    arrete_1 = make_arrete(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="arrete_1",
        html='<html><body data-arretify_version="0.2.0"></body></html>',
    )
    arrete_2 = make_arrete(
        arrete_id="2022-01-01",
        aiot="0002",
        filename="arrete_2",
        html='<html><body data-arretify_version="0.2.0"></body></html>',
    )

    with pytest.raises(ValueError, match="multiple AIOT"):
        make_permit_header([arrete_1, arrete_2])
