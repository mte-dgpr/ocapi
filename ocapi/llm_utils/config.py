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
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ocapi.config import settings
from ocapi.exceptions import LLMConfigError
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.utils import to_bool_or_default, to_int_or_default

_LOGGER = get_logger(__name__)

_MODELS_CONFIG_PATH = settings.paths.project_root / "config" / "llm_models.json"
_RESILIENCE_CONFIG_PATH = settings.paths.project_root / "config" / "llm_resilience.json"
_RATE_LIMIT_CONFIG_PATH = settings.paths.project_root / "config" / "llm_rate_limit.json"

_DEFAULT_LLM_MODELS_CONFIG: dict[str, Any] = {
    "primary_model_key": "piag_mistral_medium",
    "secondary_model_key": None,
    "models": {
        "piag_mistral_medium": {
            "provider": "mte-piag",
            "model_id": "mte-api-piag-mistral-medium-latest",
        },
        "openai_gpt4o": {
            "provider": "openai",
            "model_id": "gpt-4o",
        },
        "openai_gpt5": {
            "provider": "openai",
            "model_id": "gpt-5",
            "reasoning_model": True,
        },
        "openai_gpt5mini": {
            "provider": "openai",
            "model_id": "gpt-5-mini",
            "reasoning_model": True,
        },
    },
}
_DEFAULT_PRIMARY_MODEL = _DEFAULT_LLM_MODELS_CONFIG["primary_model_key"]

_DEFAULT_LLM_RESILIENCE_CONFIG: dict[str, Any] = {
    "fallback_enabled": False,
    "timeout_seconds": 45,
    "retry": {
        "primary": {
            "max_attempts": 5,
            "base_delay_ms": 300,
            "max_delay_ms": 5000,
            "jitter": True,
        },
        "secondary": {
            "max_attempts": 2,
            "base_delay_ms": 300,
            "max_delay_ms": 3000,
            "jitter": True,
        },
    },
    "confidence_score": {
        "enabled": False,
        "min_threshold": 70,
        "action_below_threshold": "pass",
    },
}

_DEFAULT_LLM_RATE_LIMIT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "min_interval_ms": 3000,
}


@dataclass(frozen=True)
class ResolvedLLMModel:
    model_key: str
    provider: str
    model_name: str
    api_key: str | None
    api_url: str
    reasoning_model: bool | None = None
    temperature: float | None = 0.0


