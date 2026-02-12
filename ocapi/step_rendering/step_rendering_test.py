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

from ocapi.step_rendering.make_header import make_permit_header
from ocapi.step_rendering.make_other import make_permit_other
from ocapi.types import ArreteFile, NodeId, Operation, OperationType


def _make_arrete_file_from_str(
    arrete_id: str,
    aiot: str,
    filename: str,
    html: str,
    status: bool = True,
) -> ArreteFile:
    return ArreteFile(
        id=arrete_id,
        aiot=aiot,
        filename=filename,
        soup=BeautifulSoup(html, "html.parser"),
        status=status,
    )


def test_make_permit_header_contains_permit_specs_and_ordering() -> None:
    arrete_2021 = _make_arrete_file_from_str(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="arrete_2021",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>Titre 2021</h1></div>
 <div data-spec="visa">VISA UNIQUE 1</div>
 <div data-spec="visa">VISA UNIQUE 2</div>
 <div data-spec="motifs">MOTIF 2021</div>
</body></html>
""",
    )
    arrete_2020 = _make_arrete_file_from_str(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="arrete_2020",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="arrete_title"><h1>Titre 2020</h1></div>
 <div data-spec="visa">VISA UNIQUE 1</div>
 <div data-spec="motifs">MOTIF 2020</div>
</body></html>
""",
    )

    html = make_permit_header([arrete_2021, arrete_2020])

    assert 'data-spec="permit_title"' in html
    assert 'data-spec="permit_sources"' in html
    assert 'data-spec="permit_visa"' in html
    assert 'data-spec="permit_motif"' in html
    assert html.count("VISA UNIQUE 1") == 1
    assert html.index('data-date="2020-01-01"') < html.index('data-date="2021-01-01"')


def test_make_permit_header_raises_when_multiple_aiot_detected() -> None:
    arrete_1 = _make_arrete_file_from_str(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="arrete_1",
        html='<html><body data-arretify_version="0.1.0"></body></html>',
    )
    arrete_2 = _make_arrete_file_from_str(
        arrete_id="2022-01-01",
        aiot="0002",
        filename="arrete_2",
        html='<html><body data-arretify_version="0.1.0"></body></html>',
    )

    with pytest.raises(ValueError, match="multiple AIOT"):
        make_permit_header([arrete_1, arrete_2])


def test_make_permit_other_contains_only_non_consolidated_complements() -> None:
    ap_initial = _make_arrete_file_from_str(
        arrete_id="2020-01-01",
        aiot="0001",
        filename="ap_initial",
        html=(
            '<html><body data-arretify_version="0.1.0"><main data-spec="main">'
            "</main></body></html>"
        ),
    )
    complement_no_ops = _make_arrete_file_from_str(
        arrete_id="2021-01-01",
        aiot="0001",
        filename="complement_no_ops",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID COMPLEMENT A</div>
 <div data-spec="arrete_title">TITLE COMPLEMENT A</div>
 <main data-spec="main"><p>MAIN A</p></main>
</body></html>
""",
    )
    complement_with_ops = _make_arrete_file_from_str(
        arrete_id="2022-01-01",
        aiot="0001",
        filename="complement_with_ops",
        html="""
<html><body data-arretify_version="0.1.0">
 <div data-spec="identification">ID COMPLEMENT B</div>
 <div data-spec="arrete_title">TITLE COMPLEMENT B</div>
 <main data-spec="main"><p>MAIN B</p></main>
</body></html>
""",
    )
    operations = [
        Operation(
            id="op-1",
            source_id=NodeId(arrete_id="2022-01-01", article_id="1"),
            target_id=NodeId(arrete_id="2020-01-01", article_id="1"),
            operation_type=OperationType.REPLACE,
        )
    ]

    html = make_permit_other([ap_initial, complement_no_ops, complement_with_ops], operations)

    assert 'data-spec="permit_complements"' in html
    assert 'data-spec="permit_complement"' in html
    assert "ID COMPLEMENT A" in html
    assert "TITLE COMPLEMENT A" in html
    assert "MAIN A" in html
    assert "MAIN B" not in html
