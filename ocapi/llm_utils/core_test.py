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
from unittest.mock import Mock, patch

import pytest
import requests

import ocapi.llm_utils.core as llm_utils_module
from ocapi.exceptions import LLMNetworkError, LLMResponseError
from ocapi.llm_utils import ResolvedLLMModel, call_llm_api


def _make_success_response(content: str) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    return response


def test_call_llm_api_retries_until_success() -> None:
    cfg = ResolvedLLMModel(
        model_key="piag_mistral_medium",
        provider="mte-piag",
        model_name="mte-api-piag-mistral-medium-latest",
        api_key="piag-key",
        api_url="https://piag.example",
    )
    resilience_cfg = {
        "fallback_enabled": False,
        "timeout_seconds": 45,
        "retry": {"primary": {"max_attempts": 5, "base_delay_ms": 1, "max_delay_ms": 1}},
    }

    with patch("ocapi.llm_utils.core._load_llm_resilience_config", return_value=resilience_cfg):
        with patch("ocapi.llm_utils.core.time.sleep", return_value=None):
            with patch(
                "ocapi.llm_utils.core.requests.post",
                side_effect=[
                    requests.exceptions.Timeout("timeout-1"),
                    requests.exceptions.Timeout("timeout-2"),
                    _make_success_response("ok"),
                ],
            ) as mocked_post:
                result = call_llm_api(cfg, "prompt")

    assert result == "ok"
    assert mocked_post.call_count == 3
    for call in mocked_post.call_args_list:
        assert call.kwargs["timeout"] == 45


def test_call_llm_api_no_retry_for_non_retryable_http_error() -> None:
    cfg = ResolvedLLMModel(
        model_key="piag_mistral_medium",
        provider="mte-piag",
        model_name="mte-api-piag-mistral-medium-latest",
        api_key="piag-key",
        api_url="https://piag.example",
    )
    resilience_cfg = {
        "fallback_enabled": False,
        "timeout_seconds": 45,
        "retry": {"primary": {"max_attempts": 5, "base_delay_ms": 1, "max_delay_ms": 1}},
    }
    bad_response = Mock()
    bad_response.status_code = 400
    non_retryable_error = requests.exceptions.HTTPError(response=bad_response)

    with patch("ocapi.llm_utils.core._load_llm_resilience_config", return_value=resilience_cfg):
        with patch("ocapi.llm_utils.core.time.sleep", return_value=None):
            with patch(
                "ocapi.llm_utils.core.requests.post",
                side_effect=[non_retryable_error],
            ) as mocked_post:
                with pytest.raises(LLMNetworkError):
                    call_llm_api(cfg, "prompt")

    assert mocked_post.call_count == 1


def test_call_llm_api_fallback_uses_secondary_strategy() -> None:
    primary_cfg = ResolvedLLMModel(
        model_key="piag_mistral_medium",
        provider="mte-piag",
        model_name="mte-api-piag-mistral-medium-latest",
        api_key="piag-key",
        api_url="https://piag.example",
    )
    secondary_cfg = ResolvedLLMModel(
        model_key="openai_gpt5",
        provider="openai",
        model_name="gpt-5",
        api_key="openai-key",
        api_url="https://openai.example",
    )
    resilience_cfg = {
        "fallback_enabled": True,
        "timeout_seconds": 45,
        "retry": {
            "primary": {"max_attempts": 2, "base_delay_ms": 1, "max_delay_ms": 1},
            "secondary": {"max_attempts": 2, "base_delay_ms": 1, "max_delay_ms": 1},
        },
    }
    models_cfg = {
        "primary_model_key": "piag_mistral_medium",
        "secondary_model_key": "openai_gpt5",
        "models": {
            "piag_mistral_medium": {
                "provider": "mte-piag",
                "model_id": "mte-api-piag-mistral-medium-latest",
            },
            "openai_gpt5": {"provider": "openai", "model_id": "gpt-5"},
        },
    }

    with patch("ocapi.llm_utils.core._load_llm_resilience_config", return_value=resilience_cfg):
        with patch("ocapi.llm_utils.core._load_llm_models_config", return_value=models_cfg):
            with patch("ocapi.llm_utils.core.config_model_llm", return_value=secondary_cfg):
                with patch("ocapi.llm_utils.core.time.sleep", return_value=None):
                    with patch(
                        "ocapi.llm_utils.core.requests.post",
                        side_effect=[
                            requests.exceptions.Timeout("p1"),
                            requests.exceptions.Timeout("p2"),
                            requests.exceptions.Timeout("s1"),
                            _make_success_response("fallback-ok"),
                        ],
                    ) as mocked_post:
                        result = call_llm_api(primary_cfg, "prompt")

    assert result == "fallback-ok"
    assert mocked_post.call_count == 4
    for call in mocked_post.call_args_list:
        assert call.kwargs["timeout"] == 45


def test_call_llm_api_uses_configured_timeout() -> None:
    cfg = ResolvedLLMModel(
        model_key="piag_mistral_medium",
        provider="mte-piag",
        model_name="mte-api-piag-mistral-medium-latest",
        api_key="piag-key",
        api_url="https://piag.example",
    )
    resilience_cfg = {
        "fallback_enabled": False,
        "timeout_seconds": 12,
        "retry": {"primary": {"max_attempts": 1}},
    }

    with patch("ocapi.llm_utils.core._load_llm_resilience_config", return_value=resilience_cfg):
        with patch(
            "ocapi.llm_utils.core.requests.post",
            return_value=_make_success_response("ok"),
        ) as mocked_post:
            result = call_llm_api(cfg, "prompt")

    assert result == "ok"
    assert mocked_post.call_count == 1
    assert mocked_post.call_args.kwargs["timeout"] == 12


