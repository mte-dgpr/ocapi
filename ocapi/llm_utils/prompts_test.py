#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
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
from ocapi.llm_utils import parse_llm_json_list_response, query_llm_for_subtarget
from ocapi.types import OperationType


def test_parse_llm_json_list_response_valid() -> None:
    raw_response = """
    [
        {
            "modification_type": "REPLACE",
            "source_article": "2.1.3",
            "target_arrete": "15/08/2023",
            "target_article": "3.2.1",
            "target_in_article": "le paragraphe concernant les horaires",
            "new_content_ref": {
                "start_marker": "Le nouveau texte commence ici...",
                "end_marker": "...et se termine ici."
            }
        },
        {
            "modification_type": "ADD",
            "source_article": null,
            "target_arrete": "15/08/2023",
            "target_article": "NEW_ARTICLE:4.1",
            "target_in_article": "à la fin de l'article 4.1",
            "new_content_ref": {
                "start_marker": "Le texte ajouté commence ici...",
                "end_marker": "...et se termine ici."
            }
        }
    ]
    Merci.
    """
    result = parse_llm_json_list_response(raw_response)
    assert result == [
        {
            "modification_type": "REPLACE",
            "source_article": "2.1.3",
            "target_arrete": "15/08/2023",
            "target_article": "3.2.1",
            "target_in_article": "le paragraphe concernant les horaires",
            "new_content_ref": {
                "start_marker": "Le nouveau texte commence ici...",
                "end_marker": "...et se termine ici.",
            },
        },
        {
            "modification_type": "ADD",
            "source_article": None,
            "target_arrete": "15/08/2023",
            "target_article": "NEW_ARTICLE:4.1",
            "target_in_article": "à la fin de l'article 4.1",
            "new_content_ref": {
                "start_marker": "Le texte ajouté commence ici...",
                "end_marker": "...et se termine ici.",
            },
        },
    ]


def test_parse_llm_json_list_response_no_json() -> None:
    result = parse_llm_json_list_response("Aucune opération détectée.")
    assert result == []


def test_query_llm_for_subtarget_includes_source_article_when_provided() -> None:
    """Source HTML is embedded in the prompt when ``source_content`` is set."""
    prompt = query_llm_for_subtarget(
        OperationType.REPLACE,
        "<section>target</section>",
        "la septième ligne du tableau",
        source_content="<section>source article</section>",
    )
    assert "source article" in prompt
    assert "target" in prompt
    assert "septième ligne" in prompt


def test_query_llm_for_subtarget_omits_source_block_when_empty() -> None:
    prompt = query_llm_for_subtarget(
        OperationType.REPLACE,
        "<section>target</section>",
        "sous-emplacement",
        source_content=None,
    )
    assert "Contexte — article source" not in prompt
    assert "target" in prompt
