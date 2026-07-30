#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
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
Centralised configuration for OCAPI.

This module uses Pydantic Settings to load and validate configuration
from environment variables and .env files.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Package and project roots (computed once)
_PACKAGE_ROOT = Path(__file__).resolve().parent
_REPOSITORY_ROOT = _PACKAGE_ROOT.parent


def _default_project_root() -> Path:
    """Return the most suitable default root for bundled assets.

    In editable/source installs assets live at repository root (``config/``, ``templates/``).
    In wheel installs assets are bundled under the package directory.
    """

    expected_template = Path("templates/permis_consolide.html")
    if (_REPOSITORY_ROOT / expected_template).exists():
        return _REPOSITORY_ROOT
    if (_PACKAGE_ROOT / expected_template).exists():
        return _PACKAGE_ROOT
    return _REPOSITORY_ROOT


_PROJECT_ROOT = _default_project_root()

# Type alias for logging levels
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Supported Arrêtify version
# OCAPI relies on the semantic HTML format produced by Arrêtify.
# The supported major.minor must match the installed arretify package.
# Different major/minor versions may introduce breaking changes to the HTML format
# (data-spec attributes, CSS classes, document structure).
try:
    from importlib.metadata import version as _pkg_version

    _ARRETIFY_VERSION = _pkg_version("arretify")
    _major, _minor, *_ = _ARRETIFY_VERSION.split(".")
    SUPPORTED_ARRETIFY_VERSION = f"{_major}.{_minor}.X"
    SUPPORTED_ARRETIFY_VERSION_PATTERN = rf"^{_major}\.{_minor}\.\d+$"
except Exception:
    SUPPORTED_ARRETIFY_VERSION = "0.2.X"
    SUPPORTED_ARRETIFY_VERSION_PATTERN = r"^0\.2\.\d+$"


class FullSectionName(str, Enum):
    """All known names the LLM may use to indicate a full-section operation.

    Centralises the different appellations so that detection and resolution
    logic always resolve to the same canonical type, regardless of which
    variant the model chose to return.

    Example:
        >>> FullSectionName.CONTENU_ENTIER.value
        'contenu entier'
        >>> FullSectionName.ALL.value
        'ALL'
        >>> FullSectionName.TOUT.value
        'tout'
        >>> {name.value for name in FullSectionName}
        {'contenu entier', 'ALL', 'tout'}
    """

    CONTENU_ENTIER = "contenu entier"
    ALL = "ALL"
    TOUT = "tout"


class LLMConfig(BaseSettings):
    """Configuration for LLM APIs.

    Attributes:
        piag_api_key: PIAG API key (optional, may be None in dev).
        piag_api_url: PIAG API endpoint URL.
        openai_api_key: OpenAI API key (optional).
        openai_api_url: OpenAI API endpoint URL.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        validate_assignment=True,
    )

    # PIAG API (default for MTE)
    piag_api_key: str | None = Field(
        default=None,
        description="API key for the PIAG service",
    )
    piag_api_url: str = Field(
        default="https://preprod.api.piag.e2.rie.gouv.fr/v1/chat/completions",
        description="PIAG endpoint URL",
    )

    # Mistral API (optional)
    mistral_api_key: str | None = Field(
        default=None,
        description="API key for Mistral",
    )
    mistral_api_url: str = Field(
        default="https://api.mistral.ai/v1/chat/completions",
        description="Mistral endpoint URL",
    )

    # OpenAI API (optional)
    openai_api_key: str | None = Field(
        default=None,
        description="API key for OpenAI",
    )
    openai_api_url: str = Field(
        default="https://api.openai.com/v1/chat/completions",
        description="OpenAI endpoint URL",
    )

    # Anthropic API (optional)
    anthropic_api_key: str | None = Field(
        default=None,
        description="API key for Anthropic",
    )
    anthropic_api_url: str = Field(
        default="https://api.anthropic.com/v1/messages",
        description="Anthropic endpoint URL",
    )

    # Google API (optional)
    google_api_key: str | None = Field(
        default=None,
        description="API key for Google (Gemini)",
    )
    google_api_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        description="Google Gemini endpoint URL (OpenAI-compatible)",
    )

    # Deepseek API (optional)
    deepseek_api_key: str | None = Field(
        default=None,
        description="API key for Deepseek",
    )
    deepseek_api_url: str = Field(
        default="https://api.deepseek.com/chat/completions",
        description="Deepseek endpoint URL",
    )

    @field_validator(
        "piag_api_key",
        "mistral_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "google_api_key",
        "deepseek_api_key",
    )
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate that API keys are not empty when provided."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("API key cannot be empty")
        return v

    @field_validator(
        "piag_api_url", "mistral_api_url", "openai_api_url", "anthropic_api_url", "google_api_url"
    )
    @classmethod
    def validate_api_url(cls, v: str) -> str:
        """Validate that the URL is well-formed."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("API URL must start with http:// or https://")
        return v

    @model_validator(mode="after")
    def validate_at_least_one_api(self) -> "LLMConfig":
        """Verify that at least one API is configured (key present)."""
        if not self.piag_api_key and not self.openai_api_key:
            # Allow missing keys in dev/test environments
            pass
        return self


