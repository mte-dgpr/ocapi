
from ocapi.step_resolution.apply_ops import ArticlesContentMap, apply_all_operations, build_initial_articles_content_map
from ocapi.step_resolution.build_op_graph import build_graph
from ocapi.types import ArreteFile, Operation

# TODO : liste version doit avoir un élément par AP. les APC doivent etre listés dans l'ordre chronologique. et versions c les articles cibles dans l'ordre chrono 


def step_resolution(operations: list[Operation],
                     arrete_files: list[ArreteFile]) -> list[ArticlesContentMap]:
    operations_graph = build_graph(operations)
    initial_articles_content = build_initial_articles_content_map(operations_graph, arrete_files)
    versions: list[ArticlesContentMap] = apply_all_operations(
        operations_graph, 
        arrete_files, 
        initial_articles_content
    )
    return versions
    
   