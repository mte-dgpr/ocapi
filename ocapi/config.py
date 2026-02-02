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

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):  # type: ignore[misc]
    """Configuration des APIs LLM."""

    model_config = SettingsConfigDict(env_prefix="")

    # PIAG API (défaut pour le MTE)
    piag_api_key: str | None = Field(default=None)
    piag_api_url: str = Field(default="https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions")

    # OpenAI API (optionnel)
    openai_api_key: str | None = Field(default=None)
    openai_api_url: str = Field(default="https://api.openai.com/v1/chat/completions")


class PipelineConfig(BaseSettings):  # type: ignore[misc]
    """Configuration du pipeline de traitement."""

    model_config = SettingsConfigDict(env_prefix="")

    default_llm_model: str = Field(default="mte-api-piag-mistral-medium-latest")


class AppConfig(BaseSettings):  # type: ignore[misc]
    """Configuration principale de l'application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)


# Instance singleton de la configuration
settings = AppConfig()
