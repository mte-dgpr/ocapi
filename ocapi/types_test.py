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
import pytest
from bs4 import BeautifulSoup
from pydantic import ValidationError

from .exceptions import InvalidArreteIdError, InvalidArticleIdError, InvalidFileFormatError
from .types import (
    FileType,
    NodeId,
    PermitMotifEntry,
    PermitSourceSpec,
    PermitTitleSpec,
    SectionVersionSpec,
    _BaseModelWithConfig,
    article_display_number,
    article_id_sort_tuple,
    parse_arrete_id,
    parse_article_id,
    parse_filename,
    validate_arretify_version,
)


class TestParseArticleId:

    def test_numeric_simple(self) -> None:
        assert parse_article_id("1") == "1"

    def test_numeric_dotted(self) -> None:
        assert parse_article_id("1.2") == "1.2"
        assert parse_article_id("3.1.4") == "3.1.4"

    def test_special_values(self) -> None:
        assert parse_article_id("ALL") == "ALL"
        assert parse_article_id("END") == "END"

    def test_appendix_alone(self) -> None:
        assert parse_article_id("APPENDIX") == "APPENDIX"

    def test_appendix_with_numeric_suffix(self) -> None:
        assert parse_article_id("APPENDIX:1") == "APPENDIX:1"
        assert parse_article_id("APPENDIX:1.2") == "APPENDIX:1.2"
        assert parse_article_id("APPENDIX:3.1.4") == "APPENDIX:3.1.4"

    def test_appendix_invalid_suffix(self) -> None:
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("APPENDIX:abc")
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("APPENDIX:")
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("APPENDIX_extra")

    def test_new_article_with_numeric_suffix(self) -> None:
        assert parse_article_id("NEW_ARTICLE:4.1") == "NEW_ARTICLE:4.1"
        assert parse_article_id("NEW_ARTICLE:1.2.3") == "NEW_ARTICLE:1.2.3"

    def test_new_article_invalid_suffix(self) -> None:
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("NEW_ARTICLE:abc")
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("NEW_ARTICLE:")
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("NEW_ARTICLE")

    def test_invalid_values(self) -> None:
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("")
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("abc")
        with pytest.raises(InvalidArticleIdError):
            parse_article_id("1.2.")

    def test_dashed_numbering(self) -> None:
        assert parse_article_id("1-2") == "1-2"
        assert parse_article_id("4-1-3") == "4-1-3"

    def test_roman_numeral_levels(self) -> None:
        assert parse_article_id("I") == "I"
        assert parse_article_id("IV") == "IV"
        assert parse_article_id("I.1") == "I.1"
        assert parse_article_id("2.IX") == "2.IX"
        assert parse_article_id("III-2") == "III-2"

    def test_letter_levels(self) -> None:
        assert parse_article_id("A") == "A"
        assert parse_article_id("A.3") == "A.3"
        assert parse_article_id("3.B") == "3.B"
        assert parse_article_id("a-2") == "a-2"

    def test_mixed_levels_in_prefixes(self) -> None:
        assert parse_article_id("APPENDIX:I.1") == "APPENDIX:I.1"
        assert parse_article_id("NEW_ARTICLE:A.3") == "NEW_ARTICLE:A.3"


def test_article_display_number_strips_new_article_prefix() -> None:
    assert article_display_number("NEW_ARTICLE:4.1") == "4.1"
    assert article_display_number("2.3") == "2.3"


def test_article_id_sort_tuple_orders_dotted_numbers() -> None:
    assert article_id_sort_tuple("1") < article_id_sort_tuple("2")
    assert article_id_sort_tuple("1.2") < article_id_sort_tuple("1.10")
    assert article_id_sort_tuple("NEW_ARTICLE:3.1") == article_id_sort_tuple("3.1")


def test_article_id_sort_tuple_roman_numerals() -> None:
    assert article_id_sort_tuple("IV") == (4,)
    assert article_id_sort_tuple("III") < article_id_sort_tuple("IV")
    assert article_id_sort_tuple("2.IX") == (2, 9)


def test_article_id_sort_tuple_letters_a_to_h() -> None:
    assert article_id_sort_tuple("A") == (1,)
    assert article_id_sort_tuple("H") == (8,)
    assert article_id_sort_tuple("3.B") == (3, 2)
    assert article_id_sort_tuple("a") == (1,)


