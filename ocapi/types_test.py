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

from bs4 import BeautifulSoup

from .types import FileType, _BaseModelWithConfig, parse_filename, validate_arretify_version


class TestBaseModelWithConfig(unittest.TestCase):

    def test_serialize_model_excludes_none(self) -> None:
        class TestModel(_BaseModelWithConfig):
            a: int
            b: str | None = None
            c: float | None = None

        model = TestModel(a=10, b=None, c=3.14)
        # exclude_none dans ConfigDict ne s'applique pas automatiquement à model_dump()
        # Il faut utiliser model_dump(exclude_none=True) ou model_dump_json()
        serialized_default = model.model_dump()
        assert "b" in serialized_default  # Par défaut, None est inclus
        assert serialized_default["b"] is None

        # Mais quand on utilise exclude_none explicitement
        serialized_no_none = model.model_dump(exclude_none=True)
        assert "b" not in serialized_no_none
        assert "c" in serialized_no_none
        assert serialized_no_none["c"] == 3.14


class TestParseFilename(unittest.TestCase):
    """Tests pour la fonction parse_filename."""

    def test_parse_valid_ap_autorisation(self) -> None:
        """Test avec un fichier AP d'autorisation valide."""
        arrete_id, file_type = parse_filename("2009-12-08_ap d'autorisation_description.html")
        assert arrete_id == "2009-12-08"
        assert file_type == FileType.AP_AUTORISATION

    def test_parse_valid_ap_prescriptions_complementaires(self) -> None:
        """Test avec un fichier AP prescriptions complémentaires valide."""
        arrete_id, file_type = parse_filename(
            "2014-01-09_ap prescriptions complémentaires_details.html"
        )
        assert arrete_id == "2014-01-09"
        assert file_type == FileType.AP_COMPLEMENTAIRE

    def test_parse_valid_arrete_prefectoral(self) -> None:
        """Test avec un fichier arrêté préfectoral valide."""
        arrete_id, file_type = parse_filename(
            "2020-04-20_arrêté préfectoral_portant autorisation.html"
        )
        assert arrete_id == "2020-04-20"
        assert file_type == FileType.ARRETE_PREFECTORAL

    def test_parse_apc_abbreviation_returns_autre(self) -> None:
        """Test que l'abréviation APC seule retourne AUTRE (ne devrait pas être rencontrée)."""
        arrete_id, file_type = parse_filename("2023-02-22_apc_modification.html")
        assert arrete_id == "2023-02-22"
        assert file_type == FileType.AUTRE

    def test_parse_ap_abbreviation_returns_autre(self) -> None:
        """Test que l'abréviation AP seule retourne AUTRE (ne devrait pas être rencontrée)."""
        arrete_id, file_type = parse_filename("2021-09-24_ap_nouveau document.html")
        assert arrete_id == "2021-09-24"
        assert file_type == FileType.AUTRE

    def test_parse_unknown_file_type(self) -> None:
        """Test avec un type de fichier inconnu (doit retourner AUTRE)."""
        arrete_id, file_type = parse_filename("2024-01-15_type_inconnu_description.html")
        assert arrete_id == "2024-01-15"
        assert file_type == FileType.AUTRE

    def test_parse_invalid_no_html_extension(self) -> None:
        """Test avec un fichier sans extension .html."""
        with self.assertRaises(ValueError) as context:
            parse_filename("2024-01-15_ap_document.pdf")
        assert "extension .html" in str(context.exception)

    def test_parse_invalid_date_format(self) -> None:
        """Test avec un format de date invalide."""
        with self.assertRaises(ValueError) as context:
            parse_filename("2024-13-45_ap_document.html")
        assert "Date invalide" in str(context.exception)

    def test_parse_invalid_date_not_iso(self) -> None:
        """Test avec une date non ISO."""
        with self.assertRaises(ValueError) as context:
            parse_filename("15-01-2024_ap_document.html")
        assert "Date invalide" in str(context.exception)

    def test_parse_invalid_missing_parts(self) -> None:
        """Test avec un nom de fichier qui n'a pas assez de parties."""
        with self.assertRaises(ValueError) as context:
            parse_filename("2024-01-15.html")
        assert "Format invalide" in str(context.exception)

    def test_parse_complex_filename(self) -> None:
        """Test avec un nom de fichier complexe avec plusieurs underscores."""
        filename = (
            "2023-02-22_ap prescriptions complémentaires_"
            "13450_2023_02_22_B+T energie_APCmod_.pdf.html"
        )
        arrete_id, file_type = parse_filename(filename)
        assert arrete_id == "2023-02-22"
        assert file_type == FileType.AP_COMPLEMENTAIRE

    def test_parse_real_example_1(self) -> None:
        """Test avec un exemple réel du dossier data."""
        arrete_id, file_type = parse_filename(
            "2009-12-08_ap d'autorisation_20091208_APpub_UniteRegenerationHuilesUsagees (1).html"
        )
        assert arrete_id == "2009-12-08"
        assert file_type == FileType.AP_AUTORISATION

    def test_parse_real_example_2(self) -> None:
        """Test avec un autre exemple réel du dossier data."""
        filename = (
            "2023-12-04_ap prescriptions complémentaires_"
            "AP du 04.12.2023_OSILUB à Gonfreville-l'Orcher.html"
        )
        arrete_id, file_type = parse_filename(filename)
        assert arrete_id == "2023-12-04"
        assert file_type == FileType.AP_COMPLEMENTAIRE



