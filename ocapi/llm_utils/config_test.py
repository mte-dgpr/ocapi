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
from unittest.mock import patch

import pytest

from ocapi.config import settings
from ocapi.llm_utils import config_model_llm
from ocapi.llm_utils.config import _DEFAULT_LLM_RESILIENCE_CONFIG, _load_llm_resilience_config


def test_config_model_llm_uses_primary_and_secondary_keys() -> None:
    models_cfg = {
        "primary_model_key": "openai_primary",
        "secondary_model_key": "mistral_secondary",
        "models": {
            "openai_primary": {"provider": "openai", "model_id": "gpt-5"},
            "mistral_secondary": {
                "provider": "mte-piag",
                "model_id": "mte-api-piag-mistral-medium-latest",
            },
        },
    }

    with patch("ocapi.llm_utils.config._load_llm_models_config", return_value=models_cfg):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            side_effect=[
                ("openai-key", "https://openai.example"),
                ("piag-key", "https://piag.example"),
            ],
        ):
            primary = config_model_llm()
            secondary = config_model_llm("secondary")

    assert primary.provider == "openai"
    assert primary.model_name == "gpt-5"
    assert secondary.provider == "mte-piag"
    assert secondary.model_name == "mte-api-piag-mistral-medium-latest"


def test_default_models_config_uses_mistral_medium_3_5() -> None:
    default_models_cfg = {
        "primary_model_key": "mistral_medium-3-5",
        "secondary_model_key": None,
        "models": {
            "mistral_medium-3-5": {
                "provider": "mistral",
                "model_id": "mistral-medium-3-5",
                "reasoning_model": True,
            }
        },
    }

    with patch("ocapi.llm_utils.config._load_llm_models_config", return_value=default_models_cfg):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("mistral-key", "https://mistral.example"),
        ):
            primary = config_model_llm()

    assert primary.model_key == "mistral_medium-3-5"
    assert primary.provider == "mistral"
    assert primary.model_name == "mistral-medium-3-5"


def _fake_models_cfg() -> dict[str, object]:
    return {
        "primary_model_key": "openai_primary",
        "secondary_model_key": "mistral_secondary",
        "models": {
            "openai_primary": {"provider": "openai", "model_id": "gpt-5"},
            "mistral_secondary": {
                "provider": "mte-piag",
                "model_id": "mte-api-piag-mistral-medium-latest",
            },
            "anthropic_alt": {"provider": "anthropic", "model_id": "claude-opus-4-6"},
        },
    }


def test_env_overrides_primary_model_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_PRIMARY_MODEL_KEY replaces the JSON-configured primary."""
    monkeypatch.setenv("LLM_PRIMARY_MODEL_KEY", "anthropic_alt")
    with patch("ocapi.llm_utils.config._load_llm_models_config", return_value=_fake_models_cfg()):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("anthropic-key", "https://anthropic.example"),
        ):
            primary = config_model_llm()

    assert primary.model_key == "anthropic_alt"
    assert primary.provider == "anthropic"


def test_env_overrides_secondary_model_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_SECONDARY_MODEL_KEY replaces the JSON-configured secondary."""
    monkeypatch.setenv("LLM_SECONDARY_MODEL_KEY", "anthropic_alt")
    with patch("ocapi.llm_utils.config._load_llm_models_config", return_value=_fake_models_cfg()):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("anthropic-key", "https://anthropic.example"),
        ):
            secondary = config_model_llm("secondary")

    assert secondary.model_key == "anthropic_alt"


def test_unknown_env_model_key_is_ignored_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A bogus LLM_PRIMARY_MODEL_KEY falls back to the configured primary and logs."""
    monkeypatch.setenv("LLM_PRIMARY_MODEL_KEY", "does_not_exist")
    with patch("ocapi.llm_utils.config._load_llm_models_config", return_value=_fake_models_cfg()):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("openai-key", "https://openai.example"),
        ):
            with caplog.at_level("WARNING"):
                primary = config_model_llm()

    assert primary.model_key == "openai_primary"
    assert any("does_not_exist" in msg for msg in caplog.messages)


@pytest.mark.parametrize(
    "model_key, model_id",
    [
        ("albert_mistral-medium-2508", "mistral-medium-2508"),
        ("albert_gemma-4-31b", "gemma-4-31b-it"),
        ("albert_deepseek-v4-flash", "deepseek-v4-flash"),
    ],
)
def test_config_model_llm_resolves_albert_models(
    monkeypatch: pytest.MonkeyPatch, model_key: str, model_id: str
) -> None:
    """Albert models from llm_models.json use the Albert API key and endpoint."""
    monkeypatch.setattr(settings.llm, "albert_api_key", "albert-key")

    resolved = config_model_llm(model_key)

    assert resolved.provider == "albert"
    assert resolved.model_name == model_id
    assert resolved.api_key == "albert-key"
    assert resolved.api_url == "https://albert.api.etalab.gouv.fr/v1/chat/completions"


def test_config_model_llm_resolves_legacy_piag_key() -> None:
    """The former ``piag_mistral_medium`` key still resolves to the renamed PIAG model."""
    resolved = config_model_llm("piag_mistral_medium")

    assert resolved.model_key == "piag_mistral_medium-2508"
    assert resolved.provider == "mte-piag"


def _fake_models_cfg_with_reasoning() -> dict[str, object]:
    return {
        "primary_model_key": "openai_reasoning",
        "secondary_model_key": None,
        "models": {
            "openai_reasoning": {
                "provider": "openai",
                "model_id": "gpt-5",
                "reasoning_model": True,
            },
        },
    }


def test_disable_reasoning_env_overrides_json_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_DISABLE_REASONING=true forces reasoning_model to False even when JSON has True."""
    monkeypatch.setenv("LLM_DISABLE_REASONING", "true")
    with patch(
        "ocapi.llm_utils.config._load_llm_models_config",
        return_value=_fake_models_cfg_with_reasoning(),
    ):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("openai-key", "https://openai.example"),
        ):
            model = config_model_llm()

    assert model.reasoning_model is False


