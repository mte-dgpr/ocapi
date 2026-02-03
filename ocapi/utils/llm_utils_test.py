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
import unittest

from ocapi.utils.llm_utils import parse_llm_json_list_response


class TestLLMUtils(unittest.TestCase):
    def test_parse_ops_llm_response_valid(self) -> None:
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
        expected_output: list[dict[str, object]] = [
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
        result = parse_llm_json_list_response(raw_response)
        assert result == expected_output

    def test_parse_ops_llm_response_no_json(self) -> None:
        raw_response = "Aucune opération détectée."
        expected_output: list[dict[str, object]] = []
        result = parse_llm_json_list_response(raw_response)
        assert result == expected_output