def _read_json_config(path: Path, default_value: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        _LOGGER.warning(f"Config file not found ({path}). Using default configuration.")
        return default_value

    try:
        with path.open(encoding="utf-8") as handle:
            payload: Any = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        _LOGGER.warning(f"Invalid JSON config ({path}): {exc}. Falling back to default.")
        return default_value

    if not isinstance(payload, dict):
        _LOGGER.warning(f"Invalid JSON config ({path}): object expected. Falling back to default.")
        return default_value

    return payload


def _load_llm_models_config() -> dict[str, Any]:
    return _read_json_config(_MODELS_CONFIG_PATH, _DEFAULT_LLM_MODELS_CONFIG)


def _load_llm_resilience_config() -> dict[str, Any]:
    return _read_json_config(_RESILIENCE_CONFIG_PATH, _DEFAULT_LLM_RESILIENCE_CONFIG)


def _load_llm_rate_limit_config() -> dict[str, Any]:
    return _read_json_config(_RATE_LIMIT_CONFIG_PATH, _DEFAULT_LLM_RATE_LIMIT_CONFIG)


def _primary_secondary_keys(models_cfg: dict[str, Any]) -> tuple[str, str | None]:
    primary = models_cfg.get("primary_model_key")
    secondary = models_cfg.get("secondary_model_key")
    models = models_cfg.get("models", {})
    if not isinstance(models, dict) or not models:
        return str(_DEFAULT_PRIMARY_MODEL), None
    if not isinstance(primary, str) or primary not in models:
        primary = next(iter(models.keys()))
    if not isinstance(secondary, str) or secondary not in models:
        secondary = None

    env_primary = os.environ.get("LLM_PRIMARY_MODEL_KEY", "").strip()
    if env_primary:
        if env_primary in models:
            primary = env_primary
        else:
            _LOGGER.warning(
                "LLM_PRIMARY_MODEL_KEY=%r not found in llm_models.json; keeping %r.",
                env_primary,
                primary,
            )

    env_secondary = os.environ.get("LLM_SECONDARY_MODEL_KEY", "").strip()
    if env_secondary:
        if env_secondary in models:
            secondary = env_secondary
        else:
            _LOGGER.warning(
                "LLM_SECONDARY_MODEL_KEY=%r not found in llm_models.json; keeping %r.",
                env_secondary,
                secondary,
            )

    return primary, secondary


def _resolve_model_key(model: str | None, models_cfg: dict[str, Any]) -> str:
    models = models_cfg.get("models", {})
    if not isinstance(models, dict) or not models:
        raise LLMConfigError("No LLM model available in the configuration.")

    primary_key, secondary_key = _primary_secondary_keys(models_cfg)

    if model is None or model.strip() == "" or model == "primary":
        return primary_key
    if model == "secondary":
        if secondary_key is None:
            raise LLMConfigError("No secondary model configured.")
        return secondary_key
    if model in models:
        return model

    legacy_aliases = {
        "GPT5": "openai_gpt5",
        "GPT5mini": "openai_gpt5mini",
        "mte-api-piag-mistral-medium-latest": "piag_mistral_medium",
    }
    if model in legacy_aliases and legacy_aliases[model] in models:
        return legacy_aliases[model]

    for model_key, model_cfg in models.items():
        if (
            isinstance(model_key, str)
            and isinstance(model_cfg, dict)
            and model_cfg.get("model_id") == model
        ):
            return model_key

    raise LLMConfigError(f"Unknown LLM model: {model}")


def _provider_api_config(provider: str) -> tuple[str | None, str]:
    if provider == "mte-piag":
        return settings.llm.piag_api_key, str(settings.llm.piag_api_url)
    if provider == "mistral":
        return settings.llm.mistral_api_key, str(settings.llm.mistral_api_url)
    if provider == "openai":
        return settings.llm.openai_api_key, str(settings.llm.openai_api_url)
    if provider == "anthropic":
        return settings.llm.anthropic_api_key, str(settings.llm.anthropic_api_url)
    if provider == "google":
        return settings.llm.google_api_key, str(settings.llm.google_api_url)
    raise LLMConfigError(f"Unsupported LLM provider: {provider}")


def config_model_llm(model: str | None = None) -> ResolvedLLMModel:
    """Resolve a LLM model configuration from the centralised JSON config.

    Parameters
    ----------
    model : str | None
        - ``None`` / ``"primary"``: configured primary model
        - ``"secondary"``: configured secondary model
        - model_key: explicit key in ``llm_models.json``
        - legacy aliases (GPT5, GPT5mini, old Mistral model_id)
    """
    models_cfg = _load_llm_models_config()
    model_key = _resolve_model_key(model, models_cfg)
    models = models_cfg.get("models", {})
    model_cfg = models.get(model_key, {})
    if not isinstance(model_cfg, dict):
        raise LLMConfigError(f"Invalid configuration for model: {model_key}")

    provider = model_cfg.get("provider")
    model_name = model_cfg.get("model_id")
    if not isinstance(provider, str) or not isinstance(model_name, str):
        raise LLMConfigError(f"Invalid configuration for model: {model_key}")

    reasoning_model = model_cfg.get("reasoning_model")
    raw_temperature = model_cfg.get("temperature", 0.0)
    temperature = float(raw_temperature) if raw_temperature is not None else None

    api_key, api_url = _provider_api_config(provider)
    return ResolvedLLMModel(
        model_key=model_key,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        api_url=api_url,
        reasoning_model=reasoning_model if isinstance(reasoning_model, bool) else None,
        temperature=temperature,
    )


@dataclass(frozen=True)
class ConfidenceScoreConfig:
    """Validated confidence-score filtering settings from ``llm_resilience.json``."""

    enabled: bool
    min_threshold: int  # 0-100 inclusive
    action_below_threshold: str  # "pass" | "retry"


def get_confidence_score_config() -> ConfidenceScoreConfig:
    """Return the validated confidence-score configuration from ``llm_resilience.json``.

    Attributes
    ----------
    enabled : bool
        Whether confidence-score filtering is active.
    min_threshold : int
        Operations whose ``confidence_score < min_threshold`` are acted on (0-100).
    action_below_threshold : str
        ``"pass"`` to skip the low-confidence operation immediately;
        ``"retry"`` to re-run the LLM call for the block first, then skip if still low.
    """
    resilience_cfg = _load_llm_resilience_config()
    raw = resilience_cfg.get("confidence_score", {})
    if not isinstance(raw, dict):
        raw = {}

    defaults = _DEFAULT_LLM_RESILIENCE_CONFIG["confidence_score"]

    enabled = to_bool_or_default(raw.get("enabled"), defaults["enabled"])
    raw_threshold = raw.get("min_threshold", defaults["min_threshold"])
    min_threshold = max(0, min(100, to_int_or_default(raw_threshold, defaults["min_threshold"], 0)))
    action = raw.get("action_below_threshold", defaults["action_below_threshold"])
    if not isinstance(action, str) or action not in ("pass", "retry"):
        action = defaults["action_below_threshold"]

    return ConfidenceScoreConfig(
        enabled=enabled,
        min_threshold=min_threshold,
        action_below_threshold=action,
    )
