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
from ocapi.constants import DEFAULT_LLM_MODEL
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.step_detection.step_detection import step_detection
from ocapi.step_rendering.step_rendering import step_rendering
from ocapi.step_resolution.step_resolution import step_resolution
from ocapi.types import ArreteFile, ArreteId, ArticlesContentMap, Operation, Permis


def run_pipeline(arrete_files: list[ArreteFile], arrete_ids_included: set[ArreteId]) -> Permis:
    operations: list[Operation] = []
    modele = DEFAULT_LLM_MODEL

    for arrete_file in arrete_files:
        docs, img_map = step_chunking(arrete_file)
        operations.extend(step_detection(docs, arrete_file.id, modele, img_map))

    filtered_operations = operations[:]
    if arrete_ids_included:
        filtered_operations = [
            operation
            for operation in filtered_operations
            if operation.source_id.arrete_id in arrete_ids_included
            and operation.target_id.arrete_id in arrete_ids_included
        ]

    versions: list[ArticlesContentMap] = step_resolution(filtered_operations, arrete_files)
    permis = step_rendering(versions, arrete_files)
    return permis
