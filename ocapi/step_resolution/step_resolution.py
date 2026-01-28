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
from ocapi.step_resolution.apply_ops import apply_all_operations, build_initial_articles_content_map
from ocapi.step_resolution.build_op_graph import build_graph
from ocapi.types import ArreteFile, ArticlesContentMap, Operation


def step_resolution(
    operations: list[Operation], arrete_files: list[ArreteFile]
) -> list[ArticlesContentMap]:
    operations_graph = build_graph(operations)
    initial_articles_content = build_initial_articles_content_map(operations_graph, arrete_files)
    versions: list[ArticlesContentMap] = apply_all_operations(
        operations_graph, arrete_files, initial_articles_content
    )
    return versions
