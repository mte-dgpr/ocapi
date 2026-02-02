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
"""
Constantes partagées pour OCAPI.

Ce module sert de couche de compatibilité. Toutes les valeurs
proviennent désormais de ocapi.config.settings.
"""

from ocapi.config import settings

# Chemins
PROJECT_ROOT = settings.paths.project_root
CATALOGUE_PATH = settings.paths.catalogue_path

# Pipeline
DEFAULT_LLM_MODEL = settings.pipeline.default_llm_model
FULL_SECTION = settings.pipeline.full_section