class PathsConfig(BaseSettings):
    """Configuration for file paths.

    Attributes:
        project_root: Project root (default: parent directory of the ocapi package).
        catalogue_path: Path to the arrêté catalogue.

    Example:
        >>> paths = PathsConfig()
        >>> assert paths.project_root.exists()
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        validate_assignment=True,
    )

    # Project root (default: parent directory of the ocapi package)
    project_root: Path = Field(
        default=_PROJECT_ROOT,
        description="Project root directory",
    )
    # Path to the arrêté catalogue
    catalogue_path: Path = Field(
        default=_PROJECT_ROOT / "data" / "0005804239" / "journaux" / "catalogue_ap.json",
        description="Path to the arrêté catalogue",
    )
    # Path to the consolidated permit HTML template
    permis_template_path: Path = Field(
        default=_PROJECT_ROOT / "templates" / "permis_consolide.html",
        description="Path to the consolidated permit HTML template",
    )
    # Default input directory for arrêté HTML files
    input_dir: Path | None = Field(default=None)
    # Default output path for the consolidated permit
    output_file: Path | None = Field(default=None)

    @field_validator("project_root")
    @classmethod
    def validate_project_root(cls, v: Path) -> Path:
        """Validate that the project root exists."""
        if not v.exists():
            raise ValueError(f"Project root directory does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Project root must be a directory: {v}")
        return v

    @field_validator("catalogue_path")
    @classmethod
    def validate_catalogue_path(cls, v: Path) -> Path:
        """Validate the catalogue path (may not yet exist)."""
        return v

    @field_validator("permis_template_path")
    @classmethod
    def validate_permis_template_path(cls, v: Path) -> Path:
        """Validate that the consolidated permit HTML template exists."""
        if not v.exists():
            raise ValueError(f"Consolidated permit HTML template not found: {v}")
        if not v.is_file():
            raise ValueError(f"Consolidated permit template must be a file: {v}")
        return v.resolve()


class LoggingConfig(BaseSettings):
    """Configuration for the logging system.

    Attributes:
        level: Default logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Log file path (None to disable file logging).
        max_bytes: Maximum log file size before rotation (in bytes).
        backup_count: Number of backup files to keep.
        use_timed_rotation: If True, enable daily rotation in addition to size-based rotation.
        console_output: If True, print logs to the console.

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
        description="Default logging level",
    )
    log_file: Path | None = Field(
        default=None,
        description="Log file path (None to disable)",
    )
    max_bytes: int = Field(
        default=1024 * 1024,  # 1024 KB
        ge=1024,  # Minimum 1 KB
        description="Maximum log file size before rotation (bytes)",
    )
    backup_count: int = Field(
        default=5,
        ge=0,
        le=100,
        description="Number of backup files to keep",
    )
    use_timed_rotation: bool = Field(
        default=True,
        description="Enable daily rotation",
    )
    console_output: bool = Field(
        default=True,
        description="Print logs to the console",
    )

    @field_validator("log_file")
    @classmethod
    def validate_log_file(cls, v: Path | None) -> Path | None:
        """Validate the log file path."""
        if v is None:
            return None
        # Do not check existence; the file will be created automatically
        return v


class AppConfig(BaseSettings):
    """Main application configuration.

    Combines all sub-configurations (LLM, Paths, Logging) and
    automatically loads environment variables from a .env file.

    Attributes:
        llm: LLM API configuration.
        paths: File path configuration.
        logging: Logging system configuration.

    Example:
        >>> config = AppConfig()
        >>> print(config.llm.piag_api_url)
        >>> print(config.paths.project_root)
        >>> print(config.logging.level)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # Allows LOGGING__LEVEL=DEBUG
        extra="ignore",
        validate_assignment=True,
    )

    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM API configuration",
    )
    paths: PathsConfig = Field(
        default_factory=PathsConfig,
        description="Path configuration",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )

    @model_validator(mode="after")
    def validate_complete_config(self) -> "AppConfig":
        """Validate overall configuration consistency."""
        if not self.paths.project_root.exists():
            raise ValueError(f"Invalid project root: {self.paths.project_root}")
        return self

    def model_dump_safe(self) -> dict[str, Any]:
        """Export configuration without secrets (API keys masked)."""
        data = self.model_dump()
        if data.get("llm", {}).get("piag_api_key"):
            data["llm"]["piag_api_key"] = "***MASKED***"
        if data.get("llm", {}).get("mistral_api_key"):
            data["llm"]["mistral_api_key"] = "***MASKED***"
        if data.get("llm", {}).get("openai_api_key"):
            data["llm"]["openai_api_key"] = "***MASKED***"
        if data.get("llm", {}).get("anthropic_api_key"):
            data["llm"]["anthropic_api_key"] = "***MASKED***"
        if data.get("llm", {}).get("google_api_key"):
            data["llm"]["google_api_key"] = "***MASKED***"
        if data.get("llm", {}).get("deepseek_api_key"):
            data["llm"]["deepseek_api_key"] = "***MASKED***"
        return data


settings = AppConfig()


def reload_settings() -> AppConfig:
    """Reload the configuration (useful for tests).

    Returns:
        A new AppConfig instance.

    Example:
        >>> from ocapi.config import reload_settings
        >>> new_settings = reload_settings()
    """
    return AppConfig()


__all__ = [
    "AppConfig",
    "LLMConfig",
    "PathsConfig",
    "LoggingConfig",
    "LogLevel",
    "FullSectionName",
    "settings",
    "reload_settings",
    "SUPPORTED_ARRETIFY_VERSION",
    "SUPPORTED_ARRETIFY_VERSION_PATTERN",
]
