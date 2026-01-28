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

Ce module sert de couche de compatibilité. Les valeurs configurables
proviennent désormais de ocapi.config.settings.
"""

from pathlib import Path

from ocapi.config import settings

# Project root = repository root (parent of the top-level package directory)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_PATH = PROJECT_ROOT / "data" / "0005804239" / "journaux" / "catalogue_ap.json"
FULL_SECTION = "contenu entier"  # placeholder pour indiquer au LLM d'insérer la section complète

# Valeur issue de la configuration centralisée
DEFAULT_LLM_MODEL = settings.pipeline.default_llm_model
