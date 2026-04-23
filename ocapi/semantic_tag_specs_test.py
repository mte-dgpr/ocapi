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
from arretify.semantic_tag_specs import OperationSpec as ArretifyOperationSpec
from arretify.types import OperationType as ArretifyOperationType

from ocapi.semantic_tag_specs import (
    OPERATION_DATA_SPEC,
    OperationData,
    OperationSpec,
    OperationType,
)


def test_operation_data_spec_matches_arretify_spec_name() -> None:
    assert OPERATION_DATA_SPEC == "operation"
    assert OPERATION_DATA_SPEC == ArretifyOperationSpec.spec_name


def test_reexports_point_to_arretify_symbols() -> None:
    assert OperationSpec is ArretifyOperationSpec
    assert OperationType is ArretifyOperationType


def test_operation_data_fields() -> None:
    assert {"operation_type", "direction", "keyword"}.issubset(OperationData.model_fields.keys())
