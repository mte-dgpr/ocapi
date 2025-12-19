"""
Ce step prend une liste de blocs HTML (Document) et leurs ArreteId correspondant et retourne une liste d'opérations détectées (Operation).
Chaque opération est extraite en appelant un LLM avec un prompt spécifique.
"""
# TODO modifier les opérations pour prendre en compte les changements de titre ou deplacement d'article.
# TODO voir comment gérer l'arrete 2012 dans l'exemple cas d'école. 

from ocapi.step_detection.prompts import prompt_detection
from ocapi.step_detection.subtarget_detection import parse_subtarget
from ocapi.types import ArreteId, ImageMap, NodeId, Operation, RawOperation
from ocapi.utils.utils import IdCounter, make_id
from ocapi.utils.llm_utils import call_llm_api, config_model_llm, parse_llm_json_list_response
from ocapi.step_detection.extract_operand import extract_operand_with_images
from langchain_core.documents import Document

_OPERATION_ID_COUNTER = IdCounter()

def step_detection(html_blocks: list[Document], arrete_id: ArreteId, modele: str, img_map: ImageMap) -> list[Operation]:
    all_ops = []
    cfg = config_model_llm(modele)
    for block_html in html_blocks:
        raw = call_llm_api(cfg, prompt_detection(block_html.page_content))
        raw_list = parse_llm_json_list_response(raw)
        print(f"  → LLM returned {len(raw_list)} raw operations for block of arrete {arrete_id}")
        raw_operations = [RawOperation(**element) for element in raw_list]
        all_ops.extend(
            convert_raw_operation_to_operation(block_html.page_content, raw_op, arrete_id, img_map) for raw_op in raw_operations
        )
    return all_ops



def convert_raw_operation_to_operation(block_html: str, raw_operation: RawOperation, source_arrete_id: ArreteId, img_map: ImageMap) -> Operation:
    operand = None 
    if raw_operation.new_content_start_marker:
        operand=extract_operand_with_images(block_html, raw_operation.source_article, raw_operation.new_content_start_marker, raw_operation.new_content_end_marker, img_map)
    sub_target = None 
    if raw_operation.sub_target:
        sub_target=parse_subtarget(raw_operation.sub_target)
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
        operation_type=raw_operation.operation_type,
        operand=operand,
        sub_target=sub_target,
    )
