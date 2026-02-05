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
import re
import textwrap
from typing import Any, Tuple

import requests  # type: ignore[import-untyped]

from ocapi.config import settings
from ocapi.types import OperationType


def config_model_llm(modele: str) -> Tuple[str, str | None, str]:
    """
    Retourne (MODEL_NAME, API_KEY, API_URL) selon le nom logique du modèle.
    """
    if modele == "GPT5":
        return (
            "gpt-5",
            settings.llm.openai_api_key,
            str(settings.llm.openai_api_url),
        )
    if modele == "GPT5mini":
        return (
            "gpt-5-mini",
            settings.llm.openai_api_key,
            str(settings.llm.openai_api_url),
        )
    return (
        "mte-api-piag-mistral-medium-latest",
        settings.llm.piag_api_key,
        str(settings.llm.piag_api_url),
    )


def call_llm_api(cfg: Tuple[str, str | None, str], prompt: str) -> str:
    """
    Appelle le modèle LLM avec le prompt donné et retourne la réponse au format JSON.
    cfg : tuple (MODEL_NAME, API_KEY, API_URL)
    prompt : texte du prompt à envoyer au modèle
    """
    MODEL_NAME, API_KEY, API_URL = cfg
    # En-têtes HTTP requis pour l'authentification et le format des données
    HEADERS = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # payload minimal compatible Mistral / GPT
    if MODEL_NAME == "mte-api-piag-mistral-medium-latest":
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "n": 1,
        }
    else:
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "verbosity": "low",
            "reasoning_effort": "minimal",
            "n": 1,
        }

    # Appel avec gestion des erreurs HTTP
    r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=(40, 120))
    r.raise_for_status()

    # Extraction du contenu de la réponse du modèle
    data: Any = r.json()
    raw = str(data["choices"][0]["message"]["content"])

    return raw


def parse_llm_json_list_response(raw: str) -> list[dict[str, Any]]:
    """
    Parse la réponse brute du LLM pour extraire une liste au format JSON
    """
    # Chercher le premier grand tableau JSON dans la réponse
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        return []

    # Parser le tableau JSON
    lst: Any = json.loads(m.group())
    # S'assurer qu'on renvoie bien une liste
    return lst if isinstance(lst, list) else []


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
