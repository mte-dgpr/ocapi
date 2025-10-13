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

# === Configuration API PIAG ===
# URL de l'API PIAG en environnement de préproduction
API_URL = "https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions"

# Clé d'authentification pour l'API PIAG
# ⚠️ IMPORTANT : Cette clé doit être renseignée
API_KEY = "sk-fv5dSV6Ku0C1zLqKn4MjyQ"

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

def extract_arrete_text(filepath):
    """
    Extrait tout le texte utile d'un arrêté à partir du fichier HTML.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        # Si tu veux tout le texte :
        return soup.get_text(separator=" ", strip=True)





def ask_llm_for_operation(text_arrete):
    """
    Analyse un bloc de texte juridique via LLM pour détecter les opérations de modification.

    """ 
    prompt = f"""
Voici un extrait de texte juridique (arrêté préfectoral format HTML) : 

\"\"\"{text_arrete}\"\"\"

L'objectif final du projet est de consolider les permis (effectuer les opérations juridiques de différents arrêtés afin de construire un permis actualisé).
Ta tâche est de détecter les opérations juridiques de ce texte, de type modification, ajout ou abrogation. Si ce texte vient modifier (en remplaçant, ajoutant ou abrogeant) une partie d'un autre arrêté, j'ai besoin de détecter :

1. L'arrêté ciblé exactement (ne donne que la référence simple de l'arrêté, telle qu'elle est citée — par exemple, « arrêté préfectoral du JJ MM AAAA » — et pas des variantes type « modifié » ou d'autres éléments explicatifs).

2. L'article ciblé de l'arrêté si précisé

3. La partie ciblée de l'article si précisé (Pour une abrogation ou un remplacement, préciser "contenu entier" si c'est l'article ou l'arrêté entier qui est abrogé ou remplacé. Sinon, préciser la partie ciblée par la modification, style "la première phrase"/"le tableau"/"la dernière ligne du tableau"...)

4. La source de la modification (Le numéro de l'article de l'endroit où tu as trouvé la modification. Je veux pas le nom de l'article, juste la référence comme "Article X.X"))

5. Quelle est l'opération effectuée (Donc remplacement, ajout, abrogation)

6. Le **contenu exact de la modification** pour l’ajout ou le remplacement : Tu dois extraire et reprendre fidèlement tout le nouveau contenu de l’élément ajouté/remplacé du texte, y compris un tableau, sauf potentiellement une image en base64 si présent (par exemple, si la septième ligne d’un tableau est remplacée par une nouvelle ligne, mets dans "content" uniquement la nouvelle ligne telle qu’elle est indiquée dans le texte ; s’il s’agit d’une image, indique "content": [image du tableau du texte] ou conserve la balise <img> si elle est présente). Pour le reste, n'omet rien et n'invente rien, de manière à ce que je puisse effectuer la modification directement par la suite.

Ainsi, pour chaque opération que tu détectes, retourne moi une liste de JSON structuré dans ce format :

{{

"modification_type": "ADD|REPLACE|REMOVE",

"target_arrete": "arrêté concerné",

"target_article": "article concerné de l'arrêté",

"target_element": "élément précis de l'article si spécifié"

"source": "article source de la modification"

"content": "contenu précis de l'ajout ou de la modification" }}

Si aucune opération n'est détectée, retourne une liste vide.
La réponse doit être une liste JSON, même s'il n'y a qu'une seule opération. Ne fais aucune interprétation, contente-toi de ce qui est explicitement écrit dans le texte. Ne retourne que du JSON valide, sans texte explicatif autour.

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

            # Extraction du texte complet de l'arrêté
            arrete_text = extract_arrete_text(full_path)
            print(f"Taille du texte extrait : {len(arrete_text)} caractères")

            # Analyse du texte entier via LLM
            results = ask_llm_for_operation(arrete_text)
            print("#---------Arrêté traité.-------------#")
            print(f"{len(results)} modifications détectées.")

            # Ajout des résultats à la liste globale
            for result in results:
                result["source_file"] = filename # TODO : vérifier que le filename est bien au bon format
                all_results.append(result)

            time.sleep(2)
    return all_results


if __name__ == "__main__":
    """
    Point d'entrée principal du script de détection de modifications .

    """
    dossier_html = "C:\\Users\\marie.tcheng\\Documents\\consolidation\\identifier_modifs\\exempleshtml"

    resultat = process_html_directory(dossier_html)

    # Sauvegarde des résultats dans un fichier JSON structuré
    with open("modifications_detectees.json", "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)

    # Affichage du bilan final du traitement
    print(f"{len(resultat)} modifications détectées et sauvegardées.")
