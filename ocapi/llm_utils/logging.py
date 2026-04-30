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
from ocapi.types import Operation, OperationType
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def llm_consolidation_log(operation: Operation, action: str) -> None:
    """Log LLM fallback for add / replace / remove (complex or ambiguous sub-target)."""
    op_type = (
        operation.operation_type.value
        if isinstance(operation.operation_type, OperationType)
        else str(operation.operation_type)
    )
    _LOGGER.info(
        "LLM consolidation fallback: operation_id=%s action=%s operation_type=%s target=%s",
        operation.id,
        action,
        op_type,
        operation.target_id,
    )
