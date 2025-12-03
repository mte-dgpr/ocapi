

from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import ArreteFile, ArreteId, NodeId, Operation
from ocapi.step_detection.step_detection import step_detection

def run_pipeline(arrete_files: list[ArreteFile], arrete_ids_included: set[ArreteId])-> Permis:
    operations : list[Operation] = [] 
    for arrete_file in arrete_files:
        docs, img_map = step_chunking(arrete_file)
        operations.extend(step_detection(docs, arrete_file.id, img_map))

    filtered_operations = operations[:]
    if arrete_ids_included:
        filtered_operations = filter(
            lambda operation: (
                (operation.source_id.arrete_id in arrete_ids_included) 
                and (operation.target_id.arrete_id in arrete_ids_included)
            )
        )

    versions = step_resolution(filtered_operations)
    permis = step_rendering(versions, arrete_files)
