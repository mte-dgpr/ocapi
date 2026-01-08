
from ocapi.step_resolution.apply_ops import apply_all_ops
from ocapi.step_resolution.build_op_graph import build_graph
from ocapi.types import ArreteFile, ArticleHistory, Operation

# TODO : liste version doit avoir un élément par AP. les APC doivent etre listés dans l'ordre chronologique. et versions c les articles cibles dans l'ordre chrono 
# TODO : gérer les erreurs d'application des opérations (ex: article source non trouvé)
# TODO : changer le type de versions, pour conserver juste les modifs par rapport à la version précédente (gain de place)

def step_resolution(operations: list[Operation],
                     arrete_files: list[ArreteFile]) -> ArticleHistory:
    operations_graph, arrete_files, skipped_ops_graph = build_graph(operations, arrete_files)
    history, skipped_ops_apply = apply_all_ops(
        operations_graph, 
        arrete_files, 
    )
    return history, arrete_files
    
   