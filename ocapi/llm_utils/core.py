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
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

from ocapi.exceptions import LLMConfigError, LLMNetworkError, LLMResponseError
from ocapi.llm_utils.config import (
    ResolvedLLMModel,
    _load_llm_models_config,
    _load_llm_rate_limit_config,
    _load_llm_resilience_config,
    _primary_secondary_keys,
    config_model_llm,
)
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.utils import to_bool_or_default, to_int_or_default

_LOGGER = get_logger(__name__)

_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_LAST_CALL_MONOTONIC: float | None = None


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


_accumulated_usage = TokenUsage()


def reset_accumulated_usage() -> None:
    _accumulated_usage.prompt_tokens = 0
    _accumulated_usage.completion_tokens = 0


def get_accumulated_usage() -> TokenUsage:
    return _accumulated_usage


def _extract_content(model_provider: str, data: Any) -> str:
    """Extract the text content from a raw LLM API response dict.

    Raises LLMResponseError if the expected fields are missing.
    """
    try:
        if model_provider == "anthropic":
            return str(data["content"][0]["text"])
        return str(data["choices"][0]["message"]["content"])
    except (TypeError, KeyError, IndexError) as exc:
        raise LLMResponseError("Invalid LLM response format") from exc


def _accumulate_usage(model_provider: str, data: Any) -> None:
    """Add token counts from a successful API response to the global accumulator."""
    try:
        usage = data.get("usage") or {}
        if model_provider == "anthropic":
            prompt = int(usage.get("input_tokens") or 0)
            completion = int(usage.get("output_tokens") or 0)
        else:
            prompt = int(usage.get("prompt_tokens") or 0)
            completion = int(usage.get("completion_tokens") or 0)
        _accumulated_usage.prompt_tokens += prompt
        _accumulated_usage.completion_tokens += completion
    except (TypeError, ValueError, AttributeError):
        _LOGGER.debug("Could not extract token usage from LLM response.")


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
            payload["verbosity"] = "low"
        elif model.temperature is not None:
            payload["temperature"] = model.temperature
        return payload

    if model.provider == "anthropic":
        return {
            "model": model.model_name,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": model.temperature if model.temperature is not None else 0,
        }

    if model.provider == "google":
        return {
            "model": model.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "n": 1,
        }

    raise LLMConfigError(f"Unsupported LLM provider: {model.provider}")


def _make_headers(api_key: str | None, provider: str = "") -> dict[str, str]:
    if provider == "anthropic":
        return {
            "x-api-key": api_key or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
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
    base_ms = to_int_or_default(strategy.get("base_delay_ms"), default=300, minimum=1)
    max_ms = to_int_or_default(strategy.get("max_delay_ms"), default=5000, minimum=base_ms)
    use_jitter = to_bool_or_default(strategy.get("jitter"), default=True)

    raw_delay_ms = min(base_ms * (2 ** (attempt - 1)), max_ms)
    delay_seconds = float(raw_delay_ms) / 1000.0
    if use_jitter:
        delay_seconds *= random.uniform(0.8, 1.2)
    return delay_seconds if delay_seconds >= 0.0 else 0.0


def _apply_rate_limit(rate_limit_cfg: dict[str, Any]) -> None:
    enabled = to_bool_or_default(rate_limit_cfg.get("enabled"), default=False)
    min_interval_ms = to_int_or_default(rate_limit_cfg.get("min_interval_ms"), default=0, minimum=0)
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
    max_attempts = to_int_or_default(strategy.get("max_attempts"), default=1, minimum=1)
    payload = _build_payload(model, prompt)
    headers = _make_headers(model.api_key, model.provider)

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
                content = _extract_content(model.provider, data)
            except LLMResponseError:
                _LOGGER.error(
                    f"Invalid LLM API response ({model.model_name}): "
                    f"unexpected response format. Raw response: {data}"
                )
                raise
            _accumulate_usage(model.provider, data)
            return content
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


def call_llm_api(cfg: ResolvedLLMModel, prompt: str) -> str:
    """Call the LLM with the given prompt and return the response.

    Applies the primary retry + secondary fallback strategy from ``llm_resilience.json``.
    """
    resilience_cfg = _load_llm_resilience_config()
    rate_limit_cfg = _load_llm_rate_limit_config()
    retry_cfg = resilience_cfg.get("retry", {})
    timeout_seconds = to_int_or_default(
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
    primary_retry_max = to_int_or_default(primary_retry.get("max_attempts"), default=1, minimum=1)
    secondary_retry_max = to_int_or_default(
        secondary_retry.get("max_attempts"), default=1, minimum=1
    )
    fallback_enabled = to_bool_or_default(resilience_cfg.get("fallback_enabled"), default=False)
    rate_limit_enabled = to_bool_or_default(rate_limit_cfg.get("enabled"), default=False)
    rate_limit_min_interval_ms = to_int_or_default(
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