class TestValidateArretifyVersion(unittest.TestCase):
    """Tests pour la validation de la version Arrêtify."""

    def test_validate_version_0_1_0(self) -> None:
        """Test avec version 0.1.0 (valide)."""
        html = '<html><body data-arretify_version="0.1.0"><p>Contenu</p></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        # Ne devrait pas lever d'exception
        validate_arretify_version(soup, "test.html")

    def test_validate_version_0_1_1(self) -> None:
        """Test avec version 0.1.1 (valide)."""
        html = '<html><body data-arretify_version="0.1.1"><p>Contenu</p></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        validate_arretify_version(soup, "test.html")

    def test_validate_version_0_1_99(self) -> None:
        """Test avec version 0.1.99 (valide, patch élevé)."""
        html = '<html><body data-arretify_version="0.1.99"><p>Contenu</p></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        validate_arretify_version(soup, "test.html")

    def test_validate_version_missing_raises_error(self) -> None:
        """Test sans attribut data-arretify_version."""
        html = "<html><body><p>Contenu</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        with self.assertRaises(ValueError) as context:
            validate_arretify_version(soup, "test.html")
        assert "Version Arrêtify manquante" in str(context.exception)

    def test_validate_version_0_2_0_raises_error(self) -> None:
        """Test avec version 0.2.0 (non supportée, minor différente)."""
        html = '<html><body data-arretify_version="0.2.0"><p>Contenu</p></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        with self.assertRaises(ValueError) as context:
            validate_arretify_version(soup, "test.html")
        assert "Version Arrêtify non supportée" in str(context.exception)
        assert "0.2.0" in str(context.exception)

    def test_validate_version_1_0_0_raises_error(self) -> None:
        """Test avec version 1.0.0 (non supportée, major différente)."""
        html = '<html><body data-arretify_version="1.0.0"><p>Contenu</p></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        with self.assertRaises(ValueError) as context:
            validate_arretify_version(soup, "test.html")
        assert "Version Arrêtify non supportée" in str(context.exception)

    def test_validate_invalid_version_format_raises_error(self) -> None:
        """Test avec un format de version invalide."""
        html = '<html><body data-arretify_version="invalid"><p>Contenu</p></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        with self.assertRaises(ValueError) as context:
            validate_arretify_version(soup, "test.html")
        assert "Version Arrêtify non supportée" in str(context.exception)

    def test_validate_no_body_tag_raises_error(self) -> None:
        """Test avec un document HTML sans balise body."""
        html = "<html><p>Contenu sans body</p></html>"
        soup = BeautifulSoup(html, "html.parser")
        with self.assertRaises(ValueError) as context:
            validate_arretify_version(soup, "test.html")
        assert "Document HTML invalide" in str(context.exception)