def test_article_id_sort_tuple_unknown_falls_back_to_sentinel() -> None:
    assert article_id_sort_tuple("ZZZ") == (999_999,)


def test_article_id_sort_tuple_appendix_orders_by_numeric_suffix() -> None:
    assert article_id_sort_tuple("APPENDIX:2.1") < article_id_sort_tuple("APPENDIX:2.2")
    assert article_id_sort_tuple("APPENDIX:2.1") < article_id_sort_tuple("APPENDIX:10")


class TestParseArreteId:

    def test_valid_date(self) -> None:
        assert parse_arrete_id("2009-12-08") == "2009-12-08"
        assert parse_arrete_id("2023-01-31") == "2023-01-31"

    def test_invalid_too_few_parts(self) -> None:
        with pytest.raises(InvalidArreteIdError, match="Invalid date"):
            parse_arrete_id("2024-01")

    def test_invalid_too_many_parts(self) -> None:
        with pytest.raises(InvalidArreteIdError, match="Invalid date"):
            parse_arrete_id("2024-01-15-extra")

    def test_invalid_non_numeric(self) -> None:
        with pytest.raises(InvalidArreteIdError, match="Invalid date"):
            parse_arrete_id("YYYY-MM-DD")

    def test_invalid_year_too_old(self) -> None:
        with pytest.raises(InvalidArreteIdError, match="Invalid date"):
            parse_arrete_id("1800-01-15")

    def test_invalid_year_too_recent(self) -> None:
        with pytest.raises(InvalidArreteIdError, match="Invalid date"):
            parse_arrete_id("2200-01-15")

    def test_invalid_month_out_of_range(self) -> None:
        with pytest.raises(InvalidArreteIdError, match="Invalid date"):
            parse_arrete_id("2024-13-01")

    def test_invalid_day_out_of_range(self) -> None:
        with pytest.raises(InvalidArreteIdError, match="Invalid date"):
            parse_arrete_id("2024-01-45")

    def test_reversed_date_format(self) -> None:
        with pytest.raises(InvalidArreteIdError, match="Invalid date"):
            parse_arrete_id("15-01-2024")


class TestNodeIdValidation:

    def test_valid_node_id(self) -> None:
        node = NodeId(arrete_id="2009-12-08", article_id="1.2")
        assert node.arrete_id == "2009-12-08"
        assert node.article_id == "1.2"

    def test_invalid_arrete_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            NodeId(arrete_id="invalid-date", article_id="1.2")

    def test_invalid_article_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            NodeId(arrete_id="2009-12-08", article_id="invalid")

    def test_valid_appendix_article_id(self) -> None:
        node = NodeId(arrete_id="2009-12-08", article_id="APPENDIX:1.2")
        assert node.article_id == "APPENDIX:1.2"

    def test_invalid_appendix_article_id(self) -> None:
        with pytest.raises(ValidationError):
            NodeId(arrete_id="2009-12-08", article_id="APPENDIX_invalid")

    def test_valid_new_article_id(self) -> None:
        node = NodeId(arrete_id="2009-12-08", article_id="NEW_ARTICLE:4.1")
        assert node.article_id == "NEW_ARTICLE:4.1"

    def test_invalid_new_article_id(self) -> None:
        with pytest.raises(ValidationError):
            NodeId(arrete_id="2009-12-08", article_id="NEW_ARTICLE:abc")


class TestPermitSourceSpecValidation:

    def test_valid_arrete_id(self) -> None:
        spec = PermitSourceSpec(arrete_id="2023-06-15", arrete_title="AP d'autorisation")
        assert spec.arrete_id == "2023-06-15"

    def test_invalid_arrete_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            PermitSourceSpec(arrete_id="not-a-date", arrete_title="titre")

    def test_invalid_date_month_raises(self) -> None:
        with pytest.raises(ValidationError):
            PermitSourceSpec(arrete_id="2023-13-01", arrete_title="titre")


class TestPermitMotifEntryValidation:

    def test_valid_arrete_id(self) -> None:
        entry = PermitMotifEntry(arrete_id="2020-04-20", motifs=["motif 1"])
        assert entry.arrete_id == "2020-04-20"

    def test_invalid_arrete_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            PermitMotifEntry(arrete_id="invalid", motifs=["motif 1"])


