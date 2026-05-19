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
    PageSeparatorData,
    PageSeparatorSpec,
    SectionReferenceData,
    SectionReferenceSpec,
)
from arretify.types import DocumentType
from arretify.utils.html_semantic import css_selector
from arretify.utils.testing import BaseTestCaseHtml, assert_elements_equal

from ocapi.semantic_tag_specs import OperationData, OperationSpec

from .operands_detection import resolve_references_and_operands


class TestParseOperations(BaseTestCaseHtml):

    def test_several_references_no_operand(self) -> None:
        # Arrange
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        "Les ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(
                                parent_reference="123",
                            ),
                            contents=["paragraphes 3"],
                            reserved_data_attrs=dict(group_id="11"),
                        ),
                        " et ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(
                                parent_reference="123",
                            ),
                            contents=["4"],
                            reserved_data_attrs=dict(group_id="11"),
                        ),
                        " de l' ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(
                                parent_reference="456",
                            ),
                            contents=["article 8.5.1.1"],
                            reserved_data_attrs=dict(tag_id="123"),
                        ),
                        " de l' ",
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2008-12-10",
                            ),
                            contents=["arrêté préfectoral du 10 décembre 2008"],
                            reserved_data_attrs=dict(tag_id="456"),
                        ),
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                keyword="supprimés",
                                operand="",
                                operation_type="REMOVE",
                            ),
                            contents=[
                                "sont ",
                                self.make_tag("b", contents=["supprimés"]),
                            ],
                        ),
                    ],
                )
            ]
        )
        operation_tag = self.soup.select(css_selector(OperationSpec))[0]

        # Act
        resolve_references_and_operands(self.context, operation_tag)

        # Assert
        assert_elements_equal(
            self.soup.contents[0],
            self.make_semantic_tag(
                AlineaSpec,
                data=AlineaData(number=1),
                contents=[
                    "Les ",
                    self.make_semantic_tag(
                        SectionReferenceSpec,
                        data=SectionReferenceData(
                            parent_reference="123",
                        ),
                        contents=["paragraphes 3"],
                        reserved_data_attrs=dict(tag_id="1", group_id="11"),
                    ),
                    " et ",
                    self.make_semantic_tag(
                        SectionReferenceSpec,
                        data=SectionReferenceData(
                            parent_reference="123",
                        ),
                        contents=["4"],
                        reserved_data_attrs=dict(tag_id="2", group_id="11"),
                    ),
                    " de l' ",
                    self.make_semantic_tag(
                        SectionReferenceSpec,
                        data=SectionReferenceData(
                            parent_reference="456",
                        ),
                        contents=["article 8.5.1.1"],
                        reserved_data_attrs=dict(tag_id="123"),
                    ),
                    " de l' ",
                    self.make_semantic_tag(
                        DocumentReferenceSpec,
                        data=DocumentReferenceData(
                            type=DocumentType.arrete_prefectoral,
                            date="2008-12-10",
                        ),
                        contents=["arrêté préfectoral du 10 décembre 2008"],
                        reserved_data_attrs=dict(tag_id="456"),
                    ),
                    self.make_semantic_tag(
                        OperationSpec,
                        data=OperationData(
                            direction="rtl",
                            keyword="supprimés",
                            operand="",
                            operation_type="REMOVE",
                            references="1,2",
                        ),
                        contents=[
                            "sont ",
                            self.make_tag("b", contents=["supprimés"]),
                        ],
                    ),
                ],
            ),
        )

    def test_one_reference_one_operand(self) -> None:
        # Arrange
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        "La dernière phrase de l' ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(
                                parent_reference="123",
                            ),
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
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                has_operand=True,
                                keyword="remplacée",
                                operand="",
                                operation_type="REPLACE",
                            ),
                            contents=[
                                "est ",
                                self.make_tag("b", contents=["remplacée"]),
                                " par la disposition suivante :",
                            ],
                        ),
                        self.make_tag(
                            "q",
                            contents=[
                                (
                                    "Un relevé hebdomadaire de chacun des compteurs "
                                    "d'eau est réalisé par l'exploitant"
                                )
                            ],
                        ),
                        ".",
                    ],
                )
            ]
        )
        operation_tag = self.soup.select(css_selector(OperationSpec))[0]

        # Act
        resolve_references_and_operands(self.context, operation_tag)

        # Assert
        assert_elements_equal(
            self.soup.contents[0],
            self.make_semantic_tag(
                AlineaSpec,
                data=AlineaData(number=1),
                contents=[
                    "La dernière phrase de l' ",
                    self.make_semantic_tag(
                        SectionReferenceSpec,
                        data=SectionReferenceData(
                            parent_reference="123",
                        ),
                        contents=["article 8.1.1.2"],
                        reserved_data_attrs=dict(tag_id="1"),
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
                    self.make_semantic_tag(
                        OperationSpec,
                        data=OperationData(
                            direction="rtl",
                            has_operand=True,
                            keyword="remplacée",
                            operand="2",
                            operation_type="REPLACE",
                            references="1",
                        ),
                        contents=[
                            "est ",
                            self.make_tag("b", contents=["remplacée"]),
                            " par la disposition suivante :",
                        ],
                    ),
                    self.make_tag(
                        "q",
                        contents=[
                            (
                                "Un relevé hebdomadaire de chacun des compteurs "
                                "d'eau est réalisé par l'exploitant"
                            )
                        ],
                        reserved_data_attrs=dict(tag_id="2"),
                    ),
                    ".",
                ],
            ),
        )

    def test_with_single_document_reference(self) -> None:
        # Arrange
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        "Les prescriptions de l' ",
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2008-12-10",
                            ),
                            contents=["arrêté préfectoral du 10 décembre 2008"],
                        ),
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                keyword="abrogées",
                                operand="",
                                operation_type="REMOVE",
                            ),
                            contents=[
                                "sont ",
                                self.make_tag("b", contents=["abrogées"]),
                                " .",
                            ],
                        ),
                    ],
                )
            ]
        )
        operation_tag = self.soup.select(css_selector(OperationSpec))[0]

        # Act
        resolve_references_and_operands(self.context, operation_tag)

        # Assert
        assert_elements_equal(
            self.soup.contents[0],
            self.make_semantic_tag(
                AlineaSpec,
                data=AlineaData(number=1),
                contents=[
                    "Les prescriptions de l' ",
                    self.make_semantic_tag(
                        DocumentReferenceSpec,
                        data=DocumentReferenceData(
                            type=DocumentType.arrete_prefectoral,
                            date="2008-12-10",
                        ),
                        contents=["arrêté préfectoral du 10 décembre 2008"],
                        reserved_data_attrs=dict(tag_id="1"),
                    ),
                    self.make_semantic_tag(
                        OperationSpec,
                        data=OperationData(
                            direction="rtl",
                            keyword="abrogées",
                            operand="",
                            operation_type="REMOVE",
                            references="1",
                        ),
                        contents=[
                            "sont ",
                            self.make_tag("b", contents=["abrogées"]),
                            " .",
                        ],
                    ),
                ],
            ),
        )

    def test_with_inline_tag_between_operands(self) -> None:
        # Arrange
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        "Les dispositions de l' ",
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2008-12-10",
                            ),
                            contents=["arrêté préfectoral du 10 décembre 2008"],
                        ),
                        self.make_semantic_tag(
                            PageSeparatorSpec,
                            data=PageSeparatorData(page_index=1),
                        ),
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                has_operand=True,
                                keyword="remplacées",
                                operand="",
                                operation_type="REPLACE",
                            ),
                            contents=[
                                "sont ",
                                self.make_tag("b", contents=["remplacées"]),
                                " par la disposition suivante :",
                            ],
                        ),
                        self.make_semantic_tag(
                            PageSeparatorSpec,
                            data=PageSeparatorData(page_index=2),
                        ),
                        self.make_tag(
                            "q",
                            contents=[
                                (
                                    "Un relevé hebdomadaire de chacun des compteurs "
                                    "d'eau est réalisé par l'exploitant"
                                )
                            ],
                        ),
                    ],
                )
            ]
        )
        operation_tag = self.soup.select(css_selector(OperationSpec))[0]

        # Act
        resolve_references_and_operands(self.context, operation_tag)

        # Assert
        assert_elements_equal(
            self.soup.contents[0],
            self.make_semantic_tag(
                AlineaSpec,
                data=AlineaData(number=1),
                contents=[
                    "Les dispositions de l' ",
                    self.make_semantic_tag(
                        DocumentReferenceSpec,
                        data=DocumentReferenceData(
                            type=DocumentType.arrete_prefectoral,
                            date="2008-12-10",
                        ),
                        contents=["arrêté préfectoral du 10 décembre 2008"],
                        reserved_data_attrs=dict(tag_id="1"),
                    ),
                    self.make_semantic_tag(
                        PageSeparatorSpec,
                        data=PageSeparatorData(page_index=1),
                    ),
                    self.make_semantic_tag(
                        OperationSpec,
                        data=OperationData(
                            direction="rtl",
                            has_operand=True,
                            keyword="remplacées",
                            operand="2",
                            operation_type="REPLACE",
                            references="1",
                        ),
                        contents=[
                            "sont ",
                            self.make_tag("b", contents=["remplacées"]),
                            " par la disposition suivante :",
                        ],
                    ),
                    self.make_semantic_tag(
                        PageSeparatorSpec,
                        data=PageSeparatorData(page_index=2),
                    ),
                    self.make_tag(
                        "q",
                        contents=[
                            (
                                "Un relevé hebdomadaire de chacun des compteurs "
                                "d'eau est réalisé par l'exploitant"
                            )
                        ],
                        reserved_data_attrs=dict(tag_id="2"),
                    ),
                ],
            ),
        )

    def test_ltr_resolves_right_side_reference(self) -> None:
        """LTR operations pick up references that sit on the right."""
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="ltr",
                                keyword="annule et remplace",
                                operation_type="REPLACE",
                            ),
                            contents=[
                                "Le présent arrêté ",
                                self.make_tag("b", contents=["annule et remplace"]),
                                " l'",
                            ],
                        ),
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2011-12-20",
                            ),
                            contents=["arrêté préfectoral complémentaire du 20 décembre 2011"],
                        ),
                        " .",
                    ],
                )
            ]
        )
        operation_tag = self.soup.select(css_selector(OperationSpec))[0]

        resolve_references_and_operands(self.context, operation_tag)

        assert_elements_equal(
            self.soup.contents[0],
            self.make_semantic_tag(
                AlineaSpec,
                data=AlineaData(number=1),
                contents=[
                    self.make_semantic_tag(
                        OperationSpec,
                        data=OperationData(
                            direction="ltr",
                            keyword="annule et remplace",
                            operation_type="REPLACE",
                            references="1",
                        ),
                        contents=[
                            "Le présent arrêté ",
                            self.make_tag("b", contents=["annule et remplace"]),
                            " l'",
                        ],
                    ),
                    self.make_semantic_tag(
                        DocumentReferenceSpec,
                        data=DocumentReferenceData(
                            type=DocumentType.arrete_prefectoral,
                            date="2011-12-20",
                        ),
                        contents=["arrêté préfectoral complémentaire du 20 décembre 2011"],
                        reserved_data_attrs=dict(tag_id="1"),
                    ),
                    " .",
                ],
            ),
        )

    def test_ltr_passive_resolves_right_side_reference(self) -> None:
        """Passive LTR (Sont insérés après …) resolves the right reference."""
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="ltr",
                                keyword="insérés",
                                operation_type="ADD",
                                has_operand="true",
                            ),
                            contents=[
                                "Sont ",
                                self.make_tag("b", contents=["insérés"]),
                                " après le ",
                            ],
                        ),
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(),
                            contents=["paragraphe 4.23"],
                        ),
                        " – clôture - gardiennage, les paragraphes suivants :",
                    ],
                )
            ]
        )
        operation_tag = self.soup.select(css_selector(OperationSpec))[0]

        resolve_references_and_operands(self.context, operation_tag)

        assert_elements_equal(
            self.soup.contents[0],
            self.make_semantic_tag(
                AlineaSpec,
                data=AlineaData(number=1),
                contents=[
                    self.make_semantic_tag(
                        OperationSpec,
                        data=OperationData(
                            direction="ltr",
                            keyword="insérés",
                            operation_type="ADD",
                            has_operand="true",
                            references="1",
                        ),
                        contents=[
                            "Sont ",
                            self.make_tag("b", contents=["insérés"]),
                            " après le ",
                        ],
                    ),
                    self.make_semantic_tag(
                        SectionReferenceSpec,
                        data=SectionReferenceData(),
                        contents=["paragraphe 4.23"],
                        reserved_data_attrs=dict(tag_id="1"),
                    ),
                    " – clôture - gardiennage, les paragraphes suivants :",
                ],
            ),
        )
