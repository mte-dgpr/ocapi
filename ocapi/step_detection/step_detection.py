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
"""
This step takes a list of HTML blocks (Document) with their corresponding ArreteId
and returns a list of detected operations (Operation).
Each operation is extracted by calling a LLM with a specific prompt.
"""

from langchain_core.documents import Document

from ocapi.exceptions import InvalidArreteIdError, InvalidArticleIdError, OperationError
from ocapi.step_detection.extract_operand import extract_operand_with_images
from ocapi.step_detection.prompts import prompt_detection
from ocapi.types import (
    ArreteId,
    ImageMap,
    NodeId,
    Operation,
    OperationType,
    RawOperation,
    RawOperationType,
    StatusCode,
    SubTargetType,
    parse_arrete_id,
    parse_article_id,
)
from ocapi.utils.llm_utils import (
    ConfidenceScoreConfig,
    call_llm_api,
    config_model_llm,
    get_confidence_score_config,
    parse_llm_json_list_response,
)
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.subtarget_utils import parse_subtarget
from ocapi.utils.utils import IdCounter, make_id

_LOGGER = get_logger(__name__)

_OPERATION_ID_COUNTER = IdCounter()
LLM_CFG = config_model_llm()


def _parse_and_validate_raw_operations(
    raw: str,
    arrete_id: ArreteId,
) -> list[RawOperation]:
    """Parse and structurally validate raw operations from an LLM response string."""
    raw_list = parse_llm_json_list_response(raw)
    raw_operations: list[RawOperation] = []
    for element in raw_list:
        try:
            raw_operations.append(RawOperation(**element))
        except Exception as exc:
            _LOGGER.warning(
                f"Raw operation skipped for arrêté {arrete_id} (invalid LLM parsing): {exc}"
            )

    valid_operations: list[RawOperation] = []
    for raw_op in raw_operations:
        if raw_op.source_article is None:
            _LOGGER.warning(
                f"Operation skipped (missing source_article): "
                f"type={raw_op.operation_type}, target_arrete={raw_op.target_arrete}, "
                f"target_article={raw_op.target_article}"
            )
            continue
        if raw_op.target_article is None:
            _LOGGER.warning(
                f"Operation skipped (missing target_article): "
                f"type={raw_op.operation_type}, source_article={raw_op.source_article}, "
                f"target_arrete={raw_op.target_arrete}"
            )
            continue
        try:
            parse_arrete_id(raw_op.target_arrete)
        except InvalidArreteIdError:
            _LOGGER.warning(
                f"Operation skipped (invalid target_arrete format): "
                f"type={raw_op.operation_type}, source_article={raw_op.source_article}, "
                f"target_arrete={raw_op.target_arrete}, target_article={raw_op.target_article}"
            )
            continue
        try:
            parse_article_id(raw_op.source_article)
        except InvalidArticleIdError:
            _LOGGER.warning(
                f"Operation skipped (invalid source_article format): "
                f"type={raw_op.operation_type}, source_article={raw_op.source_article}, "
                f"target_arrete={raw_op.target_arrete}, target_article={raw_op.target_article}"
            )
            continue
        try:
            parse_article_id(raw_op.target_article)
        except InvalidArticleIdError:
            _LOGGER.warning(
                f"Operation skipped (invalid target_article format): "
                f"type={raw_op.operation_type}, source_article={raw_op.source_article}, "
                f"target_arrete={raw_op.target_arrete}, target_article={raw_op.target_article}"
            )
            continue
        if raw_op.operation_type == RawOperationType.AUTRE:
            _LOGGER.warning(
                f"Operation skipped (AUTRE type – not a relevant operation): "
                f"source_article={raw_op.source_article}, "
                f"target_arrete={raw_op.target_arrete}, target_article={raw_op.target_article}"
            )
            continue
        valid_operations.append(raw_op)

    return valid_operations


def _filter_low_confidence_operations(
    operations: list[RawOperation],
    min_threshold: int,
    arrete_id: ArreteId,
) -> tuple[list[RawOperation], bool]:
    """Remove operations whose confidence score is below ``min_threshold``.

    Parameters
    ----------
    operations:
        Validated raw operations to inspect.
    min_threshold:
        Minimum acceptable confidence score (0-100 inclusive).
    arrete_id:
        Used in log messages for traceability.

    Returns
    -------
    tuple[list[RawOperation], bool]
        ``(kept_operations, had_low_confidence)`` where ``had_low_confidence``
        is ``True`` when at least one operation was dropped or flagged.
    """
    kept: list[RawOperation] = []
    had_low_confidence = False
    for op in operations:
        if op.confidence_score is not None and op.confidence_score < min_threshold:
            had_low_confidence = True
            _LOGGER.warning(
                f"Operation skipped (confidence_score={op.confidence_score} < {min_threshold}): "
                f"arrêté={arrete_id}, type={op.operation_type.value}, "
                f"source_article={op.source_article}, "
                f"target_arrete={op.target_arrete}, target_article={op.target_article}"
            )
        else:
            kept.append(op)
    return kept, had_low_confidence