class TestSectionVersionSpecValidation:

    def test_valid_spec(self) -> None:
        spec = SectionVersionSpec(
            article_id="1.2",
            is_modified=True,
            date_version="2023-06-15",
            content="contenu",
        )
        assert spec.article_id == "1.2"
        assert spec.date_version == "2023-06-15"

    def test_invalid_article_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            SectionVersionSpec(
                article_id="invalid",
                is_modified=False,
                date_version="2023-06-15",
                content="contenu",
            )

    def test_invalid_date_version_raises(self) -> None:
        with pytest.raises(ValidationError):
            SectionVersionSpec(
                article_id="1.2",
                is_modified=False,
                date_version="not-a-date",
                content="contenu",
            )

    def test_valid_appendix_article_id(self) -> None:
        spec = SectionVersionSpec(
            article_id="APPENDIX:2.1",
            is_modified=False,
            date_version="2020-01-01",
            content="contenu",
        )
        assert spec.article_id == "APPENDIX:2.1"

    def test_valid_special_article_id_all(self) -> None:
        spec = SectionVersionSpec(
            article_id="ALL",
            is_modified=False,
            date_version="2020-01-01",
            content="contenu",
        )
        assert spec.article_id == "ALL"


def test_serialize_model_excludes_none() -> None:
    class TestModel(_BaseModelWithConfig):
        a: int
        b: str | None = None
        c: float | None = None

    model = TestModel(a=10, b=None, c=3.14)
    serialized_default = model.model_dump()
    assert "b" in serialized_default
    assert serialized_default["b"] is None

    serialized_no_none = model.model_dump(exclude_none=True)
    assert "b" not in serialized_no_none
    assert "c" in serialized_no_none
    assert serialized_no_none["c"] == 3.14


class TestParseFilename:
    """Tests pour la fonction parse_filename."""

    def test_parse_valid_ap_autorisation(self) -> None:
        arrete_id, file_type = parse_filename("2009-12-08_ap d'autorisation_description.html")
        assert arrete_id == "2009-12-08"
        assert file_type == FileType.AP_AUTORISATION

    def test_parse_valid_ap_prescriptions_complementaires(self) -> None:
        arrete_id, file_type = parse_filename(
            "2014-01-09_ap prescriptions complémentaires_details.html"
        )
        assert arrete_id == "2014-01-09"
        assert file_type == FileType.AP_COMPLEMENTAIRE

    def test_parse_valid_arrete_prefectoral(self) -> None:
        arrete_id, file_type = parse_filename(
            "2020-04-20_arrêté préfectoral_portant autorisation.html"
        )
        assert arrete_id == "2020-04-20"
        assert file_type == FileType.ARRETE_PREFECTORAL

    def test_parse_apc_abbreviation_returns_autre(self) -> None:
        arrete_id, file_type = parse_filename("2023-02-22_apc_modification.html")
        assert arrete_id == "2023-02-22"
        assert file_type == FileType.AUTRE

    def test_parse_ap_abbreviation_returns_autre(self) -> None:
        arrete_id, file_type = parse_filename("2021-09-24_ap_nouveau document.html")
        assert arrete_id == "2021-09-24"
        assert file_type == FileType.AUTRE

    def test_parse_unknown_file_type(self) -> None:
        arrete_id, file_type = parse_filename("2024-01-15_type_inconnu_description.html")
        assert arrete_id == "2024-01-15"
        assert file_type == FileType.AUTRE

    def test_parse_invalid_no_html_extension(self) -> None:
        with pytest.raises(InvalidFileFormatError, match=r"\.html extension"):
            parse_filename("2024-01-15_ap_document.pdf")

    def test_parse_invalid_date_format(self) -> None:
        with pytest.raises(InvalidFileFormatError, match="Invalid date"):
            parse_filename("2024-13-45_ap_document.html")

    def test_parse_invalid_date_not_iso(self) -> None:
        with pytest.raises(InvalidFileFormatError, match="Invalid date"):
            parse_filename("15-01-2024_ap_document.html")

    def test_parse_date_only_format(self) -> None:
        arrete_id, file_type = parse_filename("2024-01-15.html")
        assert arrete_id == "2024-01-15"
        assert file_type == FileType.AUTRE

    def test_parse_invalid_missing_parts_not_a_date(self) -> None:
        with pytest.raises(InvalidFileFormatError, match="Invalid format"):
            parse_filename("not-a-valid-name.html")

    def test_parse_complex_filename(self) -> None:
        filename = (
            "2023-02-22_ap prescriptions complémentaires_"
            "13450_2023_02_22_B+T energie_APCmod_.pdf.html"
        )
        arrete_id, file_type = parse_filename(filename)
        assert arrete_id == "2023-02-22"
        assert file_type == FileType.AP_COMPLEMENTAIRE

    def test_parse_real_example_1(self) -> None:
        arrete_id, file_type = parse_filename(
            "2009-12-08_ap d'autorisation_20091208_APpub_UniteRegenerationHuilesUsagees (1).html"
        )
        assert arrete_id == "2009-12-08"
        assert file_type == FileType.AP_AUTORISATION

    def test_parse_real_example_2(self) -> None:
        filename = (
            "2023-12-04_ap prescriptions complémentaires_"
            "AP du 04.12.2023_OSILUB à Gonfreville-l'Orcher.html"
        )
        arrete_id, file_type = parse_filename(filename)
        assert arrete_id == "2023-12-04"
        assert file_type == FileType.AP_COMPLEMENTAIRE


