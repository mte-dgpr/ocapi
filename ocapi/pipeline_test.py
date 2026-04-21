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
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from ocapi.pipeline import run_pipeline
from ocapi.types import ArreteFile, NodeId, Operation, OperationType


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
def test_start_date_skips_earlier_arretes(
    mock_chunking: MagicMock, mock_detection: MagicMock
) -> None:
    """start_date excludes the initial arrêté (<=): only strictly later arrêtés are detected."""
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
def test_start_date_none_defaults_to_first_arrete(
    mock_chunking: MagicMock, mock_detection: MagicMock
) -> None:
    """Without start_date, the first arrêté is excluded from detection by default."""
    arretes = [_make_arrete("2009-12-08"), _make_arrete("2014-01-09")]

    run_pipeline(arretes, start_date=None, enable_rendering=False)

    chunked_ids = [call.args[0].id for call in mock_chunking.call_args_list]
    assert "2009-12-08" not in chunked_ids
    assert "2014-01-09" in chunked_ids
    assert mock_chunking.call_count == 1


@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_start_date_after_all_arretes_processes_none(
    mock_chunking: MagicMock, mock_detection: MagicMock
) -> None:
    arretes = [_make_arrete("2009-12-08"), _make_arrete("2014-01-09")]

    run_pipeline(arretes, start_date="2025-01-01", enable_rendering=False)

    assert mock_chunking.call_count == 0


@patch("ocapi.pipeline.step_rendering")
@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_start_date_passes_all_arretes_to_resolution(
    mock_chunking: MagicMock,
    mock_detection: MagicMock,
    mock_resolution: MagicMock,
    mock_rendering: MagicMock,
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


@patch("ocapi.pipeline.step_resolution", return_value=({}, [], []))
@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_run_pipeline_with_preloaded_operations(
    mock_chunking: MagicMock,
    mock_detection: MagicMock,
    mock_resolution: MagicMock,
) -> None:
    """When operations are provided and enable_detection=False, detection is skipped."""
    arretes = [_make_arrete("2009-12-08"), _make_arrete("2014-01-09")]
    preloaded = [
        Operation(
            id="1",
            source_id=NodeId(arrete_id="2014-01-09", article_id="1"),
            target_id=NodeId(arrete_id="2009-12-08", article_id="1"),
            operation_type=OperationType.REPLACE,
            operand="<p>test</p>",
            sub_target=None,
        )
    ]
    mock_resolution.return_value = ({}, arretes, preloaded)

    ops, history, _arretes, _permis = run_pipeline(
        arretes,
        enable_detection=False,
        enable_rendering=False,
        operations=preloaded,
    )

    assert ops == preloaded
    assert mock_chunking.call_count == 0
    assert mock_detection.call_count == 0
    mock_resolution.assert_called_once_with(preloaded, arretes, enable_llm=True)


@patch("ocapi.pipeline.step_detection", return_value=[])
@patch("ocapi.pipeline.step_chunking", return_value=([], {}))
def test_start_date_equal_to_first_arrete_skips_it(
    mock_chunking: MagicMock, mock_detection: MagicMock
) -> None:
    """Boundary: start_date == earliest arrêté excludes that arrêté from detection (<=)."""
    arretes = [_make_arrete("2009-12-08"), _make_arrete("2014-01-09")]

    run_pipeline(arretes, start_date="2009-12-08", enable_rendering=False)

    chunked_ids = [call.args[0].id for call in mock_chunking.call_args_list]
    assert "2009-12-08" not in chunked_ids
    assert "2014-01-09" in chunked_ids
    assert mock_chunking.call_count == 1
