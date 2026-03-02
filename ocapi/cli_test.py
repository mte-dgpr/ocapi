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

from ocapi.cli import main


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.config_model_llm")
@patch("ocapi.cli.load_arrete_files", return_value=[])
@patch("ocapi.cli.run_pipeline", return_value=([], {}, [], None))
def test_cli_start_date_is_forwarded(
    mock_pipeline: MagicMock,
    mock_load: MagicMock,
    mock_llm: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--start-date is parsed and forwarded to run_pipeline."""
    mock_llm.return_value = MagicMock(model_name="test-model")
    main(["run", "some/dir", "--start-date", "2014-01-09"])
    mock_pipeline.assert_called_once()
    _args, kwargs = mock_pipeline.call_args
    assert kwargs.get("start_date") == "2014-01-09" or (len(_args) > 1 and _args[1] == "2014-01-09")


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.config_model_llm")
@patch("ocapi.cli.load_arrete_files", return_value=[])
@patch("ocapi.cli.run_pipeline", return_value=([], {}, [], None))
def test_cli_no_start_date_defaults_to_none(
    mock_pipeline: MagicMock,
    mock_load: MagicMock,
    mock_llm: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """Without --start-date, start_date is None."""
    mock_llm.return_value = MagicMock(model_name="test-model")
    main(["run", "some/dir"])
    mock_pipeline.assert_called_once()
    _args, kwargs = mock_pipeline.call_args
    assert kwargs.get("start_date") is None


@patch("ocapi.cli.initialize_root_logger")
@patch("ocapi.cli.config_model_llm")
@patch("ocapi.cli.load_arrete_files")
@patch("ocapi.cli.run_pipeline", return_value=([], {}, [], None))
def test_cli_include_and_start_date_coexist(
    mock_pipeline: MagicMock,
    mock_load: MagicMock,
    mock_llm: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """--include and --start-date can be used together."""
    mock_llm.return_value = MagicMock(model_name="test-model")
    fake_arrete = MagicMock()
    fake_arrete.id = "2024-09-27"
    mock_load.return_value = [fake_arrete]
    main(["run", "some/dir", "--include", "2024-09-27", "--start-date", "2014-01-09"])
    mock_pipeline.assert_called_once()
    _args, kwargs = mock_pipeline.call_args
    assert kwargs.get("start_date") == "2014-01-09"
