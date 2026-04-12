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
import json
import random
import re
import textwrap
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests  # type: ignore[import-untyped]

from ocapi.config import settings
from ocapi.exceptions import LLMConfigError, LLMNetworkError, LLMResponseError
from ocapi.types import OperationType
from ocapi.utils.logging_utils import get_logger

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

_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_LAST_CALL_MONOTONIC: float | None = None


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


def _to_int_or_default(value: Any, default: int, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def _to_bool_or_default(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


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
    raise LLMConfigError(f"Unsupported LLM provider: {provider}")


def _build_payload(model: ResolvedLLMModel, prompt: str) -> dict[str, Any]:
    if model.provider == "mte-piag":
        return {
            "model": model.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "n": 1,
        }

    if model.provider == "mistral":
        return {
            "model": model.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "n": 1,
        }

    if model.provider == "openai":
        payload: dict[str, Any] = {
            "model": model.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "n": 1,
        }
        if model.reasoning_model:
            payload["reasoning_effort"] = "high"
            payload["verbosity"] = 0
        if model.temperature is not None:
            payload["temperature"] = model.temperature
        return payload

    raise LLMConfigError(f"Unsupported LLM provider: {model.provider}")


def _make_headers(api_key: str | None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _is_retryable_http_error(error: requests.exceptions.RequestException) -> bool:
    if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(error, requests.exceptions.HTTPError):
        status_code = error.response.status_code if error.response is not None else None
        return status_code == 429 or (status_code is not None and 500 <= status_code <= 599)
    return isinstance(error, requests.exceptions.RequestException)


def _extract_retry_after(exc: requests.exceptions.RequestException) -> float | None:
    """Return the Retry-After delay (in seconds) from a 429 response, if present."""
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    header = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
    if header is None:
        return None
    try:
        return float(header)
    except (ValueError, TypeError):
        return None


def _retry_delay_seconds(attempt: int, strategy: dict[str, Any]) -> float:
    base_ms = _to_int_or_default(strategy.get("base_delay_ms"), default=300, minimum=1)
    max_ms = _to_int_or_default(strategy.get("max_delay_ms"), default=5000, minimum=base_ms)
    use_jitter = _to_bool_or_default(strategy.get("jitter"), default=True)

    raw_delay_ms = min(base_ms * (2 ** (attempt - 1)), max_ms)
    delay_seconds = float(raw_delay_ms) / 1000.0
    if use_jitter:
        delay_seconds *= random.uniform(0.8, 1.2)
    return delay_seconds if delay_seconds >= 0.0 else 0.0


def _apply_rate_limit(rate_limit_cfg: dict[str, Any]) -> None:
    enabled = _to_bool_or_default(rate_limit_cfg.get("enabled"), default=False)
    min_interval_ms = _to_int_or_default(
        rate_limit_cfg.get("min_interval_ms"), default=0, minimum=0
    )
    if not enabled or min_interval_ms <= 0:
        return

    min_interval_seconds = min_interval_ms / 1000
    sleep_seconds = 0.0
    global _RATE_LIMIT_LAST_CALL_MONOTONIC

    with _RATE_LIMIT_LOCK:
        now = time.monotonic()
        if _RATE_LIMIT_LAST_CALL_MONOTONIC is not None:
            elapsed = now - _RATE_LIMIT_LAST_CALL_MONOTONIC
            if elapsed < min_interval_seconds:
                sleep_seconds = min_interval_seconds - elapsed
        if sleep_seconds == 0.0:
            _RATE_LIMIT_LAST_CALL_MONOTONIC = now

    if sleep_seconds > 0.0:
        _LOGGER.debug(f"Rate limiting active: waiting {sleep_seconds:.3f}s before LLM call.")
        time.sleep(sleep_seconds)
        with _RATE_LIMIT_LOCK:
            _RATE_LIMIT_LAST_CALL_MONOTONIC = time.monotonic()


def _execute_model_call(
    model: ResolvedLLMModel,
    prompt: str,
    timeout_seconds: int,
    strategy: dict[str, Any],
    rate_limit_cfg: dict[str, Any],
) -> str:
    max_attempts = _to_int_or_default(strategy.get("max_attempts"), default=1, minimum=1)
    payload = _build_payload(model, prompt)
    headers = _make_headers(model.api_key)

    for attempt in range(1, max_attempts + 1):
        try:
            _apply_rate_limit(rate_limit_cfg)
            response = requests.post(
                model.api_url,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            data: Any = response.json()
            try:
                return str(data["choices"][0]["message"]["content"])
            except (TypeError, KeyError, IndexError) as exc:
                _LOGGER.error(
                    f"Invalid LLM API response ({model.model_name}): "
                    f"choices/message/content key not found. Raw response: {data}"
                )
                raise LLMResponseError("Invalid LLM response format") from exc
        except requests.exceptions.RequestException as exc:
            retryable = _is_retryable_http_error(exc)
            is_last_attempt = attempt >= max_attempts
            if not retryable or is_last_attempt:
                _LOGGER.error(
                    f"LLM API call failed ({model.model_name}) "
                    f"attempt {attempt}/{max_attempts}: {exc}"
                )
                raise LLMNetworkError(f"LLM API call failed ({model.model_name}): {exc}") from exc

            delay_seconds = _retry_delay_seconds(attempt, strategy)
            retry_after = _extract_retry_after(exc)
            if retry_after is not None and retry_after > delay_seconds:
                delay_seconds = retry_after
            _LOGGER.warning(
                f"Retrying LLM API call ({model.model_name}) attempt {attempt}/{max_attempts} "
                f"in {delay_seconds:.2f}s: {exc}"
            )
            time.sleep(delay_seconds)

    raise LLMNetworkError("Retry loop ended without result.")


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


def call_llm_api(cfg: ResolvedLLMModel, prompt: str) -> str:
    """Call the LLM with the given prompt and return the response.

    Applies the primary retry + secondary fallback strategy from ``llm_resilience.json``.
    """
    resilience_cfg = _load_llm_resilience_config()
    rate_limit_cfg = _load_llm_rate_limit_config()
    retry_cfg = resilience_cfg.get("retry", {})
    timeout_seconds = _to_int_or_default(
        resilience_cfg.get("timeout_seconds"), default=45, minimum=1
    )
    primary_retry = (
        retry_cfg.get("primary", {})
        if isinstance(retry_cfg, dict) and isinstance(retry_cfg.get("primary", {}), dict)
        else {}
    )
    secondary_retry = (
        retry_cfg.get("secondary", {})
        if isinstance(retry_cfg, dict) and isinstance(retry_cfg.get("secondary", {}), dict)
        else {}
    )
    primary_retry_max = _to_int_or_default(primary_retry.get("max_attempts"), default=1, minimum=1)
    secondary_retry_max = _to_int_or_default(
        secondary_retry.get("max_attempts"), default=1, minimum=1
    )
    fallback_enabled = _to_bool_or_default(resilience_cfg.get("fallback_enabled"), default=False)
    rate_limit_enabled = _to_bool_or_default(rate_limit_cfg.get("enabled"), default=False)
    rate_limit_min_interval_ms = _to_int_or_default(
        rate_limit_cfg.get("min_interval_ms"), default=0, minimum=0
    )

    _LOGGER.debug(
        "LLM strategy: "
        f"timeout={timeout_seconds}s, "
        f"retry_primary_max={primary_retry_max}, "
        f"retry_secondary_max={secondary_retry_max}, "
        f"fallback_enabled={fallback_enabled}, "
        f"rate_limit_enabled={rate_limit_enabled}, "
        f"rate_limit_min_interval_ms={rate_limit_min_interval_ms}"
    )

    _LOGGER.debug(f"Primary LLM API call: {cfg.model_name}")
    try:
        return _execute_model_call(cfg, prompt, timeout_seconds, primary_retry, rate_limit_cfg)
    except LLMNetworkError as primary_error:
        if not fallback_enabled:
            _LOGGER.warning(
                f"Fallback disabled: final primary failure on {cfg.model_name}: {primary_error}"
            )
            raise

        models_cfg = _load_llm_models_config()
        _primary_key, secondary_key = _primary_secondary_keys(models_cfg)
        if secondary_key is None:
            _LOGGER.warning(
                "Fallback enabled but no valid secondary_model_key is configured. "
                f"Primary error: {primary_error}"
            )
            raise

        fallback_cfg = config_model_llm("secondary")
        if fallback_cfg.model_key == cfg.model_key:
            _LOGGER.warning(
                f"Fallback impossible: secondary model ({fallback_cfg.model_key}) is identical "
                f"to primary ({cfg.model_key}). Primary error: {primary_error}"
            )
            raise

        _LOGGER.warning(
            f"Fallback activated: switching from {cfg.model_name} to {fallback_cfg.model_name} "
            f"after primary error: {primary_error}"
        )
        return _execute_model_call(
            fallback_cfg, prompt, timeout_seconds, secondary_retry, rate_limit_cfg
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

    enabled = _to_bool_or_default(raw.get("enabled"), defaults["enabled"])
    raw_threshold = raw.get("min_threshold", defaults["min_threshold"])
    min_threshold = max(
        0, min(100, _to_int_or_default(raw_threshold, defaults["min_threshold"], 0))
    )
    action = raw.get("action_below_threshold", defaults["action_below_threshold"])
    if not isinstance(action, str) or action not in ("pass", "retry"):
        action = defaults["action_below_threshold"]

    return ConfidenceScoreConfig(
        enabled=enabled,
        min_threshold=min_threshold,
        action_below_threshold=action,
    )


def parse_llm_json_list_response(raw: str) -> list[dict[str, Any]]:
    """Parse the raw LLM response to extract a JSON list.

    Note: Returns an empty list on parsing errors. Errors are logged but not
    retried — retries must be handled at the API call level, not the parsing level.
    """
    # Find the first JSON array in the response
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        _LOGGER.warning(
            f"No JSON array found in LLM response. " f"Raw response (first 200 chars): {raw[:200]}"
        )
        return []

    # Parse the JSON array
    try:
        lst: Any = json.loads(m.group())
        # Ensure we return a list
        if not isinstance(lst, list):
            _LOGGER.warning(
                f"Parsed JSON is not a list but a {type(lst).__name__}. " f"Returning empty list."
            )
            return []
        return lst
    except json.JSONDecodeError as e:
        _LOGGER.error(
            f"LLM JSON parsing error: {e}. " f"JSON content (first 200 chars): {m.group()[:200]}"
        )
        return []


def query_llm_for_subtarget(
    operation_type: OperationType,
    target_content: str,
    sub_target: str,
    *,
    target_article_id: str | None = None,
    operand: str | None = None,
    source_content: str | None = None,
) -> str:
    """Build a prompt for LLM-assisted consolidation (locate sub-target in HTML).

    When ``source_content`` is provided, it is the HTML of the *source* article
    (arrêté modifiant) that motivates the operation; it helps disambiguate
    complex cases (e.g. table rows, nested structures).

    Returns a prompt string for a REPLACE, REMOVE or ADD operation.
    The prompt asks the LLM to return the complete modified HTML directly
    (no placeholder).
    """
    source_block = ""
    if source_content is not None and source_content.strip():
        source_block = textwrap.dedent(
            f"""
            Contexte — article source (arrêté modifiant), d'où provient la modification :

            {source_content}

            ---

            """
        ).strip()
        source_block = source_block + "\n\n"

    article_label = f" (article {target_article_id})" if target_article_id else ""

    operand_block = ""
    if operand is not None and operand.strip():
        operand_block = f"\n\nNouveau contenu à intégrer :\n\n{operand}"

    preamble = (
        f"{source_block}Vous aidez à consolider des arrêtés ICPE."
        f" Vous recevez l'article **cible**{article_label} en HTML."
    )
    output_instruction = (
        "Renvoyez UNIQUEMENT le HTML modifié complet de l'article,"
        " sans explication ni balisage markdown."
    )

    prompt_REPLACE = textwrap.dedent(
        f"""
        {preamble}
        Le sous-emplacement à remplacer est décrit en langage naturel.

        Tâche : localisez précisément le segment décrit et remplacez-le
        par le nouveau contenu fourni.
        {output_instruction}

        Article cible (HTML) :

        {target_content}

        Description du sous-emplacement à remplacer :

        {sub_target}{operand_block}
        """
    ).strip()

    prompt_ADD = textwrap.dedent(
        f"""
        {preamble}
        L'insertion doit se faire à l'endroit décrit.

        Tâche : insérez le nouveau contenu à l'emplacement indiqué.
        {output_instruction}

        Article cible (HTML) :

        {target_content}

        Description de l'emplacement d'insertion :

        {sub_target}{operand_block}
        """
    ).strip()

    prompt_REMOVE = textwrap.dedent(
        f"""
        {preamble}
        Le segment à supprimer est décrit en langage naturel.

        Tâche : supprimez le segment décrit.
        {output_instruction}

        Article cible (HTML) :

        {target_content}

        Description du segment à supprimer :

        {sub_target}
        """
    ).strip()

    if operation_type == OperationType.REPLACE:
        return prompt_REPLACE
    elif operation_type == OperationType.ADD:
        return prompt_ADD
    elif operation_type == OperationType.REMOVE:
        return prompt_REMOVE
