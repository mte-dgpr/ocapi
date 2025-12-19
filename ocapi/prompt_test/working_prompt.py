def working_prompt(html: str) -> str:
    return f"""
Voici un extrait HTML d'arrêté préfectoral :
\"\"\"{html}\"\"\"

Tu dois me fournir une liste des opérations juridiques de cet arrêté par rapport à un arrêté antérieur.
IMPORTANT : Détecte UNIQUEMENT les modifications, ajouts ou abrogations d'arrêtés EXISTANTS.
Ne pas générer d'opération pour un arrêté initial ou une simple référence ("conformément à...").
Générer une opération seulement si le texte dit explicitement "est modifié", "est abrogé", "est ajouté à l'arrêté du...".

Réponds avec une liste JSON uniquement. Si aucune modification trouvée, retourne [].

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
- source_article : prendre le "data-number" de la section ou tu trouves l'opération
  * Le numéro d'article du TEXTE FOURNI contenant l'opération (ex: "2.1.3") 
  * Si l'opération provient d'un article dans une ANNEXE (balise <footer data-spec="appendix">): utilise "APPENDIX:x.x" (avec "x.x" le data-num de la section dans l'annexe si existant)
- target_arrete : date de l'arrêté MODIFIÉ (format DD/MM/YYYY)
- target_article : 
  * Article existant à compléter : "x.x.x" (ex: "9.2.1")
  * Nouvel article à créer : "NEW_ARTICLE:x.x.x"
  * Ajout en fin d'arrêté : "END" 
  * "ALL" pour abrogation de tout l'arreté
- sub_target : 
  * "ALL" : remplacer TOUT l'article cible
  * "END" : ajouter à la FIN de l'article cible
  * Description précise : ex. "première phrase", "le tableau", "colonne N°1"
- new_content_start_marker et new_content_end_marker : 
  * Copier EXACTEMENT le contenu HTML/texte tel qu'il apparaît dans le document (80-100 premiers et derniers tokens)
  * INCLURE les balises HTML (<table>, <th>, etc.) si présentes dans le nouveau contenu
  * EXCLURE le contexte introductif : "sont remplacées par", "comme suit", etc.
  * Le contenu entre start_marker et end_marker doit être extractible tel quel pour insertion dans l'arrêté cible
- Liste vide [] si aucune opération

RAPPEL : Un arrêté qui établit des règles n'est PAS une modification. Cherche "est modifié/abrogé/remplacé/ajouté".
"""