def test_disable_reasoning_env_not_set_uses_json_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without LLM_DISABLE_REASONING, reasoning_model reflects the JSON config."""
    monkeypatch.delenv("LLM_DISABLE_REASONING", raising=False)
    with patch(
        "ocapi.llm_utils.config._load_llm_models_config",
        return_value=_fake_models_cfg_with_reasoning(),
    ):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("openai-key", "https://openai.example"),
        ):
            model = config_model_llm()

    assert model.reasoning_model is True


def test_disable_reasoning_env_false_uses_json_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_DISABLE_REASONING=false must NOT force reasoning_model to True."""
    monkeypatch.setenv("LLM_DISABLE_REASONING", "false")
    with patch(
        "ocapi.llm_utils.config._load_llm_models_config",
        return_value=_fake_models_cfg_with_reasoning(),
    ):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("openai-key", "https://openai.example"),
        ):
            model = config_model_llm()

    assert model.reasoning_model is True


def test_disable_reasoning_no_effect_on_non_reasoning_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM_DISABLE_REASONING=true must leave reasoning_model as None for models without it."""
    monkeypatch.setenv("LLM_DISABLE_REASONING", "true")
    with patch(
        "ocapi.llm_utils.config._load_llm_models_config",
        return_value=_fake_models_cfg_without_reasoning(),
    ):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("piag-key", "https://piag.example"),
        ):
            model = config_model_llm()

    assert model.reasoning_model is None


def _fake_models_cfg_without_reasoning() -> dict[str, object]:
    return {
        "primary_model_key": "piag_model",
        "secondary_model_key": None,
        "models": {
            "piag_model": {
                "provider": "mte-piag",
                "model_id": "mte-api-piag-mistral-medium-latest",
            },
        },
    }


def test_disable_reasoning_no_effect_on_non_reasoning_model_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reasoning_model stays None for a non-reasoning model when LLM_DISABLE_REASONING is unset."""
    monkeypatch.delenv("LLM_DISABLE_REASONING", raising=False)
    with patch(
        "ocapi.llm_utils.config._load_llm_models_config",
        return_value=_fake_models_cfg_without_reasoning(),
    ):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("piag-key", "https://piag.example"),
        ):
            model = config_model_llm()

    assert model.reasoning_model is None


def test_disable_reasoning_no_effect_on_non_reasoning_model_env_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reasoning_model stays None for a non-reasoning model when LLM_DISABLE_REASONING=false."""
    monkeypatch.setenv("LLM_DISABLE_REASONING", "false")
    with patch(
        "ocapi.llm_utils.config._load_llm_models_config",
        return_value=_fake_models_cfg_without_reasoning(),
    ):
        with patch(
            "ocapi.llm_utils.config._provider_api_config",
            return_value=("piag-key", "https://piag.example"),
        ):
            model = config_model_llm()

    assert model.reasoning_model is None


def test_env_timeout_overrides_resilience_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_TIMEOUT_SECONDS replaces timeout_seconds from llm_resilience.json."""
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "600")
    with patch(
        "ocapi.llm_utils.config._read_json_config",
        return_value={"timeout_seconds": 300, "fallback_enabled": False},
    ):
        cfg = _load_llm_resilience_config()

    assert cfg["timeout_seconds"] == 600
    assert cfg["fallback_enabled"] is False


def test_resilience_timeout_from_json_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without LLM_TIMEOUT_SECONDS, timeout_seconds comes from the JSON."""
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    with patch(
        "ocapi.llm_utils.config._read_json_config",
        return_value={"timeout_seconds": 300},
    ):
        cfg = _load_llm_resilience_config()

    assert cfg["timeout_seconds"] == 300


@pytest.mark.parametrize("bad_value", ["abc", "0", "-5", "1.5"])
def test_invalid_env_timeout_is_ignored_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, bad_value: str
) -> None:
    """An invalid LLM_TIMEOUT_SECONDS keeps the JSON value and logs a warning."""
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", bad_value)
    with patch(
        "ocapi.llm_utils.config._read_json_config",
        return_value={"timeout_seconds": 300},
    ):
        with caplog.at_level("WARNING"):
            cfg = _load_llm_resilience_config()

    assert cfg["timeout_seconds"] == 300
    assert any("LLM_TIMEOUT_SECONDS" in msg for msg in caplog.messages)


def test_env_timeout_does_not_mutate_default_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Overriding the timeout must not leak into the module-level default dict."""
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "999")
    with patch("ocapi.llm_utils.config._RESILIENCE_CONFIG_PATH", Path("/nonexistent.json")):
        cfg = _load_llm_resilience_config()

    assert cfg["timeout_seconds"] == 999
    assert _DEFAULT_LLM_RESILIENCE_CONFIG["timeout_seconds"] == 45
