import json
import os
import re
from typing import Tuple
from dotenv import load_dotenv
import requests

from ocapi.types import OperationType

load_dotenv()

def config_model_llm(modele: str) -> Tuple[str, str, str]:
    """
    Retourne (MODEL_NAME, API_KEY, API_URL) selon le nom logique du modèle.
    """
    if modele == "GPT5":
        return (
            "gpt-5",
            os.getenv("OPENAI_API_KEY"),
            os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"),
        )
    if modele == "GPT5mini":
        return (
            "gpt-5-mini",
            os.getenv("OPENAI_API_KEY"),
            os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"),
        )
    return (
        "mte-api-piag-mistral-medium-latest",
        os.getenv("PIAG_API_KEY"),
        os.getenv("PIAG_API_URL", "https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions"),
    )


def call_llm_api(cfg, prompt: str) -> dict:
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
    # Timeout augmenté : (connexion=60s, lecture=300s)
    r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=(60, 300))
    r.raise_for_status()

    # Extraction du contenu de la réponse du modèle
    data = r.json()
    raw = data["choices"][0]["message"]["content"]

    return raw


def parse_llm_json_list_response(raw: str) -> list:
    """
    Parse la réponse brute du LLM pour extraire une liste au format JSON
    """
    # Chercher le premier grand tableau JSON dans la réponse
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        return []

    # Parser le tableau JSON
    lst = json.loads(m.group())
    # S'assurer qu'on renvoie bien une liste
    return lst if isinstance(lst, list) else []


def query_llm_for_subtarget(typemodif: OperationType, target_content: str, sub_target: str) -> dict:
    """
    Interroge un LLM pour déterminer le sub-target à partir d'un texte descriptif et d'un contexte HTML.
    Retourne un dictionnaire avec les informations du sub-target.
    (REPLACE)
    """
    prompt_REPLACE = f"""
    Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant : 
    
    {target_content}
    
    Supprime le contenu décrit de la manière suivante : 
    
    {sub_target}
    
    et remplace le par le placeholder <NEWCONTENT>.
    """

    prompt_ADD = f"""
    Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant : 
    
    {target_content}
    
    A l'endroit décrit de la manière suivante : 
    
    {sub_target}
    
    insère le placeholder <NEWCONTENT>.
    """

    prompt_REMOVE = f"""
    Vous êtes un assistant spécialisé dans l'analyse juridique. Dans le texte suivant : 
    
    {target_content}
    
    Supprime le segment décrit de la manière suivante : 
    
    {sub_target}
    """

    if typemodif == OperationType.REPLACE:
       return prompt_REPLACE
    elif typemodif == OperationType.ADD:
       return prompt_ADD
    elif typemodif == OperationType.REMOVE:
       return prompt_REMOVE