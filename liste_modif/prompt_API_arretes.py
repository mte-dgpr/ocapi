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
import re, unicodedata
import time
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()  # Charge les données du .env

# === Configuration API === TODO : rendre cette partie remplissable pour choisir le modèle 
# URL de l'API PIAG en environnement de préproduction
API_URL = "https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions"

# Clé d'authentification pour l'API PIAG
API_KEY = os.getenv("PIAG_API_KEY")

# Nom du modèle
MODEL_NAME = "mte-api-piag-mistral-medium-latest"

# En-têtes HTTP requis pour l'authentification et le format des données
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",  # Authentification par token Bearer
    "Content-Type": "application/json",  # Format JSON pour les requêtes/réponses
}

# === Gestion Fichiers HTML ===

def normalize_html_minify(soup: BeautifulSoup) -> str:
    """
    Minifie légèrement le HTML sans casser la structure. (enlève images)
    """
    html = str(soup)
    html = unicodedata.normalize("NFC", html)
    # compacter les espaces entre balises
    html = re.sub(r">\s+<", "><", html)
    # compacter les espaces multiples
    html = re.sub(r"\s{2,}", " ", html)
    return html.strip()

def save_analysis_html(analysis_html: str, src_path: str, analysis_dir: str = "analysis_html") -> str:
    """
    Sauvegarde le HTML-lite dans analysis_html/<nom>.analysis.html
    """
    out_dir = Path(analysis_dir); out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (Path(src_path).stem + ".analysis.html")
    out_path.write_text(analysis_html, encoding="utf-8")
    return str(out_path)

def save_image_map(img_map: dict, src_path: str, analysis_dir: str = "analysis_html") -> str:
    """
    Sauvegarde la table {clé: image} en JSON à côté du HTML-lite.
    """
    out_dir = Path(analysis_dir); out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (Path(src_path).stem + ".images.json")
    out_path.write_text(json.dumps(img_map, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)

def rehydrate_images_in_html(fragment_html: str, img_map: dict) -> str:
    """
    Remplace les 'src="IMG_001"' par la data-URI correspondante de img_map.
    A utiliser AVANT d’insérer le fragment dans le permis consolidé final.
    ____ pour une étape future_______
    """
    for key, data_uri in img_map.items():
        fragment_html = fragment_html.replace(f'src="{key}"', f'src="{data_uri}"')
    return fragment_html

def extract_arrete_text(filepath):
    """
    Lit le HTML, enlève scripts/styles, remplace chaque <img> par une clé courte,
    sauve:
      - le HTML 'analysis' minifié (pour l'IA)
      - la table des images (clé -> data-URI ou src)
    Retourne:
      - analysis_html (str): EXACTEMENT ce qui sera envoyé à l'IA
      - analysis_file_path (str): chemin du .analysis.html
      - image_map_file (str): chemin du .images.json
    """
    html_raw = Path(filepath).read_text(encoding="utf-8")
    soup = BeautifulSoup(html_raw, "html.parser")

    # 1) enlever scripts/styles
    for t in soup(["script", "style"]):
        t.decompose()

    # 2) remplacer les images par des clés
    img_map = {}
    counter = 0
    for img in soup.find_all("img"):
        src = img.get("src", "")
        counter += 1
        key = f"IMG_{counter:03d}"
        if src.startswith("data:image/"):
            img_map[key] = src
            img["src"] = key  # clé légère dans le HTML-lite

    # 3) minifier le HTML
    analysis_html = normalize_html_minify(soup)

    # 4) sauvegardes
    analysis_file_path = save_analysis_html(analysis_html, filepath)
    image_map_file = save_image_map(img_map, filepath)

    # 5) retourner ce qu'on enverra à l'IA + où retrouver les infos
    return analysis_html, analysis_file_path, image_map_file

# === Envoi fichier à un LLM ===

def ask_llm_for_operation(analysis_html: str):
    """
    Envoie le HTML-lite tel quel au modèle et récupère une LISTE d'opérations.
    Chaque opération doit contenir des indices (start_index / end_index) qui pointent
    dans CE HTML-lite (indices 0-based, end_index exclusif).
    Retourne [] si rien n'est trouvé.
    """

    prompt = f"""
    Voici un texte juridique (arrêté préfectoral format HTML) :
    \"\"\"{analysis_html}\"\"\"
    L'objectif final du projet est de créer un permis consolidé (effectuer les opérations juridiques de différents arrêtés afin de construire un permis actualisé). Ta tâche est de détecter les opérations juridiques de ce texte, de type modification, ajout ou abrogation.
    Les informations cherchées sont les suivantes :
    1. Type de modification (ADD, REPLACE, REMOVE)
    2. Arrêté ciblé (référence simple de l'arrêté, telle qu'elle est citée — par exemple, « arrêté préfectoral du JJ MM AAAA » — et pas des variantes type « modifié »).
    3. Article ciblé de l'arrêté modifié si précisé
    4. Partie ciblée de l'article si précisé (Pour DELETE / REPLACE, préciser "contenu entier" le cas échéant. Sinon, préciser la partie ciblée par la modification, style "la première phrase"/"le tableau"/"la dernière ligne du tableau".)
    5. Nouveau contenu à insérer dans l'arrêté ciblé (pour ADD/REPLACE). Cite moi les indices de début et de fin du contenu ajouté, sans les explications. Cite moi aussi le contexte, c'est à dire le début EXACT et la fin EXACTE du nouveau contenu à ajouter. Je dois pouvoir extraire le contenu tel quel (commencant par le contexte de début, finissant par le contexte fin, et délimité par les indices) directement pour effectuer l'opération par la suite.
    Pour chaque opération, retourne un objet avec les clés:
    {{
    "modification_type": "ADD|REPLACE|REMOVE", "
    target_arrete": "arrêté concerné",
    "target_article": "article concerné de l'arrêté",
    "target_element": "élément précis de l'article si spécifié"
    "new_content_ref": {{
    "start_index": int,      // 0-based, end exclusif
    "end_index": int,
    "start_context": string, // 20-40 caractères EXACTS du début du nouveau contenu
    "end_context": string    // 20-40 caractères EXACTS de la fin du nouveau contenu
    }}
    }}
    Les indices et contextes DOIVENT correspondre exactement au HTML-LITE fourni. Réponds UNIQUEMENT avec une liste d'éléments JSON. Pas d'explications, pas d'interprétation.
    """ 

    # Payload de la requête API -- indique le modèle, le prompt et les paramètres
    payload = {
        "model": MODEL_NAME,   # garde ta constante existante
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0, # Température à 0 pour des résultats déterministes
        "n": 1
    }

    try:
         # Appel à l'API PIAG avec gestion des erreurs HTTP 
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=(15, 60))
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


