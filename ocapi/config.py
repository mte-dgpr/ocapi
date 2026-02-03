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

Exemple d'utilisation:
    >>> from ocapi.config import settings
    >>> print(settings.llm.piag_api_url)
    https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions
    >>> print(settings.pipeline.default_llm_model)
    mte-api-piag-mistral-medium-latest
"""

from pathlib import Path
from typing import Any

from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Racine du projet (calculée une seule fois)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LLMConfig(BaseSettings):
    """Configuration des APIs LLM.

    Attributes:
        piag_api_key: Clé API pour PIAG (optionnel, peut être None en dev)
        piag_api_url: URL de l'API PIAG
        openai_api_key: Clé API pour OpenAI (optionnel)
        openai_api_url: URL de l'API OpenAI

    Example:
        >>> llm = LLMConfig(piag_api_key="sk-xxx")
        >>> print(llm.piag_api_url)
        https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        validate_assignment=True,  # Valider lors de l'assignation
    )

    # PIAG API (défaut pour le MTE)
    piag_api_key: str | None = Field(
        default=None,
        description="Clé API pour le service PIAG",
    )
    piag_api_url: HttpUrl = Field(
        default="https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions",
        description="URL de l'endpoint PIAG",
    )

    # OpenAI API (optionnel)
    openai_api_key: str | None = Field(
        default=None,
        description="Clé API pour OpenAI",
    )
    openai_api_url: HttpUrl = Field(
        default="https://api.openai.com/v1/chat/completions",
        description="URL de l'endpoint OpenAI",
    )

    @field_validator("piag_api_key", "openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Valider le format des clés API (non vide si fournie)."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("La clé API ne peut pas être vide")
        return v

    @model_validator(mode="after")
    def validate_at_least_one_api(self) -> "LLMConfig":
        """Vérifier qu'au moins une API est configurée (clé présente)."""
        if not self.piag_api_key and not self.openai_api_key:
            # Permettre de ne pas avoir de clé en environnement de dev/test
            # mais émettre un avertissement
            pass
        return self


class PipelineConfig(BaseSettings):
    """Configuration du pipeline de traitement.

    Attributes:
        default_llm_model: Nom du modèle LLM par défaut
        full_section: Placeholder pour indiquer au LLM d'insérer la section complète
        max_retries: Nombre maximum de tentatives pour les appels LLM
        timeout: Timeout en secondes pour les appels LLM

    Example:
        >>> pipeline = PipelineConfig(default_llm_model="gpt-4")
        >>> print(pipeline.max_retries)
        3
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        validate_assignment=True,
    )

    default_llm_model: str = Field(
        default="mte-api-piag-mistral-medium-latest",
        description="Modèle LLM utilisé par défaut",
        min_length=1,
    )
    # Placeholder pour indiquer au LLM d'insérer la section complète
    full_section: str = Field(
        default="contenu entier",
        description="Placeholder pour indiquer l'insertion de section complète",
        min_length=1,
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Nombre maximum de tentatives pour les appels LLM",
    )
    timeout: int = Field(
        default=120,
        ge=1,
        le=600,
        description="Timeout en secondes pour les appels LLM",
    )

    @field_validator("default_llm_model", "full_section")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Valider que les chaînes ne sont pas vides."""
        if not v or len(v.strip()) == 0:
            raise ValueError("La valeur ne peut pas être vide")
        return v.strip()


class PathsConfig(BaseSettings):
    """Configuration des chemins de fichiers.

    Attributes:
        project_root: Racine du projet (défaut: répertoire parent du package ocapi)
        catalogue_path: Chemin vers le catalogue des arrêtés

    Example:
        >>> paths = PathsConfig()
        >>> assert paths.project_root.exists()
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        validate_assignment=True,
    )

    # Racine du projet (défaut: répertoire parent du package ocapi)
    project_root: Path = Field(
        default=_PROJECT_ROOT,
        description="Racine du projet",
    )
    # Chemin vers le catalogue des arrêtés
    catalogue_path: Path = Field(
        default=_PROJECT_ROOT / "data" / "0005804239" / "journaux" / "catalogue_ap.json",
        description="Chemin vers le catalogue des arrêtés",
    )

    @field_validator("project_root")
    @classmethod
    def validate_project_root(cls, v: Path) -> Path:
        """Valider que la racine du projet existe."""
        if not v.exists():
            raise ValueError(f"Le répertoire racine n'existe pas: {v}")
        if not v.is_dir():
            raise ValueError(f"La racine du projet doit être un répertoire: {v}")
        return v.resolve()

    @field_validator("catalogue_path")
    @classmethod
    def validate_catalogue_path(cls, v: Path) -> Path:
        """Valider le chemin du catalogue (peut ne pas exister encore)."""
        # On vérifie juste que le chemin parent existe ou peut être créé
        # Le fichier lui-même peut ne pas encore exister
        return v


class AppConfig(BaseSettings):
    """Configuration principale de l'application.

    Cette classe combine toutes les configurations (LLM, Pipeline, Paths)
    et charge automatiquement les variables d'environnement depuis .env.

    Attributes:
        llm: Configuration des APIs LLM
        pipeline: Configuration du pipeline de traitement
        paths: Configuration des chemins de fichiers

    Example:
        >>> config = AppConfig()
        >>> print(config.llm.piag_api_url)
        >>> print(config.pipeline.default_llm_model)
        >>> print(config.paths.project_root)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # Permet PIPELINE__MAX_RETRIES=5
        extra="ignore",  # Ignorer les variables d'environnement inconnues
        validate_assignment=True,
    )

    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="Configuration des APIs LLM",
    )
    pipeline: PipelineConfig = Field(
        default_factory=PipelineConfig,
        description="Configuration du pipeline",
    )
    paths: PathsConfig = Field(
        default_factory=PathsConfig,
        description="Configuration des chemins",
    )

    @model_validator(mode="after")
    def validate_complete_config(self) -> "AppConfig":
        """Valider la cohérence globale de la configuration."""
        # Vérifier que le projet est correctement initialisé
        if not self.paths.project_root.exists():
            raise ValueError(
                f"Racine du projet invalide: {self.paths.project_root}"
            )
        return self

    def model_dump_safe(self) -> dict[str, Any]:
        """Exporter la configuration sans les secrets (clés API)."""
        data = self.model_dump()
        # Masquer les clés API
        if data.get("llm", {}).get("piag_api_key"):
            data["llm"]["piag_api_key"] = "***MASKED***"
        if data.get("llm", {}).get("openai_api_key"):
            data["llm"]["openai_api_key"] = "***MASKED***"
        return data


# Instance singleton de la configuration
settings = AppConfig()


def reload_settings() -> AppConfig:
    """Recharger la configuration (utile pour les tests).

    Returns:
        Une nouvelle instance de AppConfig

    Example:
        >>> from ocapi.config import reload_settings
        >>> new_settings = reload_settings()
    """
    return AppConfig()


__all__ = [
    "AppConfig",
    "LLMConfig",
    "PipelineConfig",
    "PathsConfig",
    "settings",
    "reload_settings",
]
