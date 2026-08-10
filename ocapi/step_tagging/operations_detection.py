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
from typing import Iterator, Literal, Sequence, cast

from arretify.parsing_utils.numbering import COUNT_PATTERN_S
from arretify.regex_utils import (
    filter_regex_tree_match_children,
    flat_map_regex_tree_match,
    iter_regex_tree_match_page_elements_or_strings,
    join_with_or,
    regex_tree,
)
from arretify.types import DocumentContext, ProtectedSoup, ProtectedTag, ProtectedTagOrStr
from arretify.utils.html_create import make_semantic_tag, make_tag
from arretify.utils.html_split_merge import make_regex_tree_splitter
from arretify.utils.split_merge import split_and_map_elements
from arretify.utils.strings import merge_strings

from ocapi.semantic_tag_specs import OperationData, OperationSpec
from ocapi.types import RawOperationType

OPERATION_TYPES_GROUP_NAMES = [
    RawOperationType.ADD.value,
    RawOperationType.REMOVE.value,
    RawOperationType.REPLACE.value,
]


SECTION_AFTER_OPERATION_L = r"(le|la|les|l')\s+"
SECTION_AFTER_OPERATION_D = r"(de|du|des|d')\s+"
SECTION_AFTER_OPERATION_A = r"(à|au|à l'|aux)\s+"
SECTION_POSITION_EXPR = r"(au\s+début|à\s+la\s+fin|à\s+la\s+suite|au\s+niveau)"

TERMS_VARIANTS_LIST = [
    r"termes?",
    r"phrases?",
    r"mots?",
    r"dispositions?(\s+suivantes?)?",
]
TERMS_VARIANTS = rf"{SECTION_AFTER_OPERATION_L}({join_with_or(TERMS_VARIANTS_LIST)})"

DISPOSITION_PATTERN_S = r"les dispositions suivantes"
EXPR_CONTINUATION_LIST = [
    r"suivant\s+les\s+dispositions",
    r"par\s+les\s+(suivantes|dispositions|prescriptions)",
    r"par\s+ce\s+qui\s+suit",
    r"comme\s+précisé",
    r"celles\s+définies\s+par",
    r"par\s+celles\s+(inscrites|répertoriées)",
    r"ainsi\s+qu'il\s+suit",
    r"dans\s+les\s+conditions\s+(suivantes|ci-après)",
    r"ainsi",
    r"par\s+le\s+suivant",
    r"de\s+la\s+(façon|manière)\s+suivante",
    r"comme\s+sui(t|vant)",
    r"comme\s+(indiqué|précisé|ci-après)",
    rf"selon\s{SECTION_AFTER_OPERATION_L}",
]

EXPR_CONTINUATION = join_with_or(EXPR_CONTINUATION_LIST)


