from ocapi.step_resolution.apply_ops import ArticlesContentMap
from ocapi.types import ArreteFile


def step_rendering(arretes_versions: list[ArticlesContentMap],
                   arrete_files: list[ArreteFile]) -> Permis:
    contenu_permis = make_initial_contenu_permis(arrete_files)
    header_permis = make_header_permis(arrete_files)
    annexes_permis = make_annexes_permis(arrete_files)
    for arrete_version in arretes_versions:
        for article_id, article_content in arrete_version.items():
            contenu_permis.articles[article_id] = article_content
    return Permis(header_permis, contenu_permis, annexes_permis)