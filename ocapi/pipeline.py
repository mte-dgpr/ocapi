from typing import Iterator
from xml.dom.minidom import Document
from ocapi.constants import DEFAULT_LLM_MODEL
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.types import ArreteFile, Operation, Permis, ImageMap
from ocapi.step_detection.step_detection import step_detection

def run_pipeline(arrete_files: list[ArreteFile])-> Permis:
    operations : list[Operation] = [] 
    modele = DEFAULT_LLM_MODEL
    # TODO : valider le type arrete_id 
    for arrete_file in arrete_files:
        docs: list[Document]; img_map:ImageMap = step_chunking(arrete_file)
        operations.extend(step_detection(docs, arrete_file.id, modele, img_map))


    history, arrete_files = step_resolution(operations, arrete_files)
    permis = step_rendering(history, operations, arrete_files)

    return permis
