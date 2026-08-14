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
from typing import Callable

from ocapi.types import Operation, SubTargetType
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def _subtarget_relation(existing_op: Operation, incoming_op: Operation) -> str:
    existing_subtarget = existing_op.sub_target
    incoming_subtarget = incoming_op.sub_target

    existing_full = (
        existing_subtarget is None or existing_subtarget.type == SubTargetType.FULL_SECTION
    )
    incoming_full = (
        incoming_subtarget is None or incoming_subtarget.type == SubTargetType.FULL_SECTION
    )

    if existing_full and incoming_full:
        return "same_scope"
    if existing_full and not incoming_full:
        return "existing_less_precise"
    if not existing_full and incoming_full:
        return "incoming_less_precise"
    if existing_subtarget is not None and incoming_subtarget is not None:
        if (
            existing_subtarget.type == incoming_subtarget.type
            and existing_subtarget.position == incoming_subtarget.position
        ):
            return "same_scope"
    return "different_scope"


def filter_redundant_operations(
    reference_ops: list[Operation],
    candidate_ops: list[Operation],
    context_id: str,
    next_operation_id: Callable[[], str] | None = None,
) -> list[Operation]:
    """Filter redundant operations while preserving the most precise version of a change.

    Redundancy is detected with a strict match on:
    - source_id
    - target_id
    - operation_type
    - sub-target scope (full section vs typed/positioned sub-target)
    """
    incoming_ops = [*reference_ops, *candidate_ops]
    if not incoming_ops:
        return []

    kept_ops: list[Operation] = []
    kept_ids: set[str] = set()
    skipped_operation_count = 0
    replaced_operation_count = 0

    for incoming_op in incoming_ops:
        less_precise_indexes: list[int] = []
        skip_incoming = False

        for index, existing_op in enumerate(kept_ops):
            if (
                existing_op.source_id != incoming_op.source_id
                or existing_op.target_id != incoming_op.target_id
            ):
                continue

            relation = _subtarget_relation(existing_op, incoming_op)
            if (
                relation == "same_scope"
                and existing_op.operation_type == incoming_op.operation_type
            ):
                skip_incoming = True
                break
            if relation == "incoming_less_precise":
                skip_incoming = True
                break
            if relation == "existing_less_precise" and existing_op.id != incoming_op.id:
                less_precise_indexes.append(index)

        if skip_incoming:
            skipped_operation_count += 1
            _LOGGER.info(
                f"Dropping operation {incoming_op.id} in {context_id}: already covered "
                "by a more precise retained operation"
            )
            continue

        if less_precise_indexes:
            replaced_operation_count += len(less_precise_indexes)
            for index in reversed(less_precise_indexes):
                removed_op = kept_ops.pop(index)
                kept_ids.discard(removed_op.id)
                _LOGGER.info(
                    f"Dropping operation {removed_op.id} in {context_id}: "
                    "more precise operation exists"
                )

        if next_operation_id is not None and incoming_op.id in kept_ids:
            while incoming_op.id in kept_ids:
                incoming_op.id = next_operation_id()

        kept_ops.append(incoming_op)
        kept_ids.add(incoming_op.id)

    if skipped_operation_count or replaced_operation_count:
        total_filtered = skipped_operation_count + replaced_operation_count
        _LOGGER.info(f"Filtered {total_filtered} redundant operation(s) in {context_id}")

    return kept_ops
