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
"""Tests pour le module de configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ocapi.config import (
    AppConfig,
    LLMConfig,
    PathsConfig,
    PipelineConfig,
    reload_settings,
    settings,
)


class TestLLMConfig:
    """Tests pour LLMConfig."""

    def test_default_values(self) -> None:
        """Test des valeurs par défaut."""
        config = LLMConfig()
        assert config.piag_api_key is None
        assert "preprod.api.piag.e2.rie.gouv.fr" in str(config.piag_api_url)
        assert config.openai_api_key is None
        assert "api.openai.com" in str(config.openai_api_url)

    def test_valid_api_key(self) -> None:
        """Test avec une clé API valide."""
        config = LLMConfig(piag_api_key="sk-test-key-123")
        assert config.piag_api_key == "sk-test-key-123"

    def test_empty_api_key_raises_error(self) -> None:
        """Test qu'une clé API vide lève une erreur."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(piag_api_key="")
        assert "La clé API ne peut pas être vide" in str(exc_info.value)

    def test_whitespace_api_key_raises_error(self) -> None:
        """Test qu'une clé API avec uniquement des espaces lève une erreur."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(piag_api_key="   ")
        assert "La clé API ne peut pas être vide" in str(exc_info.value)

    def test_valid_custom_urls(self) -> None:
        """Test avec des URLs personnalisées."""
        config = LLMConfig(
            piag_api_url="https://custom.api.example.com/v1/chat",
            openai_api_url="https://custom.openai.example.com/v1/chat",
        )
        assert "custom.api.example.com" in str(config.piag_api_url)
        assert "custom.openai.example.com" in str(config.openai_api_url)

    def test_invalid_url_raises_error(self) -> None:
        """Test qu'une URL invalide lève une erreur."""
        with pytest.raises(ValidationError):
            LLMConfig(piag_api_url="not-a-valid-url")

    def test_http_url_accepted(self) -> None:
        """Test qu'une URL HTTP est acceptée."""
        config = LLMConfig(piag_api_url="http://localhost:8000/v1/chat")
        assert "localhost" in str(config.piag_api_url)


class TestPipelineConfig:
    """Tests pour PipelineConfig."""

    def test_default_values(self) -> None:
        """Test des valeurs par défaut."""
        config = PipelineConfig()
        assert config.default_llm_model == "primary"
        assert config.full_section == "contenu entier"
        assert config.max_retries == 3
        assert config.timeout == 120

    def test_custom_values(self) -> None:
        """Test avec des valeurs personnalisées."""
        config = PipelineConfig(
            default_llm_model="gpt-4",
            full_section="contenu complet",
            max_retries=5,
            timeout=300,
        )
        assert config.default_llm_model == "gpt-4"
        assert config.full_section == "contenu complet"
        assert config.max_retries == 5
        assert config.timeout == 300

    def test_empty_model_name_raises_error(self) -> None:
        """Test qu'un nom de modèle vide lève une erreur."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineConfig(default_llm_model="")
        # Pydantic valide min_length=1 avant le validateur personnalisé
        assert "at least 1 character" in str(
            exc_info.value
        ) or "La valeur ne peut pas être vide" in str(exc_info.value)

    def test_whitespace_model_name_raises_error(self) -> None:
        """Test qu'un nom de modèle avec uniquement des espaces lève une erreur."""
        with pytest.raises(ValidationError) as exc_info:
            PipelineConfig(default_llm_model="   ")
        assert "La valeur ne peut pas être vide" in str(exc_info.value)

    def test_model_name_strips_whitespace(self) -> None:
        """Test que les espaces sont retirés du nom de modèle."""
        config = PipelineConfig(default_llm_model="  gpt-4  ")
        assert config.default_llm_model == "gpt-4"

    def test_negative_retries_raises_error(self) -> None:
        """Test qu'un nombre négatif de tentatives lève une erreur."""
        with pytest.raises(ValidationError):
            PipelineConfig(max_retries=-1)

    def test_too_many_retries_raises_error(self) -> None:
        """Test qu'un nombre trop élevé de tentatives lève une erreur."""
        with pytest.raises(ValidationError):
            PipelineConfig(max_retries=100)

    def test_zero_timeout_raises_error(self) -> None:
        """Test qu'un timeout de zéro lève une erreur."""
        with pytest.raises(ValidationError):
            PipelineConfig(timeout=0)

    def test_negative_timeout_raises_error(self) -> None:
        """Test qu'un timeout négatif lève une erreur."""
        with pytest.raises(ValidationError):
            PipelineConfig(timeout=-1)

    def test_too_large_timeout_raises_error(self) -> None:
        """Test qu'un timeout trop grand lève une erreur."""
        with pytest.raises(ValidationError):
            PipelineConfig(timeout=1000)

    def test_boundary_values(self) -> None:
        """Test des valeurs aux limites."""
        config = PipelineConfig(max_retries=0, timeout=1)
        assert config.max_retries == 0
        assert config.timeout == 1

        config = PipelineConfig(max_retries=10, timeout=600)
        assert config.max_retries == 10
        assert config.timeout == 600


