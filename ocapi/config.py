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
Configuration centralisée pour OCAPI.

Ce module utilise Pydantic Settings pour charger et valider
la configuration depuis les variables d'environnement et fichiers .env.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Racine du projet (calculée une seule fois)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LLMConfig(BaseSettings):
    """Configuration des APIs LLM."""

    model_config = SettingsConfigDict(env_prefix="")

    # PIAG API (défaut pour le MTE)
    piag_api_key: str | None = Field(default=None)
    piag_api_url: str = Field(default="https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions")

    # OpenAI API (optionnel)
    openai_api_key: str | None = Field(default=None)
    openai_api_url: str = Field(default="https://api.openai.com/v1/chat/completions")


class PipelineConfig(BaseSettings):
    """Configuration du pipeline de traitement."""

    model_config = SettingsConfigDict(env_prefix="")

    default_llm_model: str = Field(default="mte-api-piag-mistral-medium-latest")
    # Placeholder pour indiquer au LLM d'insérer la section complète
    full_section: str = Field(default="contenu entier")


class PathsConfig(BaseSettings):
    """Configuration des chemins de fichiers."""

    model_config = SettingsConfigDict(env_prefix="")

    # Racine du projet (défaut: répertoire parent du package ocapi)
    project_root: Path = Field(default=_PROJECT_ROOT)
    # Chemin vers le catalogue des arrêtés
    catalogue_path: Path = Field(
        default=_PROJECT_ROOT / "data" / "0005804239" / "journaux" / "catalogue_ap.json"
    )


class AppConfig(BaseSettings):
    """Configuration principale de l'application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)


# Instance singleton de la configuration
settings = AppConfig()
