

from bs4 import BeautifulSoup
from ocapi.types import ArreteFile, Operation


def has_no_ops(arrete_file:ArreteFile, operations:list[Operation]) -> bool:
    for op in operations:
        if op.source_id == arrete_file.id:
            return False
    return True

def detect_additional_prescriptions(arrete_files: list[ArreteFile]) -> str:
    pass # TODO : refaire des appels LLM pour détecter les prescriptions additionnelles non modificatives ? à voir.

def extract_main(soup: BeautifulSoup) -> str:
    main = soup.find("main")
    if main is None:
        return ""  
    return str(main)
    

def make_other_permis(arrete_files: list[ArreteFile], operations: list[Operation]) -> str:
    other_str = ""
    for arrete_file in arrete_files:
        if arrete_file.ordered_index > 0:
            if arrete_file.status and has_no_ops(arrete_file, operations): 
                other_str += f"Contenu de l'arrêté complémentaire {arrete_file.id} : {extract_main(arrete_file.soup)}"
    return other_str
                                    