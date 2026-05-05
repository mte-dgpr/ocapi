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
from enum import Enum
from typing import Annotated, Literal

from arretify.utils.html_semantic import (
    Bool,
    Contents,
    SemanticTagData,
    SemanticTagSpec,
    StrList,
    enum_serializer,
)

__all__ = [
    "OperationData",
    "OperationSpec",
    "OperationType",
    "OPERATION_DATA_SPEC",
]


class OperationType(Enum):
    ADD = "add"
    DELETE = "delete"
    REPLACE = "replace"


class OperationData(SemanticTagData):  # type: ignore[misc]
    operation_type: Annotated[OperationType, enum_serializer]
    direction: Literal["ltr", "rtl"]
    references: StrList | None = None
    keyword: str
    has_operand: Bool = False
    operand: str | None = None


OperationSpec: SemanticTagSpec[OperationData] = SemanticTagSpec(
    spec_name="operation",
    tag_name="span",
    data_model=OperationData,
    allowed_contents=(Contents.Str(),),
    is_allowed_anywhere=True,
)


OPERATION_DATA_SPEC: str = OperationSpec.spec_name
