"""

Ce script analyse automatiquement des documents HTML juridiques pour détecter et extraire
les opérations de modification (ajout, suppression, remplacement) en utilisant :
1. Extraction de contenu HTML avec BeautifulSoup
2. Analyse sémantique via LLM pour classification des modifications
3. Structuration des résultats en format JSON exploitable


Architecture du traitement :
    Document HTML → Extraction d'un contenu HTML-LITE → Analyse LLM → Classification → JSON structuré

Prérequis :
- Python 3.8+
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
import html


# === Configuration API === 
"""
Permet désormais de configurer le modèle LLM de manière interactive.
"""
load_dotenv()  # Charge les données du .env
def config_API(modele):
    if modele=="GPT5":
        model = "gpt-5"
        key = os.getenv("OPENAI_API_KEY")
        apiurl = "https://api.openai.com/v1/chat/completions"

    elif modele=="GPT5mini":
        model = "gpt-5-mini"
        key = os.getenv("OPENAI_API_KEY")
        apiurl = "https://api.openai.com/v1/chat/completions"
   
    else:
        modele = "Mistral"
        model = "mte-api-piag-mistral-medium-latest"  # valeur par défaut
        key= os.getenv("PIAG_API_KEY")
        apiurl = "https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions"
   
    print(f"Modèle utilisé : {modele}")
   
    return model, key, apiurl

# === Gestion Fichiers HTML - input ===

def normalize_html_minify(soup: BeautifulSoup) -> str:
    """
    Minifie légèrement le HTML sans casser la structure. (enlève images + espaces inutiles)
    """
    html = str(soup)
    html = unicodedata.normalize("NFC", html)

    # compacter les espaces entre balises
    html = re.sub(r">\s+<", "><", html)

    # compacter les espaces multiples
    html = re.sub(r"\s{2,}", " ", html)

    return html.strip()

def extract_arrete_text(filepath):
    """
    Retourne une liste d'articles (liste de dicts {"index","html","is_annex","title"}).
    Ne renvoie plus analysis_html. Les scripts/styles sont retirés et les images sont remplacées
    par des clés dans le HTML des articles (mais on ne renvoie pas ici le mapping img_map).
    """
    html_raw = Path(filepath).read_text(encoding="utf-8")
    soup = BeautifulSoup(html_raw, "html.parser")

    # Enlève scripts/styles
    for t in soup(["script", "style"]):
        t.decompose()

    # Remplace les images par des clés (localement dans le soup utilisé pour construire les articles)
    counter = 0
    for img in soup.find_all("img"):
        src = img.get("src", "")
        counter += 1
        key = f"IMG_{counter:03d}"
        if src:
            img["src"] = key

    # Extraction des sections "articles"
    articles = []
    used_nodes = []

    # 1) privilégier les <section> qui semblent contenir des articles
    for sec in soup.find_all("section"):
        title = sec.find(["h1", "h2", "h3", "h4"])
        title_text = title.get_text(" ", strip=True) if title else ""
        if re.search(r"\barticle\b", title_text, flags=re.IGNORECASE) or sec.get("data-type") == "article":
            is_annex = bool(re.search(r"\bannex", title_text, flags=re.IGNORECASE)) or ("annex" in (sec.get("class") or []))
            sec_html = normalize_html_minify(BeautifulSoup(str(sec), "html.parser"))
            articles.append({"index": len(articles), "html": sec_html, "is_annex": is_annex, "title": title_text})
            used_nodes.append(sec)

    # 2) fallback : si aucun <section> identifié comme article, découper par titres <h2>/<h3>
    if not articles:
        body = soup.body or soup
        current_nodes = []
        idx = 0
        for elem in list(body.children):
            # ignorer header tags
            if getattr(elem, "name", None) and elem.name == "header":
                continue
            if getattr(elem, "name", None) and elem.name in ("h2", "h3"):
                if current_nodes:
                    block_html = normalize_html_minify(BeautifulSoup("".join(str(x) for x in current_nodes), "html.parser"))
                    articles.append({"index": idx, "html": block_html, "is_annex": False, "title": ""})
                    idx += 1
                    current_nodes = []
                current_nodes.append(elem)
            else:
                current_nodes.append(elem)
        if current_nodes:
            block_html = normalize_html_minify(BeautifulSoup("".join(str(x) for x in current_nodes), "html.parser"))
            articles.append({"index": idx, "html": block_html, "is_annex": False, "title": ""})

    # 3) construire fragment "reste du document" hors header et hors sections identifiées
    soup_copy = BeautifulSoup(str(soup), "html.parser")
    for h in soup_copy.find_all("header"):
        h.decompose()

    # si nous avons identifié des sections originales, essayer de les retirer de la copie
    if used_nodes:
        for orig_sec in used_nodes:
            short = " ".join(orig_sec.get_text(" ", strip=True).split())[:80]
            for sec_c in soup_copy.find_all("section"):
                if short and short in " ".join(sec_c.get_text(" ", strip=True).split()):
                    sec_c.decompose()
                    break

    remaining_html = ""
    if soup_copy.body:
        remaining_html = normalize_html_minify(soup_copy.body)
    else:
        remaining_html = normalize_html_minify(soup_copy)

    text_only = BeautifulSoup(remaining_html, "html.parser").get_text(" ", strip=True)
    if text_only and len(text_only) > 10:
        articles.append({"index": len(articles), "html": remaining_html, "is_annex": True, "title": "remaining"})

    return articles
#== Extraction du fragment HTML à insérer - output ===

def _find_marker(haystack: str, marker: str) -> int:
    """
    Retourne l'index de 'marker' dans 'haystack'. Essai exact, puis souple (espaces/sauts de ligne compressés). -1 si introuvable.
    """
    if not marker: return -1

    # Essai exact
    i = haystack.find(marker)
    if i != -1: return i

    # Essai "souple" : autoriser \s+ à la place des suites d'espaces
    n = html.unescape(marker)
    # construire un pattern qui autorise \s+ pour les espaces
    pattern = re.sub(r"\s+", r"\\s+", re.escape(n))
    m = re.search(pattern, haystack, flags=re.IGNORECASE | re.DOTALL)
    return m.start() if m else -1

def _pick_section_html_for_source(analysis_html: str, source_article: str | None) -> tuple[str, int]:
    """
    Si source_article contient un numéro (ex: 'Article 4'), on tente d'isoler la <section>
    qui contient ce numéro dans son titre. Sinon on retourne tout le document.
    """
    if not source_article:
        # Si pas de source, on va chercher le contenu dans tout le document. 
        return analysis_html

    m = re.search(r'(\d+(?:\.\d+)*)', source_article) # m est la suite de chiffre extraite de source articles
    wanted = m.group(1) if m else source_article.strip() # Si trouvé, on le garde, sinon garde le titre

    soup = BeautifulSoup(analysis_html, "html.parser")
    for sec in soup.find_all("section"):
        # chercher texte du titre dans la section
        title_text = " ".join(sec.get_text(" ", strip=True).split()) #recup texte de la section et nettoie
        if re.search(rf'\b{re.escape(wanted)}\b', title_text, flags=re.IGNORECASE):
            sec_html = str(sec)
            return sec_html

    return analysis_html

def _rehydrate_images(fragment_html: str, img_map: dict) -> str:
    """
    Remet les src originaux en utilisant BeautifulSoup (plus robuste que des remplacements texte simples).
    """
    if not img_map:
        return fragment_html

    soup = BeautifulSoup(fragment_html, "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and src in img_map:
            img["src"] = img_map[src]
    return str(soup)

def remplacer_new_content(analysis_html: str, img_map: dict, source_article: str | None, start_marker: str | None, end_marker: str | None) -> str | None:
    """
    Simplifié et direct :
    - tente d'isoler la section ciblée (si possible),
    - cherche start_marker (+ end_marker si fourni),
    - si pas de end_marker : renvoie le parent logique contenant le marker (blockquote/table/p/div/section),
      sinon un repli (fenêtre limitée) depuis le début du marker.
    """
    if not start_marker:
        return None

    # limiter au scope si possible
    scope_html = _pick_section_html_for_source(analysis_html, source_article)

    # chercher start dans la section, puis dans tout le document si besoin
    working_html = scope_html
    start_idx = _find_marker(working_html, start_marker)
    if start_idx == -1:
        working_html = analysis_html
        start_idx = _find_marker(working_html, start_marker)
        if start_idx == -1:
            return None

    # si on a un end_marker, essayer de le trouver dans le même working_html
    end_idx = -1
    if end_marker:
        end_idx = _find_marker(working_html, end_marker)
        if end_idx != -1:
            # inclure la longueur du end_marker
            end_idx = end_idx + len(end_marker)

    if end_idx != -1:
        fragment = working_html[start_idx:end_idx]
        fragment = _rehydrate_images(fragment, img_map)
        return fragment.strip() if fragment else None

    # Pas d'end_marker : tenter d'extraire le parent logique contenant le start_marker
    soup_scope = BeautifulSoup(working_html, "html.parser")
    candidate_tags = ["blockquote", "table", "p", "div", "section"]
    for tag_name in candidate_tags:
        for tag in soup_scope.find_all(tag_name):
            tag_html = str(tag)
            if _find_marker(tag_html, start_marker) != -1:
                fragment = _rehydrate_images(tag_html, img_map)
                return fragment.strip() if fragment else None

    # Dernier repli : prendre une fenêtre raisonnable depuis le start dans le working_html
    # (ex: 2000 caractères) pour éviter renvoyer tout le document
    window = 2000
    fragment = working_html[start_idx:start_idx + window]
    fragment = _rehydrate_images(fragment, img_map)
    return fragment.strip() if fragment else None

# === Envoi du fichier à un LLM ===

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
    Pour chaque opération que tu trouves, retourne un objet avec les clés:
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
    Les indices et contextes DOIVENT correspondre exactement au HTML-LITE fourni. Réponds UNIQUEMENT avec une liste d'éléments JSON. Pas d'explications, pas d'interprétation. Si tu n'en trouves pas (ce qui est probable), envoie une liste vide. 
    """ 
    # En-têtes HTTP requis pour l'authentification et le format des données
    HEADERS = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # Payload de la requête API -- indique le modèle, le prompt et les paramètres
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "n": 1
    }

    try:
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=(15, 60))
    except Exception as e:
        print("[debug] erreur réseau lors de requests.post :", e)
        return []

    # debug : afficher statut / réponse courte si erreur
    if r.status_code >= 400:
        print(f"[debug] API returned status {r.status_code}")
        print("[debug] response body:", r.text[:2000])
        return []

    try:
        data = r.json()
    except Exception as e:
        print("[debug] impossible de décoder la réponse JSON :", e)
        print("[debug] corps brut :", r.text[:2000])
        return []

    # extraction du contenu
    raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not raw:
        print("[debug] réponse du modèle vide ou format inattendu")
        return []

    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        print("[debug] aucun tableau JSON trouvé dans la réponse du modèle (preview) :", raw[:500])
        return []

    try:
        ops = json.loads(m.group())
    except Exception as e:
        print("[debug] erreur parsing JSON extrait :", e)
        print("[debug] JSON brut extrait :", m.group()[:1000])
        return []

    return ops if isinstance(ops, list) else []

