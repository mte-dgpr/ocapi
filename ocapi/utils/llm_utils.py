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
from ocapi.types import OperationType
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


_MODELS_CONFIG_PATH = settings.paths.project_root / "config" / "llm_models.json"
_RESILIENCE_CONFIG_PATH = settings.paths.project_root / "config" / "llm_resilience.json"
_RATE_LIMIT_CONFIG_PATH = settings.paths.project_root / "config" / "llm_rate_limit.json"

_DEFAULT_LLM_MODELS_CONFIG: dict[str, Any] = {
    "primary_model_key": "mistral_medium",
    "secondary_model_key": None,
    "models": {
        "mistral_medium": {
            "provider": "mistral",
            "model_id": "mte-api-piag-mistral-medium-latest",
        },
        "openai_gpt5": {
            "provider": "openai",
            "model_id": "gpt-5",
        },
        "openai_gpt5mini": {
            "provider": "openai",
            "model_id": "gpt-5-mini",
        },
    },
}

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
}

_DEFAULT_LLM_RATE_LIMIT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "min_interval_ms": 0,
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


def _read_json_config(path: Path, default_value: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default_value

    try:
        with path.open(encoding="utf-8") as handle:
            payload: Any = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        _LOGGER.warning(f"Config JSON invalide ({path}): {exc}. Fallback sur défaut.")
        return default_value

    if not isinstance(payload, dict):
        _LOGGER.warning(f"Config JSON invalide ({path}): objet attendu. Fallback sur défaut.")
        return default_value

    return payload


def _load_llm_models_config() -> dict[str, Any]:
    return _read_json_config(_MODELS_CONFIG_PATH, _DEFAULT_LLM_MODELS_CONFIG)


def _load_llm_resilience_config() -> dict[str, Any]:
    return _read_json_config(_RESILIENCE_CONFIG_PATH, _DEFAULT_LLM_RESILIENCE_CONFIG)


def _load_llm_rate_limit_config() -> dict[str, Any]:
    return _read_json_config(_RATE_LIMIT_CONFIG_PATH, _DEFAULT_LLM_RATE_LIMIT_CONFIG)


def _to_int(value: Any, default: int, minimum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _primary_secondary_keys(models_cfg: dict[str, Any]) -> tuple[str, str | None]:
    primary = models_cfg.get("primary_model_key")
    secondary = models_cfg.get("secondary_model_key")
    models = models_cfg.get("models", {})
    if not isinstance(models, dict) or not models:
        return "mistral_medium", None
    if not isinstance(primary, str) or primary not in models:
        primary = next(iter(models.keys()))
    if not isinstance(secondary, str) or secondary not in models:
        secondary = None
    return primary, secondary


def _resolve_model_key(modele: str | None, models_cfg: dict[str, Any]) -> str:
    models = models_cfg.get("models", {})
    if not isinstance(models, dict) or not models:
        raise ValueError("Aucun modèle LLM disponible dans la configuration.")

    primary_key, secondary_key = _primary_secondary_keys(models_cfg)

    if modele is None or modele.strip() == "" or modele == "primary":
        return primary_key
    if modele == "secondary":
        if secondary_key is None:
            raise ValueError("Aucun modèle secondaire configuré.")
        return secondary_key
    if modele in models:
        return modele

    legacy_aliases = {
        "GPT5": "openai_gpt5",
        "GPT5mini": "openai_gpt5mini",
        "mte-api-piag-mistral-medium-latest": "mistral_medium",
    }
    if modele in legacy_aliases and legacy_aliases[modele] in models:
        return legacy_aliases[modele]

    for model_key, model_cfg in models.items():
        if isinstance(model_cfg, dict) and model_cfg.get("model_id") == modele:
            return model_key

    raise ValueError(f"Modèle LLM inconnu: {modele}")


def _provider_api_config(provider: str) -> tuple[str | None, str]:
    if provider == "mistral":
        return settings.llm.piag_api_key, str(settings.llm.piag_api_url)
    if provider == "openai":
        return settings.llm.openai_api_key, str(settings.llm.openai_api_url)
    raise ValueError(f"Provider LLM non supporté: {provider}")


def _build_payload(model: ResolvedLLMModel, prompt: str) -> dict[str, Any]:
    if model.provider == "mistral":
        return {
            "model": model.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "n": 1,
        }

    if model.provider == "openai":
        return {
            "model": model.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "verbosity": "low",
            "reasoning_effort": "minimal",
            "n": 1,
        }

    raise ValueError(f"Provider LLM non supporté: {model.provider}")


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


def _retry_delay_seconds(attempt: int, strategy: dict[str, Any]) -> float:
    base_ms = _to_int(strategy.get("base_delay_ms"), default=300, minimum=1)
    max_ms = _to_int(strategy.get("max_delay_ms"), default=5000, minimum=base_ms)
    use_jitter = _to_bool(strategy.get("jitter"), default=True)

    raw_delay_ms = min(base_ms * (2 ** (attempt - 1)), max_ms)
    delay_seconds = raw_delay_ms / 1000
    if use_jitter:
        delay_seconds *= random.uniform(0.8, 1.2)
    return max(delay_seconds, 0.0)


def _apply_rate_limit(rate_limit_cfg: dict[str, Any]) -> None:
    enabled = _to_bool(rate_limit_cfg.get("enabled"), default=False)
    min_interval_ms = _to_int(rate_limit_cfg.get("min_interval_ms"), default=0, minimum=0)
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
        _LOGGER.debug(f"Rate limiting actif: attente de {sleep_seconds:.3f}s avant appel LLM.")
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
    max_attempts = _to_int(strategy.get("max_attempts"), default=1, minimum=1)
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
            return str(data["choices"][0]["message"]["content"])
        except requests.exceptions.RequestException as exc:
            retryable = _is_retryable_http_error(exc)
            is_last_attempt = attempt >= max_attempts
            if not retryable or is_last_attempt:
                _LOGGER.error(
                    f"Échec appel API LLM ({model.model_name}) tentative {attempt}/{max_attempts}: {exc}"
                )
                raise

            delay_seconds = _retry_delay_seconds(attempt, strategy)
            _LOGGER.warning(
                f"Retry appel API LLM ({model.model_name}) tentative {attempt}/{max_attempts} "
                f"dans {delay_seconds:.2f}s: {exc}"
            )
            time.sleep(delay_seconds)

    raise RuntimeError("Boucle de retry terminée sans résultat.")


def config_model_llm(modele: str | None = None) -> ResolvedLLMModel:
    """
    Résout la configuration d'un modèle LLM à partir de la config JSON centralisée.

    Paramètre modele:
    - None / "primary": modèle principal configuré
    - "secondary": modèle secondaire configuré
    - model_key: clé explicite du modèle dans llm_models.json
    - compat: alias historiques (GPT5, GPT5mini, ancien model_id Mistral)
    """
    models_cfg = _load_llm_models_config()
    model_key = _resolve_model_key(modele, models_cfg)
    models = models_cfg.get("models", {})
    model_cfg = models.get(model_key, {})
    if not isinstance(model_cfg, dict):
        raise ValueError(f"Configuration invalide pour le modèle: {model_key}")

    provider = model_cfg.get("provider")
    model_name = model_cfg.get("model_id")
    if not isinstance(provider, str) or not isinstance(model_name, str):
        raise ValueError(f"Configuration invalide pour le modèle: {model_key}")

    api_key, api_url = _provider_api_config(provider)
    return ResolvedLLMModel(
        model_key=model_key,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        api_url=api_url,
    )


def call_llm_api(cfg: ResolvedLLMModel, prompt: str) -> str:
    """
    Appelle le modèle LLM avec le prompt donné et retourne la réponse au format JSON.
    Applique la stratégie de retry primaire + fallback secondaire selon llm_resilience.json.
    """
    resilience_cfg = _load_llm_resilience_config()
    rate_limit_cfg = _load_llm_rate_limit_config()
    retry_cfg = resilience_cfg.get("retry", {})
    timeout_seconds = _to_int(resilience_cfg.get("timeout_seconds"), default=45, minimum=1)
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

    _LOGGER.debug(f"Appel API LLM primaire: {cfg.model_name}")
    try:
        return _execute_model_call(cfg, prompt, timeout_seconds, primary_retry, rate_limit_cfg)
    except requests.exceptions.RequestException as primary_error:
        fallback_enabled = _to_bool(resilience_cfg.get("fallback_enabled"), default=False)
        if not fallback_enabled:
            raise

        models_cfg = _load_llm_models_config()
        _primary_key, secondary_key = _primary_secondary_keys(models_cfg)
        if secondary_key is None:
            raise

        fallback_cfg = config_model_llm("secondary")
        if fallback_cfg.model_key == cfg.model_key:
            raise

        _LOGGER.warning(
            f"Fallback activé: bascule de {cfg.model_name} vers {fallback_cfg.model_name} "
            f"après erreur primaire: {primary_error}"
        )
        return _execute_model_call(
            fallback_cfg, prompt, timeout_seconds, secondary_retry, rate_limit_cfg
        )


def parse_llm_json_list_response(raw: str) -> list[dict[str, Any]]:
    """
    Parse la réponse brute du LLM pour extraire une liste au format JSON.

    Note: Cette fonction retourne une liste vide en cas d'erreur de parsing.
    Les erreurs sont loguées mais ne font pas l'objet d'un retry car le retry
    doit être géré au niveau de l'appel API, pas au niveau du parsing.
    """
    # Chercher le premier grand tableau JSON dans la réponse
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        _LOGGER.warning(
            f"Aucun tableau JSON trouvé dans la réponse LLM. "
            f"Réponse brute (premiers 200 chars): {raw[:200]}"
        )
        return []

    # Parser le tableau JSON
    try:
        lst: Any = json.loads(m.group())
        # S'assurer qu'on renvoie bien une liste
        if not isinstance(lst, list):
            _LOGGER.warning(
                f"Le JSON parsé n'est pas une liste mais un {type(lst).__name__}. "
                f"Retour d'une liste vide."
            )
            return []
        return lst
    except json.JSONDecodeError as e:
        _LOGGER.error(
            f"Erreur parsing JSON LLM: {e}. "
            f"Contenu JSON (premiers 200 chars): {m.group()[:200]}"
        )
        return []


def query_llm_for_subtarget(typemodif: OperationType, target_content: str, sub_target: str) -> str:
    """
    Interroge un LLM pour déterminer le sub-target à partir d'un texte descriptif
    et d'un contexte HTML. Retourne un dictionnaire avec les informations
    du sub-target. (REPLACE)
    """
    prompt_REPLACE = textwrap.dedent(
        f"""
        Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant :

        {target_content}

        Supprime le contenu décrit de la manière suivante :

        {sub_target}

        et remplace le par le placeholder <NEWCONTENT>.
        """
    ).strip()

    prompt_ADD = textwrap.dedent(
        f"""
        Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant :

        {target_content}

        A l'endroit décrit de la manière suivante :

        {sub_target}

        insère le placeholder <NEWCONTENT>.
        """
    ).strip()

    prompt_REMOVE = textwrap.dedent(
        f"""
        Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant :

        {target_content}

        Supprime le segment décrit de la manière suivante :

        {sub_target}
        """
    ).strip()

    if typemodif == OperationType.REPLACE:
        return prompt_REPLACE
    elif typemodif == OperationType.ADD:
        return prompt_ADD
    elif typemodif == OperationType.REMOVE:
        return prompt_REMOVE
