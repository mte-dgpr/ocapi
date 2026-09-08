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
    SectionData,
    SectionReferenceData,
    SectionReferenceSpec,
    SectionSpec,
)
from arretify.types import DocumentType, ProtectedTag, SectionType
from arretify.utils.testing import BaseTestCaseHtml

from ocapi.semantic_tag_specs import OperationData, OperationSpec
from ocapi.step_tagging import step_tagging
from ocapi.types import OperationOrigin, OperationType, RawOperationType
from ocapi.utils.tagging_io import (
    extract_operations_from_tagged_soup,
    extract_raw_operations_from_tagged_soup,
)


def _build_replace_alinea(case: BaseTestCaseHtml) -> ProtectedTag:
    return case.make_semantic_tag(
        AlineaSpec,
        data=AlineaData(number=1),
        contents=[
            "La dernière phrase de l' ",
            case.make_semantic_tag(
                SectionReferenceSpec,
                data=SectionReferenceData(parent_reference="123", start_num="8.1.1.2"),
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


def _build_add_alinea(case: BaseTestCaseHtml) -> ProtectedTag:
    return case.make_semantic_tag(
        AlineaSpec,
        data=AlineaData(number=1),
        contents=[
            "L' ",
            case.make_semantic_tag(
                SectionReferenceSpec,
                data=SectionReferenceData(parent_reference="321", start_num="8.6"),
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


def _build_delete_alinea(case: BaseTestCaseHtml) -> ProtectedTag:
    return case.make_semantic_tag(
        AlineaSpec,
        data=AlineaData(number=1),
        contents=[
            "Le dernier alinéa de l' ",
            case.make_semantic_tag(
                SectionReferenceSpec,
                data=SectionReferenceData(parent_reference="555", start_num="1.2.2"),
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


class TestExtractOperationsFromTaggedSoup(BaseTestCaseHtml):
    def test_replace_operation(self) -> None:
        self.soup_extend([_build_replace_alinea(self)])
        step_tagging(self.context)

        ops = extract_raw_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 1
        op = ops[0]
        assert op.operation_type == RawOperationType.REPLACE
        assert op.origin == OperationOrigin.REGEX
        assert op.target_arrete == "2008-12-10"
        assert op.target_article == "8.1.1.2"
        assert op.source_article is None
        assert op.failure_message is None

    def test_add_operation(self) -> None:
        self.soup_extend([_build_add_alinea(self)])
        step_tagging(self.context)

        ops = extract_raw_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 1
        assert ops[0].operation_type == RawOperationType.ADD
        assert ops[0].origin == OperationOrigin.REGEX
        assert ops[0].target_arrete == "2010-05-11"
        assert ops[0].target_article == "8.6"

    def test_delete_operation(self) -> None:
        self.soup_extend([_build_delete_alinea(self)])
        step_tagging(self.context)

        ops = extract_raw_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 1
        assert ops[0].operation_type == RawOperationType.REMOVE
        assert ops[0].origin == OperationOrigin.REGEX
        assert ops[0].target_arrete == "2005-02-15"
        assert ops[0].target_article == "1.2.2"

    def test_paragraph_subtarget_uses_reference_tree(self) -> None:
        """Paragraphes referenced through their parent article become sub_target."""
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        "Les ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(parent_reference="123"),
                            contents=["paragraphes 3"],
                            reserved_data_attrs=dict(tag_id="1", group_id="11"),
                        ),
                        " et ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(parent_reference="123"),
                            contents=["4"],
                            reserved_data_attrs=dict(tag_id="2", group_id="11"),
                        ),
                        " de l' ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(parent_reference="456", start_num="8.5.1.1"),
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
                        " ",
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                keyword="supprimés",
                                operation_type="REMOVE",
                                references=["1", "2"],
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

        ops = extract_raw_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 1
        op = ops[0]
        assert op.operation_type == RawOperationType.REMOVE
        assert op.target_arrete == "2008-12-10"
        assert op.target_article == "8.5.1.1"
        assert op.sub_target == "paragraphes 3 et 4"

    def test_multiple_articles_split_into_separate_operations(self) -> None:
        """References targeting several articles emit one operation per article."""
        self.soup_extend(
            [
                self.make_semantic_tag(
                    AlineaSpec,
                    data=AlineaData(number=1),
                    contents=[
                        "Les ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(parent_reference="999", start_num="5"),
                            contents=["article 5"],
                            reserved_data_attrs=dict(tag_id="1", group_id="g1"),
                        ),
                        " et ",
                        self.make_semantic_tag(
                            SectionReferenceSpec,
                            data=SectionReferenceData(parent_reference="999", start_num="6"),
                            contents=["article 6"],
                            reserved_data_attrs=dict(tag_id="2", group_id="g1"),
                        ),
                        " de l' ",
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2008-12-10",
                            ),
                            contents=["arrêté préfectoral du 10 décembre 2008"],
                            reserved_data_attrs=dict(tag_id="999"),
                        ),
                        " ",
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                keyword="supprimés",
                                operation_type="REMOVE",
                                references=["1", "2"],
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

        ops = extract_raw_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 2
        assert all(op.operation_type == RawOperationType.REMOVE for op in ops)
        assert all(op.target_arrete == "2008-12-10" for op in ops)
        assert [op.target_article for op in ops] == ["5", "6"]
        assert all(op.sub_target is None for op in ops)

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

        ops = extract_raw_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert ops == []

    def test_extract_operations_builds_replace_operation(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    SectionSpec,
                    data=SectionData(number="1", type=SectionType.ARTICLE),
                    contents=[_build_replace_alinea(self)],
                )
            ]
        )
        step_tagging(self.context)

        next_id = iter(["10"])
        ops = extract_operations_from_tagged_soup(
            self.soup,
            arrete_id="2021-01-01",
            next_operation_id=lambda: next(next_id),
        )

        assert len(ops) == 1
        op = ops[0]
        assert op.id == "10"
        assert op.origin == OperationOrigin.REGEX
        assert op.operation_type == OperationType.REPLACE
        assert op.target_id.arrete_id == "2008-12-10"
        assert op.target_id.article_id == "8.1.1.2"
        assert op.operand is not None
        assert "Un relevé hebdomadaire est réalisé" in op.operand
        assert op.sub_target is not None
        assert op.sub_target.type.value == "FULL_SECTION"
        assert op.sub_target.description == "ALL"

    def test_extract_operations_keeps_all_target_without_implicit_subtarget(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    SectionSpec,
                    data=SectionData(number="1", type=SectionType.ARTICLE),
                    contents=[_build_replace_alinea(self)],
                )
            ]
        )
        step_tagging(self.context)

        next_id = iter(["10"])
        ops = extract_operations_from_tagged_soup(
            self.soup,
            arrete_id="2021-01-01",
            next_operation_id=lambda: next(next_id),
        )

        op = ops[0]
        assert op.target_id.article_id != "ALL"
        assert op.sub_target is not None
        assert op.sub_target.type.value == "FULL_SECTION"
        assert op.sub_target.description == "ALL"

    def test_extract_operations_builds_add_operation_with_operand(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    SectionSpec,
                    data=SectionData(number="4", type=SectionType.ARTICLE),
                    contents=[
                        self.make_semantic_tag(
                            AlineaSpec,
                            data=AlineaData(number=1),
                            contents=[
                                "L' ",
                                self.make_semantic_tag(
                                    SectionReferenceSpec,
                                    data=SectionReferenceData(
                                        parent_reference="77", start_num="9.4"
                                    ),
                                    contents=["article 9 .4"],
                                ),
                                " de l' ",
                                self.make_semantic_tag(
                                    DocumentReferenceSpec,
                                    data=DocumentReferenceData(
                                        type=DocumentType.arrete_prefectoral,
                                        date="2012-03-01",
                                    ),
                                    contents=["arrêté préfectoral du 1 mars 2012"],
                                    reserved_data_attrs=dict(tag_id="77"),
                                ),
                                " est complétée par les dispositions suivantes :",
                                self.make_tag("q", contents=["Un alinéa est ajouté."]),
                            ],
                        )
                    ],
                )
            ]
        )
        step_tagging(self.context)

        next_id = iter(["11"])
        ops = extract_operations_from_tagged_soup(
            self.soup,
            arrete_id="2021-01-01",
            next_operation_id=lambda: next(next_id),
        )

        assert len(ops) == 1
        op = ops[0]
        assert op.id == "11"
        assert op.origin == OperationOrigin.REGEX
        assert op.operation_type == OperationType.ADD
        assert op.source_id.article_id == "4"
        assert op.target_id.arrete_id == "2012-03-01"
        assert op.target_id.article_id == "9.4"
        assert op.operand is not None
        assert "Un alinéa est ajouté" in op.operand
        assert op.sub_target is not None
        assert op.sub_target.type.value == "FULL_SECTION"
        assert op.sub_target.description == "ALL"

    def test_extract_operations_builds_remove_operation_without_operand(self) -> None:
        self.soup_extend(
            [
                self.make_semantic_tag(
                    SectionSpec,
                    data=SectionData(number="6", type=SectionType.ARTICLE),
                    contents=[_build_delete_alinea(self)],
                )
            ]
        )
        step_tagging(self.context)

        next_id = iter(["12"])
        ops = extract_operations_from_tagged_soup(
            self.soup,
            arrete_id="2021-01-01",
            next_operation_id=lambda: next(next_id),
        )

        assert len(ops) == 1
        op = ops[0]
        assert op.id == "12"
        assert op.origin == OperationOrigin.REGEX
        assert op.operation_type == OperationType.REMOVE
        assert op.source_id.article_id == "6"
        assert op.target_id.arrete_id == "2005-02-15"
        assert op.target_id.article_id == "1.2.2"
        assert op.operand is None

    def test_range_reference_expands_to_one_operation_per_target_article(self) -> None:
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
                                parent_reference="doc-1", start_num="8.6", end_num="8.8"
                            ),
                            contents=["articles 8.6 à 8.8"],
                            reserved_data_attrs=dict(tag_id="sec-1"),
                        ),
                        " de l' ",
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2010-05-11",
                            ),
                            contents=["arrêté préfectoral du 11 mai 2010"],
                            reserved_data_attrs=dict(tag_id="doc-1"),
                        ),
                        " ",
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                keyword="supprimés",
                                operation_type="REMOVE",
                                references=["sec-1"],
                            ),
                            contents=["sont ", self.make_tag("b", contents=["supprimés"])],
                        ),
                    ],
                )
            ]
        )

        ops = extract_raw_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 3
        assert [op.target_article for op in ops] == ["8.6", "8.7", "8.8"]
        assert all(op.operation_type == RawOperationType.REMOVE for op in ops)

    def test_replace_range_keeps_single_replace_and_converts_others_to_remove(self) -> None:
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
                                parent_reference="doc-2", start_num="8.6", end_num="8.8"
                            ),
                            contents=["articles 8.6 à 8.8"],
                            reserved_data_attrs=dict(tag_id="sec-2"),
                        ),
                        " de l' ",
                        self.make_semantic_tag(
                            DocumentReferenceSpec,
                            data=DocumentReferenceData(
                                type=DocumentType.arrete_prefectoral,
                                date="2010-05-11",
                            ),
                            contents=["arrêté préfectoral du 11 mai 2010"],
                            reserved_data_attrs=dict(tag_id="doc-2"),
                        ),
                        " ",
                        self.make_semantic_tag(
                            OperationSpec,
                            data=OperationData(
                                direction="rtl",
                                keyword="remplacés",
                                operation_type="REPLACE",
                                references=["sec-2"],
                            ),
                            contents=["sont ", self.make_tag("b", contents=["remplacés"])],
                        ),
                    ],
                )
            ]
        )

        ops = extract_raw_operations_from_tagged_soup(self.soup, arrete_id="2021-01-01")

        assert len(ops) == 3
        assert [op.target_article for op in ops] == ["8.6", "8.7", "8.8"]
        assert [op.operation_type for op in ops] == [
            RawOperationType.REPLACE,
            RawOperationType.REMOVE,
            RawOperationType.REMOVE,
        ]
