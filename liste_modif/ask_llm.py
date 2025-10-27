import os, json, re, time, requests
from typing import Tuple
from dotenv import load_dotenv
import os
from pathlib import Path

# charger explicitement le .env à la racine du projet (un niveau au-dessus de liste_modif)
project_root = Path(__file__).resolve().parents[1]
env_path = project_root / ".env"
print("DEBUG: load .env from:", env_path)
if env_path.exists():
    load_dotenv(env_path)
else:
    # fallback : essayer find_dotenv si .env n'est pas à l'emplacement attendu
    from dotenv import find_dotenv
    p = find_dotenv()
    print("DEBUG: find_dotenv returned:", p)
    if p:
        load_dotenv(p)

def config_API(modele: str) -> Tuple[str,str,str]:
    """
    Permet de configurer interactivement quel modèle utiliser. 
    """
    if modele == "GPT5":
        return "gpt-5", os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
    if modele == "GPT5mini":
        return "gpt-5-mini", os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
    return "mte-api-piag-mistral-medium-latest", os.getenv("PIAG_API_KEY"), os.getenv("PIAG_API_URL", "https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions")

def ask_llm_for_operation(analysis_html: str, cfg) -> list:
    MODEL_NAME, API_KEY, API_URL = cfg

    prompt = f"""
    Voici un extrait de texte juridique (article ou extrait d'un arrêté préfectoral format HTML) :
    \"\"\"{analysis_html}\"\"\"
    L'objectif final du projet est de créer un permis consolidé (effectuer les opérations juridiques de différents arrêtés afin de construire un permis actualisé). Ta tâche est de détecter s'il y a une opération juridique dans ce texte, de type modification, ajout ou abrogation. 
    S'il y a une opération (modification d'un arrêté, abrogation, ajout dans un autre arrêté), alors les informations cherchées sont les suivantes :
    1. Type de modification (ADD, REPLACE, REMOVE)
    2. Arrêté ciblé (référence simple de l'arrêté, telle qu'elle est citée — par exemple, « arrêté préfectoral du JJ MM AAAA » — et pas des variantes type « modifié »).
    3. Article ciblé de l'arrêté modifié si précisé
    4. Partie ciblée de l'article si précisé (Pour DELETE / REPLACE, préciser "contenu entier" le cas échéant. Sinon, préciser la partie ciblée par la modification, style "la première phrase"/"le tableau"/"la dernière ligne du tableau".)
    5. Nouveau contenu à insérer dans l'arrêté ciblé (pour ADD/REPLACE). Cite moi le début EXACT et la fin EXACTE du nouveau contenu à ajouter. Ne recopie pas tout, je pourrai extraire moi-même. Je dois pouvoir extraire le contenu tel quel directement pour effectuer l'opération par la suite, donc le nouveau contenu ne doit pas contenir de contexte explicatif..
    6. Article source de la modification (juste référence de l'article, pas de titre/contenu explicatif. Juste "Article X.X", par exemple.)
    Pour chaque opération que tu trouves, retourne donc un objet avec les clés:
    {{
    "modification_type": "ADD|REPLACE|REMOVE", 
    "target_arrete": "arrêté concerné",
    "target_article": "article concerné de l'arrêté",
    "target_element": "élément précis de l'article si spécifié"
    "new_content_ref": {{
    "start_marker": string,   // 80 à 100 caractères EXACTS du début du nouveau contenu. pas plus. 
    "end_marker": string,     // 80 à 100 caractères EXACTS de la fin du nouveau contenu. pas plus. 
    }}
    "source_article" : "référence article source, sans le titre"
    }}
    Les markers DOIVENT correspondre exactement au HTML-LITE fourni. Réponds UNIQUEMENT avec une liste d'éléments JSON. Pas d'explications, pas d'interprétation. Si tu n'en trouves pas (ce qui est possible), envoie une liste vide. 
    """ 
    prompt2 = "Hello"
    # En-têtes HTTP requis pour l'authentification et le format des données
    HEADERS = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

     # payload minimal compatible Mistral / GPT
    if MODEL_NAME == "mte-api-piag-mistral-medium-latest":
        payload = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "n": 1}
    else:
        payload = {"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "verbosity": "low", "reasoning_effort": "minimal", "n": 1}


    try:
         # Appel à l'API PIAG avec gestion des erreurs HTTP 
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=(40, 120))
        r.raise_for_status()

        # Extraction du contenu de la réponse du modèle
        data = r.json()
        raw = data["choices"][0]["message"]["content"]
        
        # Chercher le premier grand tableau JSON dans la réponse
        m = re.search(r"\[[\s\S]*\]", raw)
        if not m:
            return []

        # Parser le tableau JSON
        ops = json.loads(m.group())
        # S'assurer qu'on renvoie bien une liste
        return ops if isinstance(ops, list) else []

    except Exception as e:
        print(" Erreur de parsing JSON ou d'appel API :", e)
        return []