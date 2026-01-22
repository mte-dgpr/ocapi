from bs4 import BeautifulSoup
from ocapi.step_rendering.make_header import make_header_permis
from ocapi.step_rendering.make_main_content import make_contenu_permis
from ocapi.step_rendering.make_other import make_other_permis
from ocapi.types import ArreteFile, ArticleHistory, Operation, Permis

# TODO : faire un fichier avec une fonction qui donne les versions pour un article.


def step_rendering(history: ArticleHistory, operations: list[Operation],
                   arrete_files: list[ArreteFile]) -> Permis:
    contenu_permis = make_contenu_permis(history, arrete_files, operations)
    header_permis = make_header_permis(arrete_files)
    other_permis = make_other_permis(arrete_files, operations=operations)
    return Permis(header=header_permis, contenu=contenu_permis, other=other_permis)