# Operation target(1) operation description(2) operand(3, optional)
# Example:
# les dispositions de l'article 8.1.1.1 l'arrêté du 12 mai 2016(1) sont complétées
# par les dispositions suivantes :(2)
# Un contrôle trimestriel de l'alarme en point bas des lignes de zingage et des
# lignes époxy est mis en place par l'exploitant.(3)
#
# This regex detects the part (2) of the operation.
RTL_OPERATION_NODE = regex_tree.Group(
    regex_tree.Sequence(
        [
            r"^[\s\S]*",
            regex_tree.Branching(
                [
                    r"est\s+ainsi",
                    r"sont\s+ainsi",
                    r"est",
                    r"sont",
                ]
            ),
            r"\s+",
            regex_tree.Branching(
                [
                    # ADD OPERATIONS
                    regex_tree.Sequence(
                        [
                            regex_tree.Group(
                                r"créée?s?",
                                group_name=RawOperationType.ADD.value,
                            ),
                            r"\s+",
                            regex_tree.Branching(
                                [
                                    r"un\s+(nouve(l|au)\s+)?",
                                    rf"{COUNT_PATTERN_S}\s+(nouveaux\s+)?",
                                    rf"en fin\s+{SECTION_AFTER_OPERATION_D}",
                                    SECTION_AFTER_OPERATION_A,
                                    DISPOSITION_PATTERN_S,
                                ]
                            ),
                        ]
                    ),
                    regex_tree.Sequence(
                        [
                            regex_tree.Group(
                                r"insérée?s?",
                                group_name=RawOperationType.ADD.value,
                            ),
                            r"(?!\s+aux?\s+recueils?\s+des\s+actes\s+administratifs)",
                            r"\s+",
                            regex_tree.Branching(
                                [
                                    regex_tree.Sequence(
                                        [
                                            regex_tree.Branching([r"après", r"dans"]),
                                            r"\s+",
                                            SECTION_AFTER_OPERATION_L,
                                        ]
                                    ),
                                    regex_tree.Sequence(
                                        [
                                            SECTION_POSITION_EXPR,
                                            r"\s+",
                                            SECTION_AFTER_OPERATION_D,
                                        ]
                                    ),
                                    r"et\s+(est|sont)\s+ainsi\s+rédigés?",
                                    r"le nouve(l|au)",
                                    rf"les\s+{COUNT_PATTERN_S}",
                                    rf"{COUNT_PATTERN_S}\s+points?",
                                    rf"{SECTION_AFTER_OPERATION_A}",
                                    DISPOSITION_PATTERN_S,
                                ]
                            ),
                        ]
                    ),
                    regex_tree.Sequence(
                        [
                            regex_tree.Group(
                                r"complétée?s?",
                                group_name=RawOperationType.ADD.value,
                            ),
                            r"[,\s]+",
                            regex_tree.Branching(
                                [
                                    r"à\s+(sa|la)\s+fin",
                                    r"comme\s+suit",
                                    r"ainsi",
                                    r"par\s+",
                                    r"d'",
                                ]
                            ),
                        ]
                    ),
                    regex_tree.Group(
                        regex_tree.Branching(
                            [
                                r"modifiée?s?\s+par\s+l'ajout",
                                r"ajoutée?s?",
                            ]
                        ),
                        group_name=RawOperationType.ADD.value,
                    ),
                    # REPLACE OPERATIONS
                    regex_tree.Group(
                        regex_tree.Branching(
                            [
                                # Table regex
                                r"modifiée?s?\s+ou\s+supprimée?s?\s+et\s+remplacée?s?",
                                r"supprimée?s?,\s+modifiée?s?\s+ou\s+ajoutée?s?",
                                r"modifiée?s?,\s+supprimée?s?\s+ou\s+complétée?s?",
                                r"modifiée?s?,\s+complétée?s?,?\s+ou\s+annulée?s?",
                            ],
                        ),
                        group_name=RawOperationType.REPLACE.value,
                    ),
                    regex_tree.Group(
                        regex_tree.Branching(
                            [
                                # Simple regex
                                r"abrogée?s?\s+et\s+substituée?s?",
                                r"supprimée?s?\s+et(\s+est|\s+sont)?\s+remplacée?s?",
                                r"annulée?s?\s+et\s+remplacée?s?",
                                r"abrogée?s?\s+(et|ou)\s+remplacée?s?",
                                r"modifiée?s?\s+et\s+(remplacée?|complétée?)s?",
                                r"remplacée?s?\s+et\s+complétée?s?",
                                r"modifiée?s?\s+et\s+rédigée?s?",
                                r"modifiée?s?\s+(et|ou)\s+supprimée?s?",
                            ],
                        ),
                        group_name=RawOperationType.REPLACE.value,
                    ),
                    regex_tree.Sequence(
                        [
                            regex_tree.Group(
                                r"substituée?s?",
                                group_name=RawOperationType.REPLACE.value,
                            ),
                            r"\s+",
                            r"par",
                        ]
                    ),
                    regex_tree.Sequence(
                        [
                            regex_tree.Group(
                                r"remplacée?s?",
                                group_name=RawOperationType.REPLACE.value,
                            ),
                            r"\s+",
                            regex_tree.Branching(
                                [
                                    regex_tree.Group(
                                        r":\s*$",
                                        group_name="__has_operand",
                                    ),
                                    EXPR_CONTINUATION,
                                    rf"par\s+{TERMS_VARIANTS}",
                                    rf"par\s+{SECTION_AFTER_OPERATION_L}?",
                                ]
                            ),
                        ]
                    ),
                    regex_tree.Sequence(
                        [
                            regex_tree.Group(
                                r"modifiée?s?",
                                group_name=RawOperationType.REPLACE.value,
                            ),
                            r"\s+",
                            regex_tree.Branching(
                                [
                                    regex_tree.Group(
                                        r":\s*$",
                                        group_name="__has_operand",
                                    ),
                                    EXPR_CONTINUATION,
                                    rf"pour\s+{SECTION_AFTER_OPERATION_L}",
                                    r"pour\s+(ce\s+)?qui\s+concerne",
                                    (
                                        rf"par\s+:?celles?\s+{SECTION_AFTER_OPERATION_D}?"
                                        rf"{SECTION_AFTER_OPERATION_L}?"
                                    ),
                                    rf"conformément\s+{SECTION_AFTER_OPERATION_A}",
                                    rf"au\s+niveau\s+{SECTION_AFTER_OPERATION_D}",
                                    r"de\s+manière\s+temporaire",
                                ]
                            ),
                        ]
                    ),
                    regex_tree.Sequence(
                        [
                            regex_tree.Group(
                                r"mis(e|es)? a jour",
                                group_name=RawOperationType.REPLACE.value,
                            ),
                            r"\s+",
                            regex_tree.Branching(
                                [
                                    r"de\s+la\s+façon\s+suivante",
                                ]
                            ),
                        ]
                    ),
                    # DELETE OPERATIONS
                    regex_tree.Group(
                        regex_tree.Branching(
                            [
                                r"abrogée?s?",
                                r"supprimée?s?",
                                r"annulée?s?",
                            ]
                        ),
                        group_name=RawOperationType.REMOVE.value,
                    ),
                ]
            ),
            # When the string is not ended by a period (.), we consider that
            # there is a right operand.
            regex_tree.Repeat(
                regex_tree.Group(
                    r"[^\.]*$",
                    group_name="__has_operand",
                ),
                quantifier=(0, ...),
            ),
        ]
    ),
    group_name="__operation",
)


