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
import json
import re
import textwrap
from typing import Any

from ocapi.types import OperationType
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def prompt_detection(html: str) -> str:
    return f"""
Voici un extrait HTML d'arrêté préfectoral :
\"\"\"{html}\"\"\"

Tu dois me fournir une liste des opérations juridiques de cet arrêté par rapport à un arrêté antérieur.
IMPORTANT : Détecte UNIQUEMENT les modifications, ajouts ou abrogations d'arrêtés EXISTANTS.
Ne pas générer d'opération pour un arrêté initial ou une simple référence ("conformément à...").
Générer une opération seulement si le texte contient explicitement un verbe d'opération sur un arrêté antérieur.

Voici une liste non exhaustive des formulations courantes et l'operation_type à utiliser :
- REMOVE : "abroger", "supprimer", "annuler" (UNIQUEMENT quand le verbe est seul, sans verbe de remplacement)
- REPLACE : "modifier", "remplacer", "substituer", "mettre à jour", "modifier et rédiger", "modifier et remplacer", "remplacer et compléter", "abroger et remplacer", "abroger et substituer", "supprimer et remplacer", "annuler et remplacer", "modifier ou supprimer et remplacer"
- ADD : "créer", "insérer", "compléter", "ajouter", "modifier par l'ajout"
ATTENTION : quand un verbe d'abrogation/suppression est suivi d'un verbe de remplacement (ex. "abroger et remplacer", "supprimer et remplacer"), il s'agit d'un REPLACE, pas d'un REMOVE.

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


def parse_llm_json_list_response(raw: str) -> list[dict[str, Any]]:
    """Parse the raw LLM response to extract a JSON list.

    Note: Returns an empty list on parsing errors. Errors are logged but not
    retried — retries must be handled at the API call level, not the parsing level.
    """
    # Find the first JSON array in the response
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        _LOGGER.warning(
            f"No JSON array found in LLM response. " f"Raw response (first 200 chars): {raw[:200]}"
        )
        return []

    # Parse the JSON array
    try:
        lst: Any = json.loads(m.group())
        # Ensure we return a list
        if not isinstance(lst, list):
            _LOGGER.warning(
                f"Parsed JSON is not a list but a {type(lst).__name__}. " f"Returning empty list."
            )
            return []
        return lst
    except json.JSONDecodeError as e:
        _LOGGER.error(
            f"LLM JSON parsing error: {e}. " f"JSON content (first 200 chars): {m.group()[:200]}"
        )
        return []


def query_llm_for_subtarget(
    operation_type: OperationType,
    target_content: str,
    sub_target: str,
    *,
    target_article_id: str | None = None,
    operand: str | None = None,
    source_content: str | None = None,
) -> str:
    """Build a prompt for LLM-assisted consolidation (locate sub-target in HTML).

    When ``source_content`` is provided, it is the HTML of the *source* article
    (arrêté modifiant) that motivates the operation; it helps disambiguate
    complex cases (e.g. table rows, nested structures).

    Returns a prompt string for a REPLACE, REMOVE or ADD operation.
    The prompt asks the LLM to return the complete modified HTML directly
    (no placeholder).
    """
    source_block = ""
    if source_content is not None and source_content.strip():
        source_block = textwrap.dedent(
            f"""
            Contexte — article source (arrêté modifiant), d'où provient la modification :

            {source_content}

            ---

            """
        ).strip()
        source_block = source_block + "\n\n"

    article_label = f" (article {target_article_id})" if target_article_id else ""

    operand_block = ""
    if operand is not None and operand.strip():
        operand_block = f"\n\nNouveau contenu à intégrer :\n\n{operand}"

    preamble = (
        f"Vous aidez à consolider des arrêtés ICPE."
        f" Vous recevez l'article **cible**{article_label} en HTML."
    )
    output_instruction = (
        "Renvoyez UNIQUEMENT le HTML modifié complet de l'article,"
        " sans explication ni balisage markdown."
    )

    prompt_REPLACE = textwrap.dedent(
        f"""
        {preamble}
        Le sous-emplacement à remplacer est décrit en langage naturel.

        Tâche : localisez précisément le segment décrit et remplacez-le
        par le nouveau contenu fourni.
        {output_instruction}

        Article cible (HTML) :

        {target_content}

        {source_block}Description du sous-emplacement à remplacer :

        {sub_target}{operand_block}
        """
    ).strip()

    prompt_ADD = textwrap.dedent(
        f"""
        {preamble}
        L'insertion doit se faire à l'endroit décrit.

        Tâche : insérez le nouveau contenu à l'emplacement indiqué.
        {output_instruction}

        Article cible (HTML) :

        {target_content}

        {source_block}Description de l'emplacement d'insertion :

        {sub_target}{operand_block}
        """
    ).strip()

    prompt_REMOVE = textwrap.dedent(
        f"""
        {preamble}
        Le segment à supprimer est décrit en langage naturel.

        Tâche : supprimez le segment décrit.
        {output_instruction}

        Article cible (HTML) :

        {target_content}

        {source_block}Description du segment à supprimer :

        {sub_target}
        """
    ).strip()

    if operation_type == OperationType.REPLACE:
        return prompt_REPLACE
    elif operation_type == OperationType.ADD:
        return prompt_ADD
    elif operation_type == OperationType.REMOVE:
        return prompt_REMOVE


def extract_html_from_llm_response(raw: str, fallback: str) -> str:
    """Extract HTML content from an LLM response, stripping code fences if present."""
    text = raw.strip()
    if not text:
        return fallback
    m = re.search(r"```(?:html)?\s*\n([\s\S]*?)\n```", text)
    if m:
        return m.group(1).strip()
    return text
