import re, unicodedata, math
from bs4 import BeautifulSoup
from pathlib import Path

def normalize_html_minify(soup: BeautifulSoup) -> str:
    # Convertit un fragment BeautifulSoup en HTML "minifié" :
    # - normalisation Unicode (NFC)
    # - supprime espaces entre balises et espaces multiples
    html = str(soup)
    html = unicodedata.normalize("NFC", html)
    html = re.sub(r">\s+<", "><", html)
    html = re.sub(r"\s{2,}", " ", html)
    return html.strip()

def extract_arrete_blocs(filepath: str, target_per_block: int = 80000, max_blocks: int = 4):
    """
    Lit un fichier HTML d'arrêté et renvoie une liste de "blocs" :
    chaque bloc est un dict { index, html, is_annex, title }.

    Stratégie :
    - On essaie d'extraire des <section> comme candidats (si présents).
    - Sinon on segmente grossièrement sur titres <h2>/<h3> ou body entier.
    - On calcule le nombre de blocs souhaité en fonction de la taille totale
      et du paramètre target_per_block (taille cible par bloc en caractères).
    - On fusionne les candidats pour obtenir ~n_blocks (limité par max_blocks).
    """
    html_raw = Path(filepath).read_text(encoding="utf-8")
    soup = BeautifulSoup(html_raw, "html.parser")

    # retirer scripts/styles inutiles pour alléger
    for t in soup(["script", "style"]):
        t.decompose()

    # remplacer les src d'images par des clés placeholders (IMG_001...)
    # permet de garder une référence sans transporter d'URLs volumineuses
    counter = 0
    for img in soup.find_all("img"):
        src = img.get("src", "")
        counter += 1
        key = f"IMG_{counter:03d}"
        if src:
            img["src"] = key

    # 1) essayer d'extraire des sections comme candidats de découpage 
    candidates = []
    # n'ajouter que les <section> qui ne sont pas à l'intérieur d'une autre <section>
    for sec in soup.find_all("section"):
        if sec.find_parent("section") is not None:
            continue
        sec_html = normalize_html_minify(BeautifulSoup(str(sec), "html.parser"))
        # éviter les doublons consécutifs (souvent causés par balises de pagination ou erreurs OCR)
        if not candidates or candidates[-1] != sec_html:
            candidates.append(sec_html)

    # calculs de taille / nombre de blocs
    total_len = sum(len(c) for c in candidates)
    # n_blocks = ceil(total_len / target_per_block) mais limité par max_blocks et au moins 1
    n_blocks = min(max_blocks, max(1, math.ceil(total_len / target_per_block)))

    # Si tout tient en 1 bloc, renvoyer l'intégralité fusionnée
    if n_blocks == 1:
        joined = "".join(c for c in candidates)
        return joined

    # Fusion progressive des candidats pour obtenir environ n_blocks blocs
    blocks = []
    current_html = ""
    current_is_annex = False
    for i, cand in enumerate(candidates):
        current_html += cand
        # Condition pour clore un bloc :
        # - si la taille courante >= target_per_block et on n'a pas encore rempli les blocs cibles-1
        # - ou si on est sur le dernier candidat pour finaliser le dernier bloc
        if (len(current_html) >= target_per_block and len(blocks) < n_blocks - 1) or (len(blocks) + 1 == n_blocks and i == len(candidates) - 1):
            blocks.append(current_html)
            current_html = ""

    # Si reste de contenu non ajouté -> l'ajouter comme dernier bloc 
    #ok ça c bien
    if current_html:
        blocks.append(current_html)

    # Sécurité : si aucune fusion n'a créé de bloc, renvoyer tout
    if not blocks:
        joined = "".join(c for c in candidates)
        blocks = [joined]

    return blocks