class TestPathsConfig:
    """Tests pour PathsConfig."""

    def test_default_values(self) -> None:
        """Test des valeurs par défaut."""
        config = PathsConfig()
        assert config.project_root.exists()
        assert config.project_root.is_dir()
        assert config.catalogue_path.is_absolute()

    def test_invalid_project_root_raises_error(self) -> None:
        """Test qu'une racine invalide lève une erreur."""
        invalid_path = Path("/nonexistent/path/to/project")
        with pytest.raises(ValidationError) as exc_info:
            PathsConfig(project_root=invalid_path)
        assert "n'existe pas" in str(exc_info.value)

    def test_project_root_must_be_directory(self) -> None:
        """Test que la racine doit être un répertoire."""
        # Créer un fichier temporaire
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        # Fermer le fichier avant de l'utiliser (important sur Windows)
        try:
            with pytest.raises(ValidationError) as exc_info:
                PathsConfig(project_root=tmp_path)
            assert "doit être un répertoire" in str(exc_info.value)
        finally:
            # Supprimer le fichier temporaire (même en cas d'erreur)
            try:
                tmp_path.unlink()
            except PermissionError:
                pass  # Ignorer les erreurs de permission sur Windows

    def test_custom_paths(self) -> None:
        """Test avec des chemins personnalisés."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir).resolve()
            catalogue_path = tmp_path / "custom" / "catalogue.json"
            config = PathsConfig(
                project_root=tmp_path,
                catalogue_path=catalogue_path,
            )
            assert config.project_root == tmp_path
            assert config.catalogue_path == catalogue_path


class TestAppConfig:
    """Tests pour AppConfig."""

    def test_default_values(self) -> None:
        """Test des valeurs par défaut."""
        config = AppConfig()
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.pipeline, PipelineConfig)
        assert isinstance(config.paths, PathsConfig)

    def test_nested_configuration(self) -> None:
        """Test de la configuration imbriquée."""
        config = AppConfig()
        assert config.llm.piag_api_key is None
        assert config.pipeline.default_llm_model == "primary"
        assert config.paths.project_root.exists()

    def test_model_dump_safe_masks_secrets(self) -> None:
        """Test que model_dump_safe masque les secrets."""
        config = AppConfig()
        config.llm.piag_api_key = "sk-secret-key"
        config.llm.openai_api_key = "sk-openai-secret"

        safe_dump = config.model_dump_safe()
        assert safe_dump["llm"]["piag_api_key"] == "***MASKED***"
        assert safe_dump["llm"]["openai_api_key"] == "***MASKED***"

    def test_model_dump_safe_preserves_none(self) -> None:
        """Test que model_dump_safe préserve les valeurs None."""
        config = AppConfig()
        safe_dump = config.model_dump_safe()
        assert safe_dump["llm"]["piag_api_key"] is None
        assert safe_dump["llm"]["openai_api_key"] is None

    def test_env_file_loading(self) -> None:
        """Test du chargement depuis un fichier .env."""
        # Simuler des variables d'environnement
        with patch.dict(
            os.environ,
            {
                "PIAG_API_KEY": "test-key-from-env",
                "PIPELINE__MAX_RETRIES": "5",
                "PIPELINE__TIMEOUT": "200",
            },
            clear=False,
        ):
            config = AppConfig()
            assert config.llm.piag_api_key == "test-key-from-env"
            assert config.pipeline.max_retries == 5
            assert config.pipeline.timeout == 200

    def test_validation_on_assignment(self) -> None:
        """Test que la validation fonctionne lors de l'assignation."""
        config = AppConfig()
        # Devrait lever une erreur lors de l'assignation d'une valeur invalide
        with pytest.raises(ValidationError):
            config.pipeline.max_retries = -1

    def test_extra_env_vars_ignored(self) -> None:
        """Test que les variables d'environnement inconnues sont ignorées."""
        with patch.dict(
            os.environ,
            {"UNKNOWN_CONFIG_VAR": "should-be-ignored"},
            clear=False,
        ):
            # Ne devrait pas lever d'erreur
            config = AppConfig()
            assert config is not None


