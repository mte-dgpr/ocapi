FULL_SECTION = "contenu entier"


def prompt(analysis_html: str) -> str:
    return f"""
Voici un extrait de texte juridique (article ou extrait d'un arrêté préfectoral format HTML) :
\"\"\"{analysis_html}\"\"\"
L'objectif final du projet est de créer un permis consolidé (effectuer les opérations juridiques de différents arrêtés).
Ta tâche est de détecter s'il y a une opération juridique dans ce texte, de type modification, ajout ou abrogation.
S'il y a une opération (modification d'un arrêté, abrogation, ajout dans un autre arrêté), alors les informations cherchées sont les suivantes :
1. Type de modification (ADD, REPLACE, REMOVE)
2. Arrêté ciblé (format « arrêté préfectoral du JJ MM AAAA » — et pas des variantes type « modifié »).
3. Article ciblé de l'arrêté modifié si précisé
4. Partie ciblée de l'article si précisé
    ("{FULL_SECTION}" le cas échéant. Sinon, préciser partie ciblée par ex "la première phrase"/"le tableau"/"la dernière ligne du tableau".)
5. Nouveau contenu à insérer dans l'arrêté ciblé (pour ADD/REPLACE). Cite moi le début EXACT et la fin EXACTE du nouveau contenu à ajouter.
Ne recopie pas tout, je pourrai extraire moi-même. Je dois pouvoir extraire le contenu tel quel directement pour effectuer l'opération
par la suite, donc le nouveau contenu ne doit pas contenir de contexte explicatif..
6. Article source de la modification (juste référence de l'article, pas de titre/contenu explicatif. Juste "Article X.X", par exemple.)
Pour chaque opération que tu trouves, retourne donc un objet avec les clés:
{{
"operation_type": "ADD|REPLACE|REMOVE",
"target_arrete": "arrêté concerné",
"target_article": "article concerné de l'arrêté",
"target_element": "élément précis de l'article si spécifié"
"new_content_ref": {{
"new_content_start_marker": string,   // 80 à 100 caractères EXACTS du début du nouveau contenu. pas plus.
"new_content_end_marker": string,     // 80 à 100 caractères EXACTS de la fin du nouveau contenu. pas plus.
}}
"source_article" : "référence article source, sans le titre"
}}
Les markers DOIVENT correspondre exactement au HTML-LITE fourni. Réponds UNIQUEMENT avec une liste d'éléments JSON.
Pas d'explications, pas d'interprétation. Si tu n'en trouves pas (ce qui est possible), envoie une liste vide.
"""


# TODO : rajouter A-x.x pour article x.x dans annexes?
def prompt2(analysis_html: str) -> str:
    return f"""
Voici un extrait HTML d'arrêté préfectoral :
\"\"\"{analysis_html}\"\"\"

Détecte les opérations juridiques (modifications, ajouts, abrogations d'autres arrêtés).
Réponds UNIQUEMENT avec une liste JSON, sans explication.

ABROGATION :
{{
  "operation_type": "REMOVE",
  "source_article": "x.x.x" | null,
  "target_arrete": "DD/MM/YYYY",
  "target_article": "ALL" | "x.x.x",
  "sub_target": "ALL" | str | null
}}

MODIFICATION :
{{
  "operation_type": "REPLACE",
  "source_article": "x.x.x" | null,
  "target_arrete": "DD/MM/YYYY",
  "target_article": "x.x.x",
  "sub_target": str | null,
  "new_content_start_marker": "80-100 premiers token EXACTS du début",
  "new_content_end_marker": "80-100 derniers token EXACTS de la fin"
}}

AJOUT :
{{
  "operation_type": "ADD",
  "source_article": "x.x.x" | null,
  "target_arrete": "DD/MM/YYYY",
  "target_article": "END" | "NEW_ARTICLE:x.x.x" | "x.x.x",
  "sub_target": "END" | str | null,
  "new_content_start_marker": "80-100 premiers token EXACTS du début",
  "new_content_end_marker": "80-100 derniers token EXACTS de la fin"
}}

AUTRE :
{{
  "operation_type": "AUTRE",
  "source_article": "x.x.x" | null,
  "target_arrete": "DD/MM/YYYY",
  "target_article": "x.x.x" | null,
  "failure_message": "description brève de pourquoi l'operation n'a pu etre caracterisée"
}}

Notes CRITIQUES :
- source_article : article du TEXTE FOURNI contenant l'opération si existe (ex: "2.1.3")
- target_arrete : date de l'arrêté MODIFIÉ (format DD/MM/YYYY)
- target_article : 
  * Article existant à compléter : "x.x.x" (ex: "9.2.1")
  * Nouvel article à créer : "NEW_ARTICLE:x.x.x"
  * Ajout en fin d'arrêté : "END" 
- sub_target : description (ex: "première phrase", "le tableau", "END" pour ajout en fin d'article)
- start/new_content_end_marker : 
  * UNIQUEMENT le contenu à extraire (80-100 premiers et derniers tokens))
  * EXCLURE tout contexte : "sont remplacées par", "comme suit", etc.
  * Je dois pouvoir extraire le contenu compris entre new_content_start_marker et new_content_end_marker tel quel pour l'insérer dans l'arrêté ciblé.
- Liste vide [] si aucune opération
"""
