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
