
"""
Lire data/arretes_blocs/*.blocks.json. 
Pour chaque bloc, appeler ask_llm_for_operation (ou skip si --no-api)
Ecrire sorties groupées par AP dans data/operations_brutes/<ap>.ops.json
Choisir le modèle via --model ou la variable DEFAULT_MODEL
"""

#TODO comprendre choix du modele 
#TODO modifier les opérations pour prendre en compte les changements de titre ou deplacement d'article. 
#TODO réécrire le prompt????
#TODO envoyer la structure ? 

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Tuple
import requests

from dotenv import load_dotenv

# charger explicitement le .env à la racine du projet (remonter suffisamment)
project_root = Path(__file__).resolve().parents[3]
env_path = project_root / ".env"
print("DEBUG: load .env from:", env_path)
if env_path.exists():
    load_dotenv(env_path)
else:
    from dotenv import find_dotenv
    p = find_dotenv()
    print("DEBUG: find_dotenv returned:", p)
    if p:
        load_dotenv(p)

def config_API(modele: str) -> Tuple[str, str, str]:
    """
    Retourne (MODEL_NAME, API_KEY, API_URL) selon le nom logique du modèle.
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
    
# --- traitement des fichiers blocs -> opérations brutes ---

def run(skip_api: bool = True, modele: str = None, input_dir: Path = None, out_dir: Path = None):
    """
    Mode proche de run_pipeline.py :
    - lit les fichiers *.blocks.json dans data/arretes_blocs
    - pour chaque bloc appelle ask_llm_for_operation (ou skip si --no-api)
    - écrit un fichier groupé par AP dans data/operations_brutes/<ap>.ops.json
    - sortie contient métadonnées similaires à run_pipeline (api_attempts, api_nonempty, etc.)
    """
    modele = modele or os.getenv("DEFAULT_MODEL")
    cfg = config_API(modele)
    print(f"DEBUG: modele={modele} -> cfg_model={cfg[0]} key_present={bool(cfg[1])}")

    if input_dir is None:
        input_dir = project_root / "permis" / "data" / "arretes_blocs"
    if out_dir is None:
        out_dir = project_root / "permis" / "data" / "operations_brutes"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(Path(input_dir).glob("*.blocks.json"))
    if not files:
        print("Aucun fichier de blocs trouvé dans", input_dir)
        return

    for f in files:
        ap_name = f.stem.replace(".blocks", "")
        src_html_name = ap_name + ".html"
        print("Traitement :", f.name, "->", ap_name)
        try:
            blocks = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print("Impossible de lire/parse", f, e)
            continue

        if not blocks:
            print("Aucun bloc normalisé pour", f)
            continue

        all_ops = []
        t0 = time.time()

        for b in blocks:
            html_block = b.get("html", "")
            block_index = b.get("index")
            if skip_api:
                ops = []
            else:
                ops = ask_llm_for_operation(html_block, cfg)

            # enrichir ops avec métadatas de provenance
            for op in ops:
                if isinstance(op, dict):
                    op.setdefault("block_index", block_index)
                    op.setdefault("source_file", src_html_name)
                all_ops.append(op)

            if not skip_api:
                time.sleep(0.2)

        elapsed = time.time() - t0
        out = {
            "source_file": src_html_name,
            "total_chars": sum(len(b.get("html","")) for b in blocks),
            "n_blocks_sent": len(blocks),
            "processing_time_s": round(elapsed, 2),
            "operations": all_ops
        }

        out_path = Path(out_dir) / f"{ap_name}.ops.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Écrit : {out_path} - {len(all_ops)} operations - temps {elapsed:.2f}s")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Envoyer blocs au LLM et sauvegarder opérations brutes par AP")
    p.add_argument("--no-api", action="store_true", help="ne pas appeler l'API (mode test)")
    p.add_argument("--model", "-m", help="nom du modèle logique (ex: GPT5, GPT5mini, ou vide pour default)")
    p.add_argument("--input", "-i", help="dossier input contenant *.blocks.json")
    p.add_argument("--out", "-o", help="dossier de sortie pour opérations brutes")
    args = p.parse_args()

    input_dir = Path(args.input) if args.input else None
    out_dir = Path(args.out) if args.out else None
    run(skip_api=args.no_api, modele=args.model, input_dir=input_dir, out_dir=out_dir)