def test_call_llm_api_invalid_timeout_falls_back_to_default() -> None:
    cfg = ResolvedLLMModel(
        model_key="piag_mistral_medium",
        provider="mte-piag",
        model_name="mte-api-piag-mistral-medium-latest",
        api_key="piag-key",
        api_url="https://piag.example",
    )
    resilience_cfg = {
        "fallback_enabled": False,
        "timeout_seconds": "invalid",
        "retry": {"primary": {"max_attempts": 1}},
    }

    with patch("ocapi.llm_utils.core._load_llm_resilience_config", return_value=resilience_cfg):
        with patch(
            "ocapi.llm_utils.core.requests.post",
            return_value=_make_success_response("ok"),
        ) as mocked_post:
            result = call_llm_api(cfg, "prompt")

    assert result == "ok"
    assert mocked_post.call_count == 1
    assert mocked_post.call_args.kwargs["timeout"] == 45


def test_call_llm_api_raises_on_invalid_response_shape() -> None:
    cfg = ResolvedLLMModel(
        model_key="piag_mistral_medium",
        provider="mte-piag",
        model_name="mte-api-piag-mistral-medium-latest",
        api_key="piag-key",
        api_url="https://piag.example",
    )
    resilience_cfg = {
        "fallback_enabled": False,
        "timeout_seconds": 45,
        "retry": {"primary": {"max_attempts": 1}},
    }
    bad_response = Mock()
    bad_response.raise_for_status.return_value = None
    bad_response.json.return_value = {"unexpected": "shape"}

    with patch("ocapi.llm_utils.core._load_llm_resilience_config", return_value=resilience_cfg):
        with patch("ocapi.llm_utils.core.requests.post", return_value=bad_response):
            with pytest.raises(LLMResponseError, match="Invalid LLM response format"):
                call_llm_api(cfg, "prompt")


def test_call_llm_api_rate_limit_applies_min_interval() -> None:
    cfg = ResolvedLLMModel(
        model_key="piag_mistral_medium",
        provider="mte-piag",
        model_name="mte-api-piag-mistral-medium-latest",
        api_key="piag-key",
        api_url="https://piag.example",
    )
    resilience_cfg = {
        "fallback_enabled": False,
        "timeout_seconds": 45,
        "retry": {"primary": {"max_attempts": 1}},
    }
    rate_limit_cfg = {"enabled": True, "min_interval_ms": 500}
    llm_utils_module._RATE_LIMIT_LAST_CALL_MONOTONIC = None

    with patch("ocapi.llm_utils.core._load_llm_resilience_config", return_value=resilience_cfg):
        with patch("ocapi.llm_utils.core._load_llm_rate_limit_config", return_value=rate_limit_cfg):
            with patch(
                "ocapi.llm_utils.core.requests.post",
                return_value=_make_success_response("ok"),
            ) as mocked_post:
                with patch(
                    "ocapi.llm_utils.core.time.monotonic",
                    side_effect=[100.0, 100.1, 100.5],
                ):
                    with patch(
                        "ocapi.llm_utils.core.time.sleep", return_value=None
                    ) as mocked_sleep:
                        first_result = call_llm_api(cfg, "prompt-1")
                        second_result = call_llm_api(cfg, "prompt-2")

    assert first_result == "ok"
    assert second_result == "ok"
    assert mocked_post.call_count == 2
    assert mocked_sleep.call_count == 1
    assert mocked_sleep.call_args.args[0] == pytest.approx(0.4, abs=0.001)
    llm_utils_module._RATE_LIMIT_LAST_CALL_MONOTONIC = None


def test_call_llm_api_rate_limit_disabled_does_not_sleep() -> None:
    cfg = ResolvedLLMModel(
        model_key="piag_mistral_medium",
        provider="mte-piag",
        model_name="mte-api-piag-mistral-medium-latest",
        api_key="piag-key",
        api_url="https://piag.example",
    )
    resilience_cfg = {
        "fallback_enabled": False,
        "timeout_seconds": 45,
        "retry": {"primary": {"max_attempts": 1}},
    }
    rate_limit_cfg = {"enabled": False, "min_interval_ms": 500}
    llm_utils_module._RATE_LIMIT_LAST_CALL_MONOTONIC = None

    with patch("ocapi.llm_utils.core._load_llm_resilience_config", return_value=resilience_cfg):
        with patch("ocapi.llm_utils.core._load_llm_rate_limit_config", return_value=rate_limit_cfg):
            with patch(
                "ocapi.llm_utils.core.requests.post",
                return_value=_make_success_response("ok"),
            ) as mocked_post:
                with patch("ocapi.llm_utils.core.time.sleep", return_value=None) as mocked_sleep:
                    result = call_llm_api(cfg, "prompt")

    assert result == "ok"
    assert mocked_post.call_count == 1
    assert mocked_sleep.call_count == 0
    llm_utils_module._RATE_LIMIT_LAST_CALL_MONOTONIC = None
