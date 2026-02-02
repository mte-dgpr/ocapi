"""
Ce step prend une liste de blocs HTML (Document) et leurs ArreteId correspondant
et retourne une liste d'opérations détectées (Operation).
Chaque opération est extraite en appelant un LLM avec un prompt spécifique.
"""

# TODO modifier les opérations pour prendre en compte les changements de titre
# ou deplacement d'article.

from langchain_core.documents import Document

from ocapi.step_detection.extract_operand import extract_operand_with_images
from ocapi.step_detection.prompts import prompt2
from ocapi.step_detection.subtarget_detection import parse_subtarget
from ocapi.types import ArreteId, ImageMap, NodeId, Operation, OperationType, RawOperation
from ocapi.utils.llm_utils import call_llm_api, config_model_llm, parse_llm_json_list_response
from ocapi.utils.utils import IdCounter, make_id

_OPERATION_ID_COUNTER = IdCounter()


def step_detection(
    html_blocks: list[Document], arrete_id: ArreteId, modele: str, img_map: ImageMap
) -> list[Operation]:
    all_ops: list[Operation] = []
    cfg = config_model_llm(modele)
    for block_html in html_blocks:
        raw = call_llm_api(cfg, prompt2(block_html.page_content))
        raw_list = parse_llm_json_list_response(raw)
        raw_operations = [RawOperation(**element) for element in raw_list]
        all_ops.extend(
            convert_raw_operation_to_operation(block_html, raw_op, arrete_id, img_map)
            for raw_op in raw_operations
        )
    return all_ops


def convert_raw_operation_to_operation(
    block_html: Document,
    raw_operation: RawOperation,
    source_arrete_id: ArreteId,
    img_map: ImageMap,
) -> Operation:
    block_content = block_html.page_content
    if raw_operation.source_article is None:
        raise ValueError("raw operation is missing source_article")
    if raw_operation.target_article is None:
        raise ValueError("raw operation is missing target_article")

    operand = None
    if raw_operation.new_content_start_marker and raw_operation.new_content_end_marker:
        operand = extract_operand_with_images(
            block_content,
            raw_operation.source_article,
            raw_operation.new_content_start_marker,
            raw_operation.new_content_end_marker,
            img_map,
        )
    sub_target = None
    if raw_operation.sub_target:
        sub_target = parse_subtarget(raw_operation.sub_target)

    raw_op_type = raw_operation.operation_type
    op_type_value = getattr(raw_op_type, "value", raw_op_type)
    op_type = OperationType(op_type_value)

    return Operation(
        id=make_id(_OPERATION_ID_COUNTER),
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
