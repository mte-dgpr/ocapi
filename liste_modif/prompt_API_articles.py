"""

Ce script analyse automatiquement des documents HTML juridiques pour détecter et extraire
les opérations de modification (ajout, suppression, remplacement) en utilisant :
1. Extraction de contenu HTML avec BeautifulSoup
2. Analyse sémantique via LLM (Mistral) pour classification des modifications
3. Structuration des résultats en format JSON exploitable


Architecture du traitement :
    Document HTML → Analyse LLM → Classification → JSON structuré

Prérequis :
- Python 3.8+
- requests, beautifulsoup4, lxml
- Accès API PIAG (clé d'authentification requise)
- Documents HTML

"""

import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from dotenv import load_dotenv
import os

load_dotenv()  # Charge les données du .env

# === Configuration API PIAG ===
# URL de l'API PIAG en environnement de préproduction
API_URL = "https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions"

# Clé d'authentification pour l'API PIAG
# ⚠️ IMPORTANT : Cette clé doit être renseignée
API_KEY = os.getenv("PIAG_API_KEY")

# Nom du modèle
MODEL_NAME = "mte-api-piag-mistral-medium-latest"

# En-têtes HTTP requis pour l'authentification et le format des données
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",  # Authentification par token Bearer
    "Content-Type": "application/json",  # Format JSON pour les requêtes/réponses
}


# def extract_dsr_alinea_blocks(filepath):
#     """
#     Extrait tous les blocs de contenu juridique marqués avec la classe CSS 'dsr-alinea'.

#     Args:
#         filepath (str): Chemin vers le fichier HTML à analyser

#     Returns:
#         list[str]: Liste des contenus textuels extraits de chaque bloc dsr-alinea

#     Processus d'extraction :
#         1. Ouvre et parse le fichier HTML avec BeautifulSoup
#         2. Recherche tous les éléments <div class="arretify-operation">
#         3. Extrait le texte de chaque élément en préservant la structure
#         4. Filtre les blocs vides ou ne contenant que des espaces

#     Format HTML attendu :
#         <div class="dsr-alinea">
#             Contenu de l'alinéa juridique (article, paragraphe, etc.)
#         </div>

#     Note technique :
#         La classe 'dsr-alinea' est une convention utilisée dans les documents
#         juridiques gouvernementaux pour identifier les unités de contenu structuré.
#     """
#     with open(filepath, "r", encoding="utf-8") as f:
#         soup = BeautifulSoup(f, "html.parser")
#         divs = soup.find_all("div", class_="arretify-operation")
#         return [
#             div.get_text(separator=" ", strip=True)
#             for div in divs
#             if div.get_text(strip=True)
#         ]



def extract_text_blocks(filepath, max_chars=12000):
    """
    Extrait le texte du HTML et le découpe en blocs de taille max_chars.
    Coupe de préférence à la fin d'une balise <section> ou <div>.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        # On récupère le texte utile
        main_content = soup.find("main")
        if not main_content:
            main_content = soup.body
        # On récupère tous les blocs de texte (sections ou divs)
        blocks = []
        current_block = ""
        for elem in main_content.find_all(["section", "div"], recursive=True):
            text = elem.get_text(separator=" ", strip=True)
            if not text:
                continue
            if len(current_block) + len(text) < max_chars:
                current_block += "\n" + text
            else:
                blocks.append(current_block.strip())
                current_block = text
        if current_block.strip():
            blocks.append(current_block.strip())
        return blocks
    


def ask_llm_for_operation(text_arrete):
    """
    Analyse un bloc de texte juridique via LLM pour détecter les opérations de modification.

    """ 
    prompt = f"""
Voici un extrait de texte juridique (article d'arrêté préfectoral, format HTML) :

\"\"\"{text_arrete}\"\"\"

L'objectif final du projet est de consolider les permis (effectuer les opérations juridiques de différents arrêtés afin de construire un permis actualisé). Ta tâche est de détecter les opérations juridiques de ce texte.

Les opérations sont de 3 types : remplacement, ajout ou abrogation. Si cet article contient une opération visant un autre texte, j'ai besoin que tu la détecte et que tu me donnes certaines informations en vue de la consolidation de permis. Notamment je veux :

1. L'arrêté ciblé par la modification exactement (ne donne que la référence simple de l'arrêté, telle qu'elle est citée — par exemple, « arrêté préfectoral du JJ MM AAAA » — et pas de variantes ou éléments explicatifs tels que "modifié").

2. L'article ciblé de l'arrêté si précisé.

3. La partie ciblée de l'article si précisé (Pour une abrogation ou un remplacement, préciser "contenu entier" si c'est l'article ou l'arrêté entier qui est abrogé ou remplacé. Sinon, préciser la partie ciblée par la modification, style "la première phrase"/"le tableau"/"la dernière ligne du tableau"...)