def process_html_directory(folder_path, cfg):
    """
    Parcourt le dossier, pour chaque fichier :
     - extrait la liste d'articles via extract_arrete_text (article par article)
     - reconstruit localement img_map pour le fichier traité
     - envoie chaque article séparément à ask_llm_for_operation
     - transforme les markers -> fragment HTML en cherchant uniquement DANS L'ARTICLE
    """
    all_results = []

    for filename in os.listdir(folder_path):
        if filename.endswith(".html"):
            full_path = os.path.join(folder_path, filename)
            print(f" Traitement de : {filename}")

            # extraire la liste d'articles (article par article)
            articles = extract_arrete_text(full_path)
            total_len = sum(len(a.get("html","")) for a in articles)
            print(f"Taille cumulée des articles extraits : {total_len} caractères")

            # reconstruire img_map à partir du fichier original (nécessaire pour _rehydrate_images)
            html_raw = Path(full_path).read_text(encoding="utf-8")
            soup_orig = BeautifulSoup(html_raw, "html.parser")
            for t in soup_orig(["script", "style"]):
                t.decompose()
            img_map = {}
            counter = 0
            for img in soup_orig.find_all("img"):
                src = img.get("src", "")
                counter += 1
                key = f"IMG_{counter:03d}"
                if src:
                    img_map[key] = src

            file_results = []
            # pour chaque article/fragment, envoyer séparément au LLM
            for art in articles:
                art_html = art.get("html", "")
                is_annex = art.get("is_annex", False)
                art_index = art.get("index", None)

                try:
                    results = ask_llm_for_operation(art_html, cfg)
                except Exception:
                    results = []

                for item in results:
                    item["source_file"] = filename
                    item["article_index"] = art_index
                    item["is_annex"] = is_annex

                    typeitem = item.get("modification_type")
                    fragment = None
                    if typeitem != "DELETE":
                        ref = item.get("new_content_ref") or {}
                        start_marker = ref.get("start_marker")
                        end_marker = ref.get("end_marker")
                        source_article = item.get("source_article")
                        # rechercher la modif UNIQUEMENT dans l'article (art_html)
                        fragment = remplacer_new_content(art_html, img_map, source_article, start_marker, end_marker)
                    item["new_content_html"] = fragment  # peut être None si introuvable

                    file_results.append(item)

                time.sleep(1)

            print("#---------Arrêté traité.-------------#")
            print(f"{len(file_results)} modifications détectées.")
            all_results.extend(file_results)

            time.sleep(1)

    return all_results

# === Point d'entrée principal ===
if __name__ == "__main__":

    dossier_html = "C:\\Users\\marie.tcheng\\Documents\\consolidation\\bench-ocapi\\exempleshtml"

    modele = input("Modèle à utiliser (laisser vide pour défaut Mistral / GPT5 / GPT5mini) : ")
    cfg = config_API(modele)
    resultat = process_html_directory(dossier_html, cfg)

    # Sauvegarde des résultats dans un fichier JSON structuré
    with open("modifications_detectees_articles.json", "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)

    # Affichage du bilan final du traitement
    print(f"{len(resultat)} modifications détectées et sauvegardées.")