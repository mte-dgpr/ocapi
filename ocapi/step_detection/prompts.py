#
# Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
def prompt_detection(html: str) -> str:
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
  "target_arrete": "YYYY-MM-DD",
  "target_article": "ALL" | "x.x.x",
  "sub_target": "ALL" | str | null
}}

MODIFICATION :
{{
  "operation_type": "REPLACE",
  "source_article": "x.x.x" | null,
  "target_arrete": "YYYY-MM-DD",
  "target_article": "x.x.x",
  "sub_target": str | null,
  "new_content_start_marker": "80-100 premiers token EXACTS du début",
  "new_content_end_marker": "80-100 derniers token EXACTS de la fin"
}}

AJOUT :
{{
  "operation_type": "ADD",
  "source_article": "x.x.x" | null,
  "target_arrete": "YYYY-MM-DD",
  "target_article": "END" | "NEW_ARTICLE:x.x.x" | "x.x.x",
  "sub_target": "END" | str | null,
  "new_content_start_marker": "80-100 premiers token EXACTS du début",
  "new_content_end_marker": "80-100 derniers token EXACTS de la fin"
}}

AUTRE :
{{
  "operation_type": "AUTRE",
  "source_article": "x.x.x" | null,
  "target_arrete": "YYYY-MM-DD",
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