def process_html_directory(folder_path):
    all_results = []

    for filename in os.listdir(folder_path):
        if filename.endswith(".html"):
            full_path = os.path.join(folder_path, filename)
            print(f" Traitement de : {filename}")

            # 1) préparer HTML-lite + images.json
            analysis_html, analysis_file, image_map_file = extract_arrete_text(full_path)
            print(f"Taille du texte extrait : {len(analysis_html)} caractères")

            # 2) appel IA avec EXACTEMENT ce HTML-lite
            try:
                results = ask_llm_for_operation(analysis_html)
            except Exception as e:
                print(" Erreur de parsing JSON ou d'appel API :", e)
                results = []

            print("#---------Arrêté traité.-------------#")
            print(f"{len(results)} modifications détectées.")

            # 3) enrichir les items avec les chemins utiles pour la suite
            for item in results:
                item["source_file"] = filename
                item["analysis_html_file"] = analysis_file   # pour relire le HTML-lite
                item["image_map_file"] = image_map_file      # pour réhydrater les images
                all_results.append(item)

            time.sleep(2)  # petite pause API (si utile)

    return all_results


if __name__ == "__main__":
    """
    Point d'entrée principal du script de détection de modifications .

    """
    dossier_html = "C:\\Users\\marie.tcheng\\Documents\\consolidation\\bench-ocapi\\exempleshtml\\ex4"

    resultat = process_html_directory(dossier_html)

    # Sauvegarde des résultats dans un fichier JSON structuré
    with open("modifications_detectees_arretes.json", "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)

    # Affichage du bilan final du traitement
    print(f"{len(resultat)} modifications détectées et sauvegardées.")
