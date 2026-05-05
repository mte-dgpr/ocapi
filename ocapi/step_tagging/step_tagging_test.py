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

from ocapi.semantic_tag_specs import OperationSpec, OperationType
from ocapi.step_tagging import step_tagging


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
        assert data.operation_type == OperationType.REPLACE
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
