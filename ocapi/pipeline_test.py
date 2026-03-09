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
from unittest.mock import patch

from bs4 import BeautifulSoup

from ocapi.pipeline import run_pipeline
from ocapi.types import ArreteFile


def _make_arrete(arrete_id: str) -> ArreteFile:
    html = f"""
    <html><body data-arretify_version="0.1.0">
     <main data-spec="main">
      <section data-spec="section" data-number="1"><p>{arrete_id}</p></section>
     </main>
    </body></html>
    """
    return ArreteFile(
        id=arrete_id,
        aiot="0001",
        filename=f"{arrete_id}_test.html",
        soup=BeautifulSoup(html, "html.parser"),
    )


@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_start_date_skips_earlier_arretes(  # type: ignore[no-untyped-def]
    mock_chunking, mock_detection
) -> None:
    """start_date exclut l'arrêté initial (<=) : seuls les arrêtés strictement postérieurs sont détectés."""  # noqa: E501
    arretes = [
        _make_arrete("2009-12-08"),
        _make_arrete("2014-01-09"),
        _make_arrete("2023-12-04"),
    ]

    run_pipeline(arretes, start_date="2014-01-09", enable_rendering=False)

    chunked_ids = [call.args[0].id for call in mock_chunking.call_args_list]
    assert "2009-12-08" not in chunked_ids
    assert "2014-01-09" not in chunked_ids
    assert "2023-12-04" in chunked_ids
    assert mock_chunking.call_count == 1


@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_start_date_none_processes_all(  # type: ignore[no-untyped-def]
    mock_chunking, mock_detection
) -> None:
    arretes = [_make_arrete("2009-12-08"), _make_arrete("2014-01-09")]

    run_pipeline(arretes, start_date=None, enable_rendering=False)

    assert mock_chunking.call_count == 2


@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_start_date_after_all_arretes_processes_none(  # type: ignore[no-untyped-def]
    mock_chunking, mock_detection
) -> None:
    arretes = [_make_arrete("2009-12-08"), _make_arrete("2014-01-09")]

    run_pipeline(arretes, start_date="2025-01-01", enable_rendering=False)

    assert mock_chunking.call_count == 0


@patch("ocapi.pipeline.step_rendering")
@patch("ocapi.pipeline.step_resolution", return_value=({}, []))
@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_start_date_passes_all_arretes_to_resolution(  # type: ignore[no-untyped-def]
    mock_chunking, mock_detection, mock_resolution, mock_rendering
) -> None:
    """start_date filters detection, but all arrêtés must still reach resolution."""
    arretes = [
        _make_arrete("2009-12-08"),
        _make_arrete("2014-01-09"),
        _make_arrete("2023-12-04"),
    ]

    run_pipeline(arretes, start_date="2014-01-09", enable_rendering=False)

    assert mock_chunking.call_count == 1
    mock_resolution.assert_called_once()
    resolved_arretes = mock_resolution.call_args[0][1]
    resolved_ids = [a.id for a in resolved_arretes]
    assert "2009-12-08" in resolved_ids
    assert "2014-01-09" in resolved_ids
    assert "2023-12-04" in resolved_ids


@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_start_date_equal_to_first_arrete_skips_it(  # type: ignore[no-untyped-def]
    mock_chunking, mock_detection
) -> None:
    """Boundary: start_date == earliest arrêté exclut cet arrêté de la détection (<=)."""
    arretes = [_make_arrete("2009-12-08"), _make_arrete("2014-01-09")]

    run_pipeline(arretes, start_date="2009-12-08", enable_rendering=False)

    chunked_ids = [call.args[0].id for call in mock_chunking.call_args_list]
    assert "2009-12-08" not in chunked_ids
    assert "2014-01-09" in chunked_ids
    assert mock_chunking.call_count == 1
