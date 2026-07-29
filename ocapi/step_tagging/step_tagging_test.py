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
from arretify.semantic_tag_specs import (
    AlineaData,
    AlineaSpec,
    DocumentReferenceData,
    DocumentReferenceSpec,
    SectionReferenceData,
    SectionReferenceSpec,
)
from arretify.types import DocumentType
from arretify.utils.html_semantic import css_selector, get_semantic_tag_data
from arretify.utils.testing import BaseTestCaseHtml

from ocapi.semantic_tag_specs import OperationData, OperationSpec
from ocapi.step_tagging import step_tagging
from ocapi.types import RawOperationType


class TestStepTagging(BaseTestCaseHtml):
    def test_tags_replace_operation_and_resolves_operand(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        "La dernière phrase de l' ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(parent_reference="123"),
                            contents=["article 8.1.1.2"],
                        ),
                        " de l' ",
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2008-12-10",
                            ),
                            contents=["arrêté préfectoral du 10 décembre 2008"],
                            reserved_data_attrs=dict(tag_id="123"),
                        ),
                        " est remplacée par la disposition suivante :",
                        self.make_tag(
                            "q",
                            contents=[
                                (
                                    "Un relevé hebdomadaire de chacun des compteurs d'eau "
                                    "est réalisé par l'exploitant"
                                )
                            ],
                        ),
                    ],
                )
            ]
        )

        step_tagging(self.context)

        operation_tags = self.soup.select(css_selector(OperationSpec))
        assert len(operation_tags) == 1
        data = get_semantic_tag_data(OperationSpec, operation_tags[0])
        assert data.operation_type == RawOperationType.REPLACE
        assert data.keyword == "remplacée"
        assert data.direction == "rtl"
        assert data.references
        assert data.operand

    def test_noop_when_no_references(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=["Cet alinéa ne contient aucune référence."],
                )
            ]
        )

        step_tagging(self.context)

        assert self.soup.select(css_selector(OperationSpec)) == []

    def test_retags_preexisting_operation_span_with_nested_markup(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                keyword="insérés",
                                operation_type="ADD",
                                has_operand="true",
                            ),
                            contents=[
                                "Sont ",
                                self.make_tag("b", contents=["insérés"]),
                                " après le ",
                                self.make_semantic_tag(
                                    SectionReferenceSpec,
                                    data=SectionReferenceData(),
                                    contents=["paragraphe 4.23"],
                                ),
                                ", les paragraphes suivants :",
                            ],
                        ),
                        self.make_tag("q", contents=["Contenu à insérer."]),
                    ],
                )
            ]
        )

        step_tagging(self.context)

        operation_tags = self.soup.select(css_selector(OperationSpec))
        assert len(operation_tags) == 1
        data = get_semantic_tag_data(OperationSpec, operation_tags[0])
        assert data.operation_type == RawOperationType.ADD
        assert data.direction == "ltr"
        assert data.references
        assert data.operand

    def test_is_idempotent_on_already_tagged_html(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        "La dernière phrase de l' ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(parent_reference="123"),
                            contents=["article 8.1.1.2"],
                        ),
                        " de l' ",
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2008-12-10",
                            ),
                            contents=["arrêté préfectoral du 10 décembre 2008"],
                            reserved_data_attrs=dict(tag_id="123"),
                        ),
                        " est remplacée par la disposition suivante :",
                        self.make_tag("q", contents=["Un nouveau contenu."]),
                    ],
                )
            ]
        )

        step_tagging(self.context)
        first_run_data = [
            get_semantic_tag_data(OperationSpec, tag).model_dump(mode="json")
            for tag in self.soup.select(css_selector(OperationSpec))
        ]

        step_tagging(self.context)
        second_run_data = [
            get_semantic_tag_data(OperationSpec, tag).model_dump(mode="json")
            for tag in self.soup.select(css_selector(OperationSpec))
        ]

        assert first_run_data == second_run_data
