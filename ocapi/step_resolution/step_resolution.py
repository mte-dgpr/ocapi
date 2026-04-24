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
    operations: list[Operation],
    arrete_files: list[ArreteFile],
    *,
    enable_llm: bool = True,
) -> tuple[ArticleHistory, list[ArreteFile], list[Operation]]:
    """Build the article history by applying the detected operations.

    Builds the operations graph, then applies each operation in chronological
    order. Updates the status of abrogated arrêtés and writes back the
    resolved ``status_code`` onto each operation.

    Parameters
    ----------
    operations : list[Operation]
        Operations detected by ``step_detection``.
    arrete_files : list[ArreteFile]
        Available arrêtés, sorted chronologically.
    enable_llm : bool
        When ``False``, complex sub-targets that require LLM consolidation
        are skipped with ``DISABLED_LLM_CALL`` instead of calling the LLM.

    Returns
    -------
    ArticleHistory
        Complete version history of each modified article,
        indexed by ``NodeId(arrete_id, article_id)``.
    list[ArreteFile]
        Updated arrêtés (``status`` set to ``False`` for abrogated ones).
    list[Operation]
        Operations with their resolved ``status_code``.
    """
    _LOGGER.info(f"Resolution: {len(operations)} operation(s) to process")
    operations_graph, arrete_files, skipped_ops_graph, graph_ops = build_graph(
        operations, arrete_files
    )
    history, skipped_ops_apply, resolved_status = apply_all_ops(
        operations_graph,
        arrete_files,
        enable_llm=enable_llm,
    )

    updated_ops = [
        (
            op.model_copy(update={"status_code": resolved_status[op.id]})
            if op.id in resolved_status
            else op
        )
        for op in graph_ops
    ]

    _LOGGER.info(f"Resolution: {len(history)} article(s) in history")
    return history, arrete_files, updated_ops