class TestValidateArretifyVersion:
    """Tests pour la validation de la version Arrêtify."""

    def test_validate_version_0_2_0(self) -> None:
        soup = BeautifulSoup(
            '<html><body data-arretify_version="0.2.0"><p>Contenu</p></body></html>',
            "html.parser",
        )
        validate_arretify_version(soup, "test.html")

    def test_validate_version_0_2_1(self) -> None:
        soup = BeautifulSoup(
            '<html><body data-arretify_version="0.2.1"><p>Contenu</p></body></html>',
            "html.parser",
        )
        validate_arretify_version(soup, "test.html")

    def test_validate_version_0_2_99(self) -> None:
        soup = BeautifulSoup(
            '<html><body data-arretify_version="0.2.99"><p>Contenu</p></body></html>',
            "html.parser",
        )
        validate_arretify_version(soup, "test.html")

    def test_validate_version_missing_raises_error(self) -> None:
        soup = BeautifulSoup("<html><body><p>Contenu</p></body></html>", "html.parser")
        with pytest.raises(InvalidFileFormatError, match="Missing Arrêtify version"):
            validate_arretify_version(soup, "test.html")

    def test_validate_version_0_1_0_raises_error(self) -> None:
        soup = BeautifulSoup(
            '<html><body data-arretify_version="0.1.0"><p>Contenu</p></body></html>',
            "html.parser",
        )
        with pytest.raises(InvalidFileFormatError, match="Unsupported Arrêtify version"):
            validate_arretify_version(soup, "test.html")

    def test_validate_version_1_0_0_raises_error(self) -> None:
        soup = BeautifulSoup(
            '<html><body data-arretify_version="1.0.0"><p>Contenu</p></body></html>',
            "html.parser",
        )
        with pytest.raises(InvalidFileFormatError, match="Unsupported Arrêtify version"):
            validate_arretify_version(soup, "test.html")

    def test_validate_invalid_version_format_raises_error(self) -> None:
        soup = BeautifulSoup(
            '<html><body data-arretify_version="invalid"><p>Contenu</p></body></html>',
            "html.parser",
        )
        with pytest.raises(InvalidFileFormatError, match="Unsupported Arrêtify version"):
            validate_arretify_version(soup, "test.html")

    def test_validate_no_body_tag_raises_error(self) -> None:
        soup = BeautifulSoup("<html><p>Contenu sans body</p></html>", "html.parser")
        with pytest.raises(InvalidFileFormatError, match="Invalid HTML document"):
            validate_arretify_version(soup, "test.html")


def test_permit_title_aiot_code_is_stored() -> None:
    assert PermitTitleSpec(aiot_code="0001").aiot_code == "0001"


def test_permit_title_aiot_code_can_be_none() -> None:
    assert PermitTitleSpec(aiot_code=None).aiot_code is None
