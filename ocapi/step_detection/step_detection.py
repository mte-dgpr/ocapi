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
Ce step prend une liste de blocs HTML (Document) et leurs ArreteId correspondant
et retourne une liste d'opérations détectées (Operation).
Chaque opération est extraite en appelant un LLM avec un prompt spécifique.
"""

# TODO modifier les opérations pour prendre en compte les changements de titre
# ou deplacement d'article.

from langchain_core.documents import Document

from ocapi.step_detection.extract_operand import extract_operand_with_images
from ocapi.step_detection.prompts import prompt_detection
from ocapi.types import ArreteId, ImageMap, NodeId, Operation, OperationType, RawOperation
from ocapi.utils.llm_utils import call_llm_api, config_model_llm, parse_llm_json_list_response
from ocapi.utils.logging_utils import get_logger
from ocapi.utils.subtarget_utils import parse_subtarget
from ocapi.utils.utils import IdCounter, make_id

_LOGGER = get_logger(__name__)

_OPERATION_ID_COUNTER = IdCounter()
LLM_CFG = config_model_llm()


def step_detection(
    html_blocks: list[Document], arrete_id: ArreteId, img_map: ImageMap
) -> list[Operation]:
    _LOGGER.info(f"Détection: traitement de {len(html_blocks)} bloc(s)")
    all_ops: list[Operation] = []
    for block_html in html_blocks:
        # Appel LLM pour détecter les opérations dans le bloc HTML
        # TODO : implémenter un retry en cas d'erreur (sur l'extraction du contenu par ex)
        raw = call_llm_api(LLM_CFG, prompt_detection(block_html.page_content))
        raw_list = parse_llm_json_list_response(raw)
        raw_operations = [RawOperation(**element) for element in raw_list]
        for raw_op in raw_operations:
            try:
                op = convert_raw_operation_to_operation(
                    block_html.page_content, raw_op, arrete_id, img_map
                )
                all_ops.append(op)
            except ValueError as exc:
                missing = []
                if raw_op.source_article is None:
                    missing.append("source_article")
                if raw_op.target_article is None:
                    missing.append("target_article")
                detail = f"champs manquants: {', '.join(missing)}" if missing else str(exc)
                _LOGGER.warning(
                    f"Opération ignorée pour l'arrêté {arrete_id} "
                    f"(type={raw_op.operation_type}, "
                    f"source={raw_op.source_article}, "
                    f"target={raw_op.target_article}): {detail}"
                )
                continue
    _LOGGER.info(f"Détection: {len(all_ops)} opération(s) détectée(s)")
    return all_ops


def convert_raw_operation_to_operation(
    block_html: str,
    raw_operation: RawOperation,
    source_arrete_id: ArreteId,
    img_map: ImageMap,
) -> Operation:
    if raw_operation.source_article is None:
        raise ValueError("raw operation is missing source_article")
    if raw_operation.target_article is None:
        raise ValueError("raw operation is missing target_article")

    # Générer l'ID de l'opération en premier pour pouvoir l'utiliser dans le logging
    operation_id = make_id(_OPERATION_ID_COUNTER)

    operand = None
    if raw_operation.new_content_start_marker and raw_operation.new_content_end_marker:
        operand = extract_operand_with_images(
            block_html,
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
    )