SUBJECT_LTR = r"(?:le|les)\spr[ée]sente?s?\s(?:arr[êe]t[ée]s?|articles?|dispositions?)"


# LTR operations are recognised at the start of an alinea. Two flavours:
#  * active voice: "Le présent arrêté annule et remplace l'arrêté X"
#  * passive voice: "Sont insérés après le paragraphe X, les ..."
# In both cases the references follow on the right as sibling tags, so the
# regex must NOT consume them. The trailing determiner (le/la/les/l') is
# consumed so the reference ends up as the immediate right sibling of the
# operation tag.
LTR_OPERATION_NODE = regex_tree.Group(
    regex_tree.Branching(
        [
            # Active voice
            regex_tree.Sequence(
                [
                    r"^\s*",
                    SUBJECT_LTR,
                    r"\s",
                    regex_tree.Branching(
                        [
                            regex_tree.Group(
                                regex_tree.Branching(
                                    [
                                        r"annule\s(et|ou)\sremplace",
                                        r"abroge\s(et|ou)\sremplace",
                                        r"modifie\set\sremplace",
                                        r"modifie\set\scompl[èe]te",
                                        r"remplace\set\scompl[èe]te",
                                    ]
                                ),
                                group_name=RawOperationType.REPLACE.value,
                            ),
                            regex_tree.Group(
                                regex_tree.Branching(
                                    [
                                        r"abroge",
                                        r"supprime",
                                        r"annule",
                                    ]
                                ),
                                group_name=RawOperationType.REMOVE.value,
                            ),
                            regex_tree.Group(
                                regex_tree.Branching(
                                    [
                                        r"compl[èe]te",
                                        r"ajoute",
                                    ]
                                ),
                                group_name=RawOperationType.ADD.value,
                            ),
                        ]
                    ),
                    regex_tree.Repeat(
                        regex_tree.Group(
                            r"\sles\sarticles?\ssuivants?(?:\sdes?)?",
                            group_name="__has_operand",
                        ),
                        quantifier=(0, 1),
                    ),
                    r"\s(?:l['’]|le|la|les|du|des|de\sl['’]?)\s?",
                ]
            ),
            # Passive voice: "Sont insérés après le paragraphe 4.23, les ..."
            # The reference sits right after the trailing determiner; the
            # operand (the inserted content) follows on the right.
            regex_tree.Sequence(
                [
                    r"^\s*(?:est|sont)\s+",
                    regex_tree.Group(
                        regex_tree.Branching(
                            [
                                r"insérée?s?",
                                r"ajoutée?s?",
                            ]
                        ),
                        group_name=RawOperationType.ADD.value,
                    ),
                    regex_tree.Group(
                        r"\s+(?:après|avant|à\sla\ssuite\sde)\s+(?:l['’]|le|la|les|du|des)\s+",
                        group_name="__has_operand",
                    ),
                ]
            ),
        ]
    ),
    group_name="__operation",
)


