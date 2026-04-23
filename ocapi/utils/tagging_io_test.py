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
from arretify.semantic_tag_specs import (
    AlineaData,
    AlineaSpec,
    DocumentReferenceData,
    DocumentReferenceSpec,
    SectionReferenceData,
    SectionReferenceSpec,
)
from arretify.types import DocumentType
from arretify.utils.testing import BaseTestCaseHtml
from bs4 import Tag

from ocapi.step_tagging import step_tagging
from ocapi.types import RawOperationType
from ocapi.utils.tagging_io import extract_operations_from_tagged_soup


def _build_replace_alinea(case: BaseTestCaseHtml) -> Tag:
    return case.make_semantic_tag(  # type: ignore[no-any-return]
        AlineaSpec,
        data=AlineaData(number=1),
        contents=[
            "La dernière phrase de l' ",
            case.make_semantic_tag(
                SectionReferenceSpec,
                data=SectionReferenceData(parent_reference="123"),
                contents=["article 8.1.1.2"],
            ),
            " de l' ",
            case.make_semantic_tag(
                DocumentReferenceSpec,
                data=DocumentReferenceData(
                    type=DocumentType.arrete_prefectoral,
                    date="2008-12-10",
                ),
                contents=["arrêté préfectoral du 10 décembre 2008"],
                reserved_data_attrs=dict(tag_id="123"),
            ),
            " est remplacée par la disposition suivante :",
            case.make_tag(
                "q",
                contents=["Un relevé hebdomadaire est réalisé par l'exploitant"],
            ),
        ],
    )


def _build_add_alinea(case: BaseTestCaseHtml) -> Tag:
    return case.make_semantic_tag(  # type: ignore[no-any-return]
        AlineaSpec,
        data=AlineaData(number=1),
        contents=[
            "L' ",
            case.make_semantic_tag(
                SectionReferenceSpec,
                data=SectionReferenceData(parent_reference="321"),
                contents=["article 8 .6"],
            ),
            " suivant de l' ",
            case.make_semantic_tag(
                DocumentReferenceSpec,
                data=DocumentReferenceData(
                    type=DocumentType.arrete_prefectoral,
                    date="2010-05-11",
                ),
                contents=["arrêté préfectoral du 11 mai 2010"],
                reserved_data_attrs=dict(tag_id="321"),
            ),
            " est ajouté",
        ],
    )


def _build_delete_alinea(case: BaseTestCaseHtml) -> Tag:
    return case.make_semantic_tag(  # type: ignore[no-any-return]
        AlineaSpec,
        data=AlineaData(number=1),
        contents=[
            "Le dernier alinéa de l' ",
            case.make_semantic_tag(
                SectionReferenceSpec,
                data=SectionReferenceData(parent_reference="555"),
                contents=["article 1 .2 .2"],
            ),
            " de l' ",
            case.make_semantic_tag(
                DocumentReferenceSpec,
                data=DocumentReferenceData(
                    type=DocumentType.arrete_prefectoral,
                    date="2005-02-15",
                ),
                contents=["arrêté préfectoral du 15 février 2005"],
                reserved_data_attrs=dict(tag_id="555"),
            ),
            " est abrogé.",
        ],
    )


class TestExtractOperationsFromTaggedSoup(BaseTestCaseHtml):  # type: ignore[misc]
    def test_replace_operation(self) -> None:
        self.soup_extend([_build_replace_alinea(self)])
        step_tagging(self.context)

        ops = extract_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 1
        op = ops[0]
        assert op.operation_type == RawOperationType.REPLACE
        assert op.target_arrete == "2008-12-10"
        assert op.target_article == "article 8.1.1.2"
        assert op.source_article is None
        assert op.failure_message is None

    def test_add_operation(self) -> None:
        self.soup_extend([_build_add_alinea(self)])
        step_tagging(self.context)

        ops = extract_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 1
        assert ops[0].operation_type == RawOperationType.ADD
        assert ops[0].target_arrete == "2010-05-11"
        assert ops[0].target_article == "article 8 .6"

    def test_delete_operation(self) -> None:
        self.soup_extend([_build_delete_alinea(self)])
        step_tagging(self.context)

        ops = extract_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 1
        assert ops[0].operation_type == RawOperationType.REMOVE
        assert ops[0].target_arrete == "2005-02-15"
        assert ops[0].target_article == "article 1 .2 .2"

    def test_no_tags_returns_empty(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=["Simple prose sans aucune référence."],
                )
            ]
        )
        step_tagging(self.context)

        ops = extract_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert ops == []
