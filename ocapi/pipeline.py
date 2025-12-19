from typing import Iterator
from xml.dom.minidom import Document
from ocapi.constants import DEFAULT_LLM_MODEL
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.types import ArreteFile, ArreteId, ArticlesContentMap, Operation, Permis, ImageMap
from ocapi.step_detection.step_detection import step_detection

def run_pipeline(arrete_files: list[ArreteFile], arrete_ids_included: set[ArreteId])-> Permis:
    operations : list[Operation] = [] 
    modele = DEFAULT_LLM_MODEL
    for arrete_file in arrete_files:
        docs: list[Document]; img_map:ImageMap = step_chunking(arrete_file)
        operations.extend(step_detection(docs, arrete_file.id, modele, img_map))

    filtered_operations = operations[:]
    if arrete_ids_included:
        filtered_operations = filter(
            lambda operation: (
                (operation.source_id.arrete_id in arrete_ids_included) 
                and (operation.target_id.arrete_id in arrete_ids_included)
            )
        )

    versions : list[ArticlesContentMap] = step_resolution(filtered_operations)
    # ajouter à la sortie : le delta entre versions ? 
    # modifier le type articlescontentmap pour que chaque le dict contienne nodeId, content, bool de si modifié ?
    permis = step_rendering(versions, arrete_files)


    return permis
