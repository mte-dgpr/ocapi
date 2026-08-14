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
from ocapi.step_tagging.operations_filtering import filter_redundant_operations
from ocapi.types import OperationType, SubTarget, SubTargetType
from ocapi.utils.testing import make_testing_op


def test_filter_redundant_operations_drops_strict_duplicates() -> None:
    reference = make_testing_op(
        OperationType.REPLACE,
        operation_id="1",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )
    duplicate_candidate = make_testing_op(
        OperationType.REPLACE,
        operation_id="2",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )

    kept = filter_redundant_operations(
        reference_ops=[reference],
        candidate_ops=[duplicate_candidate],
        context_id="arrêté 2024-01-10",
    )

    assert kept == [reference]


def test_filter_redundant_operations_keeps_when_source_differs() -> None:
    reference = make_testing_op(
        OperationType.REPLACE,
        operation_id="1",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )
    different_source = make_testing_op(
        OperationType.REPLACE,
        operation_id="2",
        source_arrete="2024-01-10",
        source_article="1.1",
        target_arrete="2020-01-01",
        target_article="2",
    )

    kept = filter_redundant_operations(
        reference_ops=[reference],
        candidate_ops=[different_source],
        context_id="arrêté 2024-01-10",
    )

    assert kept == [reference, different_source]


def test_filter_redundant_operations_keeps_when_subtarget_scope_differs() -> None:
    reference = make_testing_op(
        OperationType.REPLACE,
        sub_target=SubTarget(type=SubTargetType.PARAGRAPHE, position=1, description="paragraphe 1"),
        operation_id="1",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )
    different_subtarget = make_testing_op(
        OperationType.REPLACE,
        sub_target=SubTarget(type=SubTargetType.PARAGRAPHE, position=2, description="paragraphe 2"),
        operation_id="2",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )

    kept = filter_redundant_operations(
        reference_ops=[reference],
        candidate_ops=[different_subtarget],
        context_id="arrêté 2024-01-10",
    )

    assert kept == [reference, different_subtarget]


def test_filter_redundant_operations_keeps_precise_reference_against_less_precise_candidate() -> (
    None
):
    reference = make_testing_op(
        OperationType.REPLACE,
        sub_target=SubTarget(type=SubTargetType.PARAGRAPHE, position=1, description="paragraphe 1"),
        operation_id="1",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )
    less_precise_candidate = make_testing_op(
        OperationType.REPLACE,
        operation_id="2",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )

    kept = filter_redundant_operations(
        reference_ops=[reference],
        candidate_ops=[less_precise_candidate],
        context_id="arrêté 2024-01-10",
    )

    assert kept == [reference]


def test_filter_redundant_operations_keeps_precise_candidate_against_full_reference() -> None:
    reference = make_testing_op(
        OperationType.REPLACE,
        operation_id="1",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )
    precise_candidate = make_testing_op(
        OperationType.REPLACE,
        sub_target=SubTarget(type=SubTargetType.PARAGRAPHE, position=1, description="paragraphe 1"),
        operation_id="2",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )

    kept = filter_redundant_operations(
        reference_ops=[reference],
        candidate_ops=[precise_candidate],
        context_id="arrêté 2024-01-10",
    )

    assert kept == [precise_candidate]


def test_filter_redundant_operations_keeps_when_reference_list_empty() -> None:
    candidate = make_testing_op(
        OperationType.REPLACE,
        operation_id="2",
        source_arrete="2024-01-10",
        source_article="1",
        target_arrete="2020-01-01",
        target_article="2",
    )

    kept = filter_redundant_operations(
        reference_ops=[],
        candidate_ops=[candidate],
        context_id="arrêté 2024-01-10",
    )

    assert kept == [candidate]
