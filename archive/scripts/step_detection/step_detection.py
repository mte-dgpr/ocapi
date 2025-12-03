"""
Lire data/arretes_blocs/*.blocks.json.
Pour chaque bloc, appeler ask_llm_for_operation (ou skip si --no-api)
Ecrire sorties groupées par AP dans data/operations_brutes/<ap>.ops.json
Choisir le modèle via --model ou la variable DEFAULT_MODEL
"""
# TODO modifier les opérations pour prendre en compte les changements de titre ou deplacement d'article.

from typing import Any, Dict

from ocapi.step_detection.subtarget_detection import parse_subtarget
from ocapi.types import ArreteId, NodeId, Operation, OperationType, RawOperation
from ocapi.utils.utils import IdCounter, make_id
from prompts import prompt2
from ocapi.utils.llm_utils import call_llm_api, config_model_llm, parse_llm_json_list_response
from ocapi.step_detection.extract_operand import extract_operand

_OPERATION_ID_COUNTER = IdCounter()

# charger explicitement le .env à la racine du projet (remonter suffisamment)

def step_detection(html_blocks: list[str], arrete_id: ArreteId, modele: str) -> list[Operation]:
    all_ops = []
    cfg = config_model_llm(modele)
    for block_html in html_blocks:
        raw = call_llm_api(cfg, prompt2(block_html))
        raw_list = parse_llm_json_list_response(raw)
        raw_operations = [RawOperation(element) for element in raw_list]
        all_ops.extend(
            convert_raw_operation_to_operation(block_html, raw_op, arrete_id) for raw_op in raw_operations
        )
    return all_ops


def convert_raw_operation_to_operation(block_html: str, raw_operation: RawOperation, source_arrete_id: ArreteId) -> Operation:
    operand = None 
    if raw_operation.new_content_start_marker:
        operand=extract_operand(block_html, raw_operation.source_article, raw_operation.new_content_start_marker, raw_operation.new_content_end_marker)
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
