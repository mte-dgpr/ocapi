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
  "sub_target": "ALL" | str | null,
  "confidence_score": integer (0-100)
}}

MODIFICATION :
{{
  "operation_type": "REPLACE",
  "source_article": "x.x.x" | null,
  "target_arrete": "YYYY-MM-DD",
  "target_article": "ALL" | "x.x.x",
  "sub_target": str | null,
  "new_content_start_marker": "80-100 premiers token EXACTS du début" | null,
  "new_content_end_marker": "80-100 derniers token EXACTS de la fin" | null,
  "confidence_score": integer (0-100)
}}

REMPLACEMENT TOTAL (arrêté refonte) : Quand un arrêté remplace ENTIÈREMENT un arrêté antérieur
(« remplace l'arrêté du... », « abroge et remplace... »), utiliser target_article: "ALL".
Dans ce cas, new_content_start_marker et new_content_end_marker peuvent être null.

AJOUT :
{{
  "operation_type": "ADD",
  "source_article": "x.x.x" | null,
  "target_arrete": "YYYY-MM-DD",
  "target_article": "END" | "NEW_ARTICLE:x.x.x" | "x.x.x",
  "sub_target": "END" | str | null,
  "new_content_start_marker": "80-100 premiers token EXACTS du début",
  "new_content_end_marker": "80-100 derniers token EXACTS de la fin",
  "confidence_score": integer (0-100)
}}

AUTRE :
{{
  "operation_type": "AUTRE",
  "source_article": "x.x.x" | null,
  "target_arrete": "YYYY-MM-DD",
  "target_article": "x.x.x" | null,
  "failure_message": "description brève de pourquoi l'operation n'a pu etre caracterisée",
  "confidence_score": integer (0-100)
}}

REPORTS D'ÉCHÉANCES :
Quand le texte reporte une échéance figurant dans un article d'un arrêté antérieur
(ex. « l'échéance figurant à l'article 7.2.2 de l'arrêté du… est reportée au… »,
« le délai prévu à l'article X est prolongé jusqu'au… »), cela NE constitue PAS un
remplacement complet de l'article cible.
Utiliser un REPLACE avec un sub_target décrivant précisément la partie concernée
(ex. "l'échéance de réalisation du zonage", "la date limite de mise en conformité").
NE PAS utiliser sub_target "ALL" pour un simple report d'échéance.
Les marqueurs de contenu doivent délimiter le texte de la nouvelle disposition dans l'article source.

Exemple :
Texte source (article 1) : « L'échéance de réalisation du zonage des dangers internes
à l'établissement, selon les dispositions des articles 7.2.2 et 7.3.4 de l'arrêté du
10 décembre 2008, est reportée au 31 décembre 2010 »
→ Génère UNE opération par article cible :
{{
  "operation_type": "REPLACE",
  "source_article": "1",
  "target_arrete": "2008-12-10",
  "target_article": "7.2.2",
  "sub_target": "l'échéance de réalisation du zonage des dangers internes",
  "new_content_start_marker": "L'échéance de réalisation du zonage des dangers internes à l'établissement...",
  "new_content_end_marker": "...est reportée au 31 décembre 2010 ;",
  "confidence_score": 85
}}

Notes CRITIQUES :
- confidence_score : entier entre 0 et 100 indiquant ta certitude sur la détection de l'opération (0 = très incertain, 100 = totalement certain)
- source_article : prendre EXACTEMENT le "data-number" de la section ou tu trouves l'opération
  * Le numéro d'article du TEXTE FOURNI contenant l'opération (ex: "2.1.3")
  * Si l'opération provient d'un article dans une ANNEXE (balise <footer data-spec="appendix">): ajoute le suffixe "APPENDIX:" (devant "x.x" le data-number exact de la section dans l'annexe si existant)
- target_arrete : date de l'arrêté MODIFIÉ (format YYYY-MM-DD)
- target_article :
  * Article existant à compléter : "x.x.x" (ex: "9.2.1")
  * Nouvel article à créer : "NEW_ARTICLE:x.x.x"
  * Ajout en fin d'arrêté : "END"
  * "ALL" UNIQUEMENT pour : abrogation totale (REMOVE) OU refonte complète (REPLACE) quand le texte dit explicitement que l'arrêté antérieur est "abrogé et remplacé" ou "se substitue intégralement à".
  * NE PAS utiliser "ALL" quand l'arrêté modifie des dispositions ponctuelles (ex. "les dispositions... sont modifiées de la façon suivante" suivi d'une liste d'articles). Dans ce cas, créer UNE opération par article cible avec son numéro exact.
- sub_target :
  * "ALL" : remplacer TOUT l'article cible
  * "END" : ajouter à la FIN de l'article cible
  * Description précise : ex. "première phrase", "le tableau", "colonne N°1"
- new_content_start_marker et new_content_end_marker :
  * Copier EXACTEMENT le contenu HTML/texte tel qu'il apparaît dans le document (80-100 premiers et derniers tokens). Suffisamment long pour identifier précisément le contenu.
  * INCLURE les balises HTML (<table>, <th>, etc.) si présentes dans le nouveau contenu
  * EXCLURE le contexte introductif : "sont remplacées par", "comme suit", etc.
  * Le contenu entre start_marker et end_marker doit être extractible tel quel pour insertion dans l'arrêté cible.
- Liste vide [] si aucune opération detectée.
"""