def step_detection(
    html_blocks: list[Document], arrete_id: ArreteId, img_map: ImageMap
) -> list[Operation]:
    """Detect operations in an arrêté via the LLM.

    For each HTML block, queries the LLM, parses the JSON response,
    filters invalid operations and converts them into typed ``Operation`` objects.

    When confidence-score filtering is enabled (``llm_resilience.json``), operations
    whose ``confidence_score`` is below ``min_threshold`` are either skipped
    (``action_below_threshold="pass"``) or trigger a one-shot LLM retry for the
    block before the low-confidence operations are skipped
    (``action_below_threshold="retry"``).

    Parameters
    ----------
    html_blocks : list[Document]
        HTML blocks produced by ``step_chunking``.
    arrete_id : ArreteId
        Source arrêté identifier (YYYY-MM-DD date).
    img_map : ImageMap
        Token → image URL mapping for rehydrating operands.

    Returns
    -------
    list[Operation]
        Detected and validated operations, ready for resolution.
    """
    confidence_cfg: ConfidenceScoreConfig = get_confidence_score_config()

    _LOGGER.info(f"Detection: processing {len(html_blocks)} block(s)")
    all_ops: list[Operation] = []

    for html_block in html_blocks:
        raw = call_llm_api(LLM_CFG, prompt_detection(html_block.page_content))
        valid_operations = _parse_and_validate_raw_operations(raw, arrete_id)

        if confidence_cfg.enabled:
            if confidence_cfg.action_below_threshold == "retry":
                _, had_low_confidence = _filter_low_confidence_operations(
                    valid_operations, confidence_cfg.min_threshold, arrete_id
                )
                if had_low_confidence:
                    _LOGGER.warning(
                        f"Low confidence score(s) detected in block (arrêté={arrete_id}). "
                        "Retrying LLM call once for this block and continuing "
                        "regardless of the confidence score for detected operations."
                    )
                    raw = call_llm_api(LLM_CFG, prompt_detection(html_block.page_content))
                    valid_operations = _parse_and_validate_raw_operations(raw, arrete_id)

            valid_operations, _ = _filter_low_confidence_operations(
                valid_operations, confidence_cfg.min_threshold, arrete_id
            )

        all_ops.extend(
            convert_raw_operation_to_operation(html_block.page_content, raw_op, arrete_id, img_map)
            for raw_op in valid_operations
        )
    _LOGGER.info(f"Detection: {len(all_ops)} operation(s) detected")
    return all_ops


def convert_raw_operation_to_operation(
    html_block: str,
    raw_operation: RawOperation,
    source_arrete_id: ArreteId,
    img_map: ImageMap,
) -> Operation:
    """Convert a LLM ``RawOperation`` into a fully typed ``Operation``.

    Extracts the operand between content markers, parses the sub_target,
    assigns a unique ID and builds the source and target ``NodeId``.

    Parameters
    ----------
    html_block : str
        Raw HTML of the block in which the operation was detected.
    raw_operation : RawOperation
        Raw operation parsed from the LLM JSON response.
    source_arrete_id : ArreteId
        Identifier of the arrêté from which this operation originates.
    img_map : ImageMap
        Token → URL mapping for rehydrating images in the operand.

    Returns
    -------
    Operation
        Typed operation with ID, source, target, type, operand and sub_target.

    Raises
    ------
    OperationError
        If ``source_article`` or ``target_article`` is missing from the ``RawOperation``.
    """
    if raw_operation.source_article is None:
        raise OperationError("raw operation is missing source_article")
    if raw_operation.target_article is None:
        raise OperationError("raw operation is missing target_article")

    # Generate the operation ID first so it can be used in logging
    operation_id = make_id(_OPERATION_ID_COUNTER)

    operand = None
    op_status_code: StatusCode | None = None
    if raw_operation.new_content_start_marker and raw_operation.new_content_end_marker:
        operand, op_status_code = extract_operand_with_images(
            html_block,
            raw_operation.source_article,
            raw_operation.new_content_start_marker,
            raw_operation.new_content_end_marker,
            img_map,
            operation_id=operation_id,
        )
    sub_target = None
    if raw_operation.sub_target:
        sub_target = parse_subtarget(raw_operation.sub_target)

    raw_op_type = raw_operation.operation_type
    op_type_value = getattr(raw_op_type, "value", raw_op_type)
    op_type = OperationType(op_type_value)

    # target_article=ALL with a non-FULL_SECTION sub-target is incoherent:
    # the LLM tried to target something specific inside "all articles".
    if raw_operation.target_article == "ALL" and sub_target is not None:
        st = (
            sub_target.type
            if isinstance(sub_target.type, SubTargetType)
            else SubTargetType(sub_target.type)
        )
        if st != SubTargetType.FULL_SECTION:
            _LOGGER.warning(
                f"Operation {operation_id}: target_article=ALL with "
                f"sub_target={sub_target.type} is not fully defined "
                f"(target_arrete={raw_operation.target_arrete})"
            )
            op_status_code = StatusCode.ERROR_EXTRACTING_TARGET

    # A full-arrêté REPLACE (target_article=ALL) is in practice an abrogation.
    if op_type == OperationType.REPLACE and raw_operation.target_article == "ALL":
        _LOGGER.info(
            f"Operation {operation_id}: REPLACE ALL converted to REMOVE "
            f"(target_arrete={raw_operation.target_arrete})"
        )
        op_type = OperationType.REMOVE
        operand = None

    return Operation(
        id=operation_id,
        source_id=NodeId(
            arrete_id=source_arrete_id,
            article_id=raw_operation.source_article,
        ),
        target_id=NodeId(
            arrete_id=raw_operation.target_arrete,
            article_id=raw_operation.target_article,
        ),
        operation_type=op_type,
        operand=operand,
        sub_target=sub_target,
        status_code=op_status_code,
        confidence_score=raw_operation.confidence_score,
    )