4. Quelle est l'opération effectuée ? (Donc remplacement, ajout, abrogation)

5. Le **contenu exact de la modification** pour l’ajout ou le remplacement : Tu dois extraire et reprendre fidèlement tout le nouveau contenu HTML de l’élément ajouté/remplacé du texte, afin que la modification de l'arrêté cible puisse être fait directement en format HTML. Par exemple, si une ligne d’un tableau est remplacée par une nouvelle, le contenu est uniquement la nouvelle ligne telle qu’elle est indiquée dans le texte ; s’il s’agit d’une image, indique "content": [image du tableau du texte] ou conserve la balise si elle est présente. N'omet rien et n'invente rien, de manière à ce que je puisse effectuer la modification directement par la suite.

Ainsi, pour chaque opération que tu détectes, retourne moi une liste de JSON structuré dans ce format :

{{

"modification_type": "ADD|REPLACE|REMOVE",

"target_arrete": "arrêté concerné",

"target_article": "article concerné de l'arrêté",

"target_element": "élément précis de l'article si spécifié"

"content": "contenu précis de l'ajout ou de la modification" }}

Si aucune opération n'est détectée, retourne une liste vide. La réponse doit être une liste JSON, même s'il n'y a qu'une seule opération. S'il y en a pas, renvoie moi une liste vide. Ne fais aucune interprétation, contente-toi de ce qui est explicitement écrit dans le texte. Ne retourne que du JSON valide, sans texte explicatif autour.

"""
    # Payload de la requête API -- indique le modèle, le prompt et les paramètres
    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,  # Température à 0 pour des résultats déterministes
    }

    try:
        # Appel à l'API PIAG avec gestion des erreurs HTTP 
        response = requests.post(API_URL, headers=HEADERS, json=data) 
        response.raise_for_status()  # Lève une exception si erreur HTTP

        # Extraction du contenu de la réponse du modèle
        raw_content = response.json()["choices"][0]["message"]["content"] #TODO: changer json en liste de json?

        # Tentative d'extraction du JSON de la réponse avec regex robuste
        match = re.search(r"\[[\s\S]*\]", raw_content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                # Si le JSON est malformé, retourne un résultat par défaut
                return []

        # Aucun JSON trouvé dans la réponse
        return []

    except Exception as e:
        # Gestion globale des erreurs avec logging
        print(" Erreur de parsing JSON ou d'appel API :", e)
        return []


def process_html_directory(folder_path):
    """
    Traite récursivement tous les fichiers HTML d'un répertoire pour détecter les modifications.

    """
    all_results = []

    # Parcours de tous les fichiers du répertoire source
    for filename in os.listdir(folder_path):
        if filename.endswith(".html"):  # Traite uniquement les fichiers HTML
            full_path = os.path.join(folder_path, filename)
            print(f" Traitement de : {filename}")

            # Extraction des articles
            text_blocks = extract_text_blocks(full_path, max_chars=10000)
            print(f"{len(text_blocks)} blocs extraits.")

            # Analyse chaque bloc via LLM
            before = len(all_results)
            for i, block in enumerate(text_blocks):
                results = ask_llm_for_operation(block)
                for result in results:
                    result["source_file"] = filename
                    result["block_index"] = i
                    all_results.append(result)
                time.sleep(2)
            after = len(all_results)
            print("#---------Arrêté traité.-------------#")
            print(f"{after - before} modifications détectées dans l'arrêté.")

    return all_results


if __name__ == "__main__":
    """
    Point d'entrée principal du script de détection de modifications .

    """
    dossier_html = "C:\\Users\\marie.tcheng\\Documents\\consolidation\\bench-ocapi\\exempleshtml" 

    resultat = process_html_directory(dossier_html)

    # Sauvegarde des résultats dans un fichier JSON structuré
    with open("modifications_detectees.json", "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)

    # Affichage du bilan final du traitement
    print(f"{len(resultat)} modifications détectées et sauvegardées.")
