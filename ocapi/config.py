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
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Racine du projet (calculée une seule fois)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Type pour les niveaux de logging
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Version Arrêtify supportée
# OCAPI s'appuie sur le format HTML sémantique généré par Arrêtify.
# Seule la version 0.1.X est actuellement supportée (0.1.0, 0.1.1, etc.)
# Les versions majeures/mineures différentes peuvent introduire des breaking changes
# dans le format HTML (attributs data-spec, classes CSS, structure du document).
SUPPORTED_ARRETIFY_VERSION = "0.1.X"
SUPPORTED_ARRETIFY_VERSION_PATTERN = r"^0\.1\.\d+$"


class LLMConfig(BaseSettings):
    """Configuration des APIs LLM.

    Attributes:
        piag_api_key: Clé API pour PIAG (optionnel, peut être None en dev)
        piag_api_url: URL de l'API PIAG
        openai_api_key: Clé API pour OpenAI (optionnel)
        openai_api_url: URL de l'API OpenAI
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
    piag_api_url: str = Field(
        default="https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions",
        description="URL de l'endpoint PIAG",
    )

    # Mistral API (optionnel)
    mistral_api_key: str | None = Field(
        default=None,
        description="Clé API pour Mistral",
    )
    mistral_api_url: str = Field(
        default="https://api.mistral.ai/v1/chat/completions",
        description="URL de l'endpoint Mistral",
    )

    # OpenAI API (optionnel)
    openai_api_key: str | None = Field(
        default=None,
        description="Clé API pour OpenAI",
    )
    openai_api_url: str = Field(
        default="https://api.openai.com/v1/chat/completions",
        description="URL de l'endpoint OpenAI",
    )

    @field_validator("piag_api_key", "mistral_api_key", "openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Valider le format des clés API (non vide si fournie)."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("La clé API ne peut pas être vide")
        return v

    @field_validator("piag_api_url", "mistral_api_url", "openai_api_url")
    @classmethod
    def validate_api_url(cls, v: str) -> str:
        """Valider que l'URL est bien formée."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("L'URL de l'API doit commencer par http:// ou https://")
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
        full_section: Placeholder pour indiquer au LLM d'insérer la section complète

    Example:
        >>> pipeline = PipelineConfig(full_section="contenu entier")
        >>> print(pipeline.full_section)
        contenu entier
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        validate_assignment=True,
    )

    # Placeholder pour indiquer au LLM d'insérer la section complète
    full_section: str = Field(
        default="contenu entier",
        description="Placeholder pour indiquer l'insertion de section complète",
        min_length=1,
    )

    @field_validator("full_section")
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
    # Chemin vers le template HTML fixe du permis consolidé
    permis_template_path: Path = Field(
        default=_PROJECT_ROOT / "templates" / "permis_consolide.html",
        description="Chemin vers le template HTML du permis consolidé",
    )
    # Chemin d'entrée par défaut pour les arrêtés HTML
    input_dir: Path | None = Field(default=None)
    # Chemin de sortie par défaut pour le permis consolidé
    output_file: Path | None = Field(default=None)

    @field_validator("project_root")
    @classmethod
    def validate_project_root(cls, v: Path) -> Path:
        """Valider que la racine du projet existe."""
        if not v.exists():
            raise ValueError(f"Le répertoire racine n'existe pas: {v}")
        if not v.is_dir():
            raise ValueError(f"La racine du projet doit être un répertoire: {v}")
        return v

    @field_validator("catalogue_path")
    @classmethod
    def validate_catalogue_path(cls, v: Path) -> Path:
        """Valider le chemin du catalogue (peut ne pas exister encore)."""
        # On vérifie juste que le chemin parent existe ou peut être créé
        # Le fichier lui-même peut ne pas encore exister
        return v

    @field_validator("permis_template_path")
    @classmethod
    def validate_permis_template_path(cls, v: Path) -> Path:
        """Valider que le template HTML du permis consolidé existe."""
        if not v.exists():
            raise ValueError(f"Template HTML du permis consolidé introuvable: {v}")
        if not v.is_file():
            raise ValueError(f"Le template du permis consolidé doit être un fichier: {v}")
        return v.resolve()


class LoggingConfig(BaseSettings):
    """Configuration du système de logging.

    Attributes:
        level: Niveau de logging par défaut (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Chemin du fichier de log (None pour désactiver le logging fichier)
        max_bytes: Taille maximale d'un fichier de log avant rotation (en octets)
        backup_count: Nombre de fichiers de backup à conserver
        use_timed_rotation: Si True, rotation quotidienne en plus de la rotation par taille
        console_output: Si True, affiche les logs dans la console

    Example:
        >>> logging = LoggingConfig(level="DEBUG")
        >>> print(logging.level)
        DEBUG
    """

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        validate_assignment=True,
    )

    level: LogLevel = Field(
        default="INFO",
        description="Niveau de logging par défaut",
    )
    log_file: Path | None = Field(
        default=None,
        description="Chemin du fichier de log (None pour désactiver)",
    )
    max_bytes: int = Field(
        default=1024 * 1024,  # 1024 KB
        ge=1024,  # Minimum 1 KB
        description="Taille maximale d'un fichier de log avant rotation (octets)",
    )
    backup_count: int = Field(
        default=5,
        ge=0,
        le=100,
        description="Nombre de fichiers de backup à conserver",
    )
    use_timed_rotation: bool = Field(
        default=True,
        description="Activer la rotation quotidienne",
    )
    console_output: bool = Field(
        default=True,
        description="Afficher les logs dans la console",
    )

    @field_validator("log_file")
    @classmethod
    def validate_log_file(cls, v: Path | None) -> Path | None:
        """Valider le chemin du fichier de log."""
        if v is None:
            return None
        # On ne vérifie pas l'existence car le fichier sera créé automatiquement
        return v


class AppConfig(BaseSettings):
    """Configuration principale de l'application.

    Cette classe combine toutes les configurations (LLM, Pipeline, Paths, Logging)
    et charge automatiquement les variables d'environnement depuis .env.

    Attributes:
        llm: Configuration des APIs LLM
        pipeline: Configuration du pipeline de traitement
        paths: Configuration des chemins de fichiers
        logging: Configuration du système de logging

    Example:
        >>> config = AppConfig()
        >>> print(config.llm.piag_api_url)
        >>> print(config.pipeline.full_section)
        >>> print(config.paths.project_root)
        >>> print(config.logging.level)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # Permet PIPELINE__FULL_SECTION=... ou LOGGING__LEVEL=DEBUG
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
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Configuration du logging",
    )

    @model_validator(mode="after")
    def validate_complete_config(self) -> "AppConfig":
        """Valider la cohérence globale de la configuration."""
        # Vérifier que le projet est correctement initialisé
        if not self.paths.project_root.exists():
            raise ValueError(f"Racine du projet invalide: {self.paths.project_root}")
        return self

    def model_dump_safe(self) -> dict[str, Any]:
        """Exporter la configuration sans les secrets (clés API)."""
        data = self.model_dump()
        # Masquer les clés API
        if data.get("llm", {}).get("piag_api_key"):
            data["llm"]["piag_api_key"] = "***MASKED***"
        if data.get("llm", {}).get("mistral_api_key"):
            data["llm"]["mistral_api_key"] = "***MASKED***"
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
    "LoggingConfig",
    "LogLevel",
    "settings",
    "reload_settings",
    "SUPPORTED_ARRETIFY_VERSION",
    "SUPPORTED_ARRETIFY_VERSION_PATTERN",
]
