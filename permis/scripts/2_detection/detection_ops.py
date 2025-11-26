from permis.scripts.utils.llm_utils import call_llm_api, parse_ops_llm_response

def detection_ops_llm(cfg, context_html: str) -> list:
    prompt = f"""
Extrait HTML d'arrêté préfectoral :
\"\"\"{context_html}\"\"\"

Détecte les opérations juridiques (modifications, ajouts, abrogations d'autres arrêtés).
Réponds UNIQUEMENT avec une liste JSON, sans explication.

ABROGATION :
{{
  "modification_type": "ABROGE",
  "source_article": "x.x.x" | null,
  "target_arrete": "DD/MM/YYYY",
  "target_article": "ALL" | "x.x.x",
  "target_in_article": "ALL" | "description élément" | null
}}

MODIFICATION :
{{
  "modification_type": "REPLACE",
  "source_article": "x.x.x" | null,
  "target_arrete": "DD/MM/YYYY",
  "target_article": "x.x.x",
  "target_in_article": "description élément" | null,
  "new_content_ref": {{
    "start_marker": "80-100 premiers token EXACTS du début",
    "end_marker": "80-100 derniers token EXACTS de la fin"
  }}
}}

AJOUT :
{{
  "modification_type": "ADD",
  "source_article": "x.x.x" | null,
  "target_arrete": "DD/MM/YYYY",
  "target_article": "END" | "NEW_ARTICLE:x.x.x" | "x.x.x",
  "target_in_article": "END" | "description position" | null,
  "new_content_ref": {{
    "start_marker": "80-100 premiers token EXACTS du début",
    "end_marker": "80-100 derniers token EXACTS de la fin"
  }}
}}

AUTRE :
{{
  "modification_type": "AUTRE",
  "source_article": "x.x.x" | null,
  "target_arrete": "DD/MM/YYYY",
  "target_article": "x.x.x" | null,
  "context": "description brève"
}}

Notes CRITIQUES :
- source_article : article du TEXTE FOURNI contenant l'opération si existe (ex: "2.1.3")
- target_arrete : date de l'arrêté MODIFIÉ (format DD/MM/YYYY)
- target_article : 
  * Article existant à compléter : "x.x.x" (ex: "9.2.1")
  * Nouvel article à créer : "NEW_ARTICLE:x.x.x"
  * Ajout en fin d'arrêté : "END" 
- target_in_article : description (ex: "première phrase", "le tableau", "END" pour ajout en fin d'article)
- start/end_marker : 
  * UNIQUEMENT le contenu à extraire (80-100 premiers et derniers tokens))
  * EXCLURE tout contexte : "sont remplacées par", "comme suit", etc.
  * Je dois pouvoir extraire le contenu compris entre start_marker et end_marker tel quel pour l'insérer dans l'arrêté ciblé.
- Liste vide [] si aucune opération
"""
    raw_response = call_llm_api(cfg, prompt)
    operations = parse_ops_llm_response(raw_response)
    return operations

# TODO : insérer rehydrate images 
# TODO : insérer extraction du contenu 
# TODO : insérer validation des opérations (lien avec noms fichiers ?)

# TODO : insérer raw ops to ops ici 