def parse_operations(
    document_context: DocumentContext,
    contents: Sequence[ProtectedTagOrStr],
) -> list[ProtectedTagOrStr]:
    splitter_rtl = make_regex_tree_splitter(RTL_OPERATION_NODE)
    splitter_ltr = make_regex_tree_splitter(LTR_OPERATION_NODE)
    return cast(
        list[ProtectedTagOrStr],
        split_and_map_elements(
            split_and_map_elements(
                contents,
                splitter_ltr,
                lambda match: _render_operation_match(
                    document_context.protected_soup, match, direction="ltr"
                ),
            ),
            splitter_rtl,
            lambda match: _render_operation_match(
                document_context.protected_soup, match, direction="rtl"
            ),
        ),
    )


def _render_operation_match(
    soup: ProtectedSoup,
    operation_match: regex_tree.Match,
    direction: Literal["ltr", "rtl"] = "rtl",
) -> ProtectedTag:
    return make_semantic_tag(
        soup,
        OperationSpec,
        contents=flat_map_regex_tree_match(
            operation_match.children,
            lambda group_match: _render_group_match(soup, group_match),
            allowed_group_names=[
                "__has_operand",
                *OPERATION_TYPES_GROUP_NAMES,
            ],
        ),
        data=_extract_operation_data(operation_match, direction=direction),
    )


def _render_group_match(
    soup: ProtectedSoup, group_match: regex_tree.Match
) -> Iterator[ProtectedTagOrStr]:
    if group_match.group_name == "__has_operand":
        yield from iter_regex_tree_match_page_elements_or_strings(group_match)
    elif group_match.group_name in OPERATION_TYPES_GROUP_NAMES:
        yield make_tag(
            soup,
            "b",
            contents=iter_regex_tree_match_page_elements_or_strings(group_match),
        )
    else:
        raise RuntimeError(f"Unexpected group name {group_match.group_name}")


def _extract_operation_data(
    operation_match: regex_tree.Match,
    direction: Literal["ltr", "rtl"] = "rtl",
) -> OperationData:
    operation_type_groups = filter_regex_tree_match_children(
        operation_match,
        OPERATION_TYPES_GROUP_NAMES,
    )
    if len(operation_type_groups) != 1:
        raise RuntimeError("Expected exactly one operation type group")
    operation_type_group = operation_type_groups[0]

    has_operand = len(filter_regex_tree_match_children(operation_match, ["__has_operand"])) > 0

    return OperationData(
        operation_type=operation_type_group.group_name,
        keyword=merge_strings(
            iter_regex_tree_match_page_elements_or_strings(operation_type_group),
            strip_other_types=True,
        ),
        has_operand=has_operand,
        references=None,
        direction=direction,
        operand=None,
    )
