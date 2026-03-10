#
# Copyright (c) 2025 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from ocapi.step_resolution.apply_ops import apply_all_ops
from ocapi.step_resolution.build_op_graph import build_graph
from ocapi.types import ArreteFile, ArticleHistory, Operation
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def step_resolution(
    operations: list[Operation], arrete_files: list[ArreteFile]
) -> tuple[ArticleHistory, list[ArreteFile]]:
    """Construit l'historique des articles en appliquant les opérations détectées.

    Construit le graphe des opérations, puis applique chaque opération dans
    l'ordre chronologique des arrêtés. Met à jour le statut des arrêtés abrogés.

    Parameters
    ----------
    operations : list[Operation]
        Opérations détectées par `step_detection`.
    arrete_files : list[ArreteFile]
        Arrêtés disponibles, triés chronologiquement.

    Returns
    -------
    ArticleHistory
        Historique complet des versions de chaque article modifié,
        indexé par `NodeId(arrete_id, article_id)`.
    list[ArreteFile]
        Arrêtés mis à jour (champ `status` à `False` pour les abrogés).
    """
    _LOGGER.info(f"Résolution: {len(operations)} opération(s) à traiter")
    operations_graph, arrete_files, skipped_ops_graph = build_graph(operations, arrete_files)
    history, skipped_ops_apply = apply_all_ops(
        operations_graph,
        arrete_files,
    )
    _LOGGER.info(f"Résolution: {len(history)} article(s) dans l'historique")
    return history, arrete_files
