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
from pathlib import Path
from unittest.mock import MagicMock, patch

from ocapi.cli import main


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.run_main", return_value=0)
def test_cli_no_detection_is_forwarded(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--no-detection is parsed and forwarded to run_main."""
    main(["run", "some/arretes_html/0005804239", "--no-detection"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("enable_detection") is False
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
    assert kwargs.get("enable_detection") is True
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
def test_cli_defaults(
    mock_main: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """Without flags, detection and rendering are both enabled by default."""
    main(["run", "some/arretes_html/0005804239"])
    mock_main.assert_called_once()
    _, kwargs = mock_main.call_args
    assert kwargs.get("enable_detection") is True
    assert kwargs.get("enable_rendering") is True
    assert kwargs.get("output_dir") is None
    assert kwargs.get("aiot") is None
