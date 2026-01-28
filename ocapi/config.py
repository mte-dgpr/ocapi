"""
Configuration centralisée pour OCAPI.

Ce module utilise Pydantic Settings pour charger et valider
la configuration depuis les variables d'environnement et fichiers .env.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class AppConfig(BaseSettings):
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