class TestSettingsSingleton:
    """Tests pour l'instance singleton settings."""

    def test_settings_is_app_config(self) -> None:
        """Test que settings est une instance de AppConfig."""
        assert isinstance(settings, AppConfig)

    def test_settings_accessible(self) -> None:
        """Test que settings est accessible."""
        assert settings.llm is not None
        assert settings.pipeline is not None
        assert settings.paths is not None

    def test_settings_llm_config(self) -> None:
        """Test de la configuration LLM."""
        assert hasattr(settings.llm, "piag_api_key")
        assert hasattr(settings.llm, "piag_api_url")
        assert hasattr(settings.llm, "openai_api_key")
        assert hasattr(settings.llm, "openai_api_url")

    def test_settings_pipeline_config(self) -> None:
        """Test de la configuration Pipeline."""
        assert hasattr(settings.pipeline, "default_llm_model")
        assert hasattr(settings.pipeline, "full_section")
        assert hasattr(settings.pipeline, "max_retries")
        assert hasattr(settings.pipeline, "timeout")

    def test_settings_paths_config(self) -> None:
        """Test de la configuration Paths."""
        assert hasattr(settings.paths, "project_root")
        assert hasattr(settings.paths, "catalogue_path")
        assert settings.paths.project_root.exists()


class TestReloadSettings:
    """Tests pour la fonction reload_settings."""

    def test_reload_settings_returns_new_instance(self) -> None:
        """Test que reload_settings retourne une nouvelle instance."""
        new_settings = reload_settings()
        assert isinstance(new_settings, AppConfig)
        # Vérifier que c'est une nouvelle instance
        assert new_settings is not settings

    def test_reload_settings_with_env_changes(self) -> None:
        """Test que reload_settings prend en compte les changements d'env."""
        with patch.dict(
            os.environ,
            {"PIAG_API_KEY": "new-test-key"},
            clear=False,
        ):
            new_settings = reload_settings()
            assert new_settings.llm.piag_api_key == "new-test-key"


class TestIntegration:
    """Tests d'intégration."""

    def test_complete_configuration_flow(self) -> None:
        """Test du flux complet de configuration."""
        # Créer une configuration complète
        config = AppConfig()

        # Vérifier que tous les composants sont présents
        assert config.llm is not None
        assert config.pipeline is not None
        assert config.paths is not None

        # Vérifier que les valeurs par défaut sont cohérentes
        assert config.pipeline.default_llm_model
        assert config.paths.project_root.exists()

    def test_configuration_with_all_env_vars(self) -> None:
        """Test avec toutes les variables d'environnement."""
        with patch.dict(
            os.environ,
            {
                "PIAG_API_KEY": "piag-key",
                "OPENAI_API_KEY": "openai-key",
                "PIAG_API_URL": "https://custom.piag.example.com/v1/chat",
                "PIPELINE__DEFAULT_LLM_MODEL": "custom-model",
                "PIPELINE__MAX_RETRIES": "7",
                "PIPELINE__TIMEOUT": "300",
            },
            clear=False,
        ):
            config = AppConfig()
            assert config.llm.piag_api_key == "piag-key"
            assert config.llm.openai_api_key == "openai-key"
            assert "custom.piag.example.com" in str(config.llm.piag_api_url)
            assert config.pipeline.default_llm_model == "custom-model"
            assert config.pipeline.max_retries == 7
            assert config.pipeline.timeout == 300

    def test_partial_configuration(self) -> None:
        """Test avec seulement quelques variables d'environnement."""
        with patch.dict(
            os.environ,
            {
                "PIAG_API_KEY": "partial-key",
                "PIPELINE__MAX_RETRIES": "2",
            },
            clear=False,
        ):
            config = AppConfig()
            # Valeurs personnalisées
            assert config.llm.piag_api_key == "partial-key"
            assert config.pipeline.max_retries == 2
            # Valeurs par défaut
            assert config.llm.openai_api_key is None
            assert config.pipeline.timeout == 120
            assert config.pipeline.default_llm_model == "primary"
