#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
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
from pathlib import Path
from unittest.mock import MagicMock, patch

from ocapi.cli import main, run_main
from ocapi.utils.testing import make_testing_arrete


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_operations_from_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--operations-from is parsed; run_main loads operations and skips detection."""
    main(["run", "some/arretes_html/0005804239", "--operations-from", "/data/ops"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("operations_from") == Path("/data/ops")
    assert kwargs.get("enable_rendering") is True


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_no_rendering_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--no-rendering is parsed and forwarded to run_main."""
    main(["run", "some/arretes_html/0005804239", "--no-rendering"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("enable_rendering") is False


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_include_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--include IDs are forwarded to run_main."""
    main(["run", "some/arretes_html/0005804239", "--include", "2024-09-27", "2023-12-04"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("include_ids") == ["2024-09-27", "2023-12-04"]


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_aiot_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--aiot is forwarded to run_main."""
    main(["run", "some/arretes_html/0005804239", "--aiot", "0005804239"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("aiot") == "0005804239"


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_output_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--output dir is forwarded to run_main as Path."""
    main(["run", "some/arretes_html/0005804239", "--output", "out/"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("output_dir") == Path("out/")


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_start_date_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--start-date is parsed and forwarded to run_main."""
    main(["run", "some/arretes_html/0005804239", "--start-date", "2014-01-09"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("start_date") == "2014-01-09"


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_no_start_date_defaults_to_none(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """Without --start-date, start_date defaults to None."""
    main(["run", "some/arretes_html/0005804239"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("start_date") is None


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_include_and_start_date_coexist(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--include and --start-date can be used together."""
    main(
        [
            "run",
            "some/arretes_html/0005804239",
            "--include",
            "2024-09-27",
            "--start-date",
            "2014-01-09",
        ]
    )
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("include_ids") == ["2024-09-27"]
    assert kwargs.get("start_date") == "2014-01-09"


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_defaults(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """Without flags, rendering is enabled and tagging is disabled by default."""
    main(["run", "some/arretes_html/0005804239"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("enable_rendering") is True
    assert kwargs.get("enable_tagging") is False
    assert kwargs.get("output_dir") is None
    assert kwargs.get("aiot") is None
    assert kwargs.get("principal_id") is None


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_principal_id_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--principal-id is parsed and forwarded to run_main."""
    main(["run", "some/arretes_html/0005804239", "--principal-id", "2024-09-27"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("principal_id") == "2024-09-27"


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_enable_tagging_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    main(["run", "some/arretes_html/0005804239", "--enable-tagging"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("enable_tagging") is True


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_tagged_output_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    main(["run", "some/arretes_html/0005804239", "--tagged-output", "/tmp/tagged"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("tagged_output_dir") == Path("/tmp/tagged")


@patch("ocapi.cli.save_tagged_html_file")
@patch("ocapi.cli.run_pipeline")
@patch("ocapi.cli.load_document_contexts")
def test_run_main_principal_id_flags_matching_arrete(
    mock_load: MagicMock,
    mock_pipeline: MagicMock,
    _mock_save: MagicMock,
    tmp_path: Path,
) -> None:
    """--principal-id marks the matching arrêté before the pipeline runs."""
    arretes = [make_testing_arrete("2020-01-01"), make_testing_arrete("2024-09-27")]
    mock_load.return_value = [(af, MagicMock()) for af in arretes]
    mock_pipeline.return_value = ([], {}, arretes, None)

    exit_code = run_main(
        tmp_path,
        enable_rendering=False,
        principal_id="2024-09-27",
    )

    assert exit_code == 0
    assert arretes[0].principal is False
    assert arretes[1].principal is True


@patch("ocapi.cli.run_pipeline")
@patch("ocapi.cli.load_document_contexts")
def test_run_main_principal_id_missing_returns_error(
    mock_load: MagicMock,
    mock_pipeline: MagicMock,
    tmp_path: Path,
) -> None:
    """--principal-id with no matching arrêté returns exit code 1 and skips the pipeline."""
    mock_load.return_value = [(make_testing_arrete("2020-01-01"), MagicMock())]

    exit_code = run_main(
        tmp_path,
        enable_rendering=False,
        principal_id="2030-01-01",
    )

    assert exit_code == 1
    mock_pipeline.assert_not_called()
