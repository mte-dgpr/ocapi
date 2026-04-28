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
"""Tests for the configuration module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ocapi.config import AppConfig, LLMConfig, PathsConfig, reload_settings, settings


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_values(self) -> None:
        """Test default values."""
        config = LLMConfig()
        assert config.piag_api_key is None
        assert "preprod.api.piag.e2.rie.gouv.fr" in str(config.piag_api_url)
        assert config.openai_api_key is None
        assert "api.openai.com" in str(config.openai_api_url)

    def test_valid_api_key(self) -> None:
        """Test with a valid API key."""
        config = LLMConfig(piag_api_key="sk-test-key-123")
        assert config.piag_api_key == "sk-test-key-123"

    def test_empty_api_key_raises_error(self) -> None:
        """Test that an empty API key raises an error."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(piag_api_key="")
        assert "API key cannot be empty" in str(exc_info.value)

    def test_whitespace_api_key_raises_error(self) -> None:
        """Test that a whitespace-only API key raises an error."""
        with pytest.raises(ValidationError) as exc_info:
            LLMConfig(piag_api_key="   ")
        assert "API key cannot be empty" in str(exc_info.value)

    def test_valid_custom_urls(self) -> None:
        """Test with custom URLs."""
        config = LLMConfig(
            piag_api_url="https://custom.api.example.com/v1/chat",
            openai_api_url="https://custom.openai.example.com/v1/chat",
        )
        assert "custom.api.example.com" in str(config.piag_api_url)
        assert "custom.openai.example.com" in str(config.openai_api_url)

    def test_invalid_url_raises_error(self) -> None:
        """Test that an invalid URL raises an error."""
        with pytest.raises(ValidationError):
            LLMConfig(piag_api_url="not-a-valid-url")

    def test_http_url_accepted(self) -> None:
        """Test that an HTTP URL is accepted."""
        config = LLMConfig(piag_api_url="http://localhost:8000/v1/chat")
        assert "localhost" in str(config.piag_api_url)


class TestPathsConfig:
    """Tests for PathsConfig."""

    def test_default_values(self) -> None:
        """Test default values."""
        config = PathsConfig()
        assert config.project_root.exists()
        assert config.project_root.is_dir()
        assert config.catalogue_path.is_absolute()

    def test_invalid_project_root_raises_error(self) -> None:
        """Test that an invalid project root raises an error."""
        invalid_path = Path("/nonexistent/path/to/project")
        with pytest.raises(ValidationError) as exc_info:
            PathsConfig(project_root=invalid_path)
        assert "does not exist" in str(exc_info.value)

    def test_project_root_must_be_directory(self) -> None:
        """Test that the project root must be a directory."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with pytest.raises(ValidationError) as exc_info:
                PathsConfig(project_root=tmp_path)
            assert "must be a directory" in str(exc_info.value)
        finally:
            try:
                tmp_path.unlink()
            except PermissionError:
                pass

    def test_custom_paths(self) -> None:
        """Test with custom paths."""
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
    """Tests for AppConfig."""

    def test_default_values(self) -> None:
        """Test default values."""
        config = AppConfig()
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.paths, PathsConfig)

    def test_nested_configuration(self) -> None:
        """Test nested configuration."""
        config = AppConfig(_env_file=None)
        assert config.llm.piag_api_key is None
        assert config.paths.project_root.exists()

    def test_model_dump_safe_masks_secrets(self) -> None:
        """Test that model_dump_safe masks secrets."""
        config = AppConfig()
        config.llm.piag_api_key = "sk-secret-key"
        config.llm.openai_api_key = "sk-openai-secret"

        safe_dump = config.model_dump_safe()
        assert safe_dump["llm"]["piag_api_key"] == "***MASKED***"
        assert safe_dump["llm"]["openai_api_key"] == "***MASKED***"

    def test_model_dump_safe_preserves_none(self) -> None:
        """Test that model_dump_safe preserves None values."""
        config = AppConfig(_env_file=None)
        safe_dump = config.model_dump_safe()
        assert safe_dump["llm"]["piag_api_key"] is None
        assert safe_dump["llm"]["openai_api_key"] is None

    def test_env_file_loading(self) -> None:
        """Test loading from a .env file."""
        with patch.dict(
            os.environ,
            {"LLM__PIAG_API_KEY": "test-key-from-env"},
            clear=False,
        ):
            config = AppConfig(_env_file=None)
            assert config.llm.piag_api_key == "test-key-from-env"

    def test_extra_env_vars_ignored(self) -> None:
        """Test that unknown environment variables are ignored."""
        with patch.dict(
            os.environ,
            {"UNKNOWN_CONFIG_VAR": "should-be-ignored"},
            clear=False,
        ):
            config = AppConfig()
            assert config is not None


class TestSettingsSingleton:
    """Tests for the settings singleton instance."""

    def test_settings_is_app_config(self) -> None:
        """Test that settings is an AppConfig instance."""
        assert isinstance(settings, AppConfig)

    def test_settings_accessible(self) -> None:
        """Test that settings is accessible."""
        assert settings.llm is not None
        assert settings.paths is not None

    def test_settings_llm_config(self) -> None:
        """Test the LLM configuration."""
        assert hasattr(settings.llm, "piag_api_key")
        assert hasattr(settings.llm, "piag_api_url")
        assert hasattr(settings.llm, "openai_api_key")
        assert hasattr(settings.llm, "openai_api_url")

    def test_settings_paths_config(self) -> None:
        """Test the Paths configuration."""
        assert hasattr(settings.paths, "project_root")
        assert hasattr(settings.paths, "catalogue_path")
        assert settings.paths.project_root.exists()


class TestReloadSettings:
    """Tests for the reload_settings function."""

    def test_reload_settings_returns_new_instance(self) -> None:
        """Test that reload_settings returns a new instance."""
        new_settings = reload_settings()
        assert isinstance(new_settings, AppConfig)
        assert new_settings is not settings

    def test_reload_settings_with_env_changes(self) -> None:
        """Test that reload_settings picks up environment changes."""
        with patch.dict(
            os.environ,
            {"LLM__PIAG_API_KEY": "new-test-key"},
            clear=False,
        ):
            new_settings = AppConfig(_env_file=None)
            assert new_settings.llm.piag_api_key == "new-test-key"


class TestIntegration:
    """Integration tests."""

    def test_complete_configuration_flow(self) -> None:
        """Test the complete configuration flow."""
        config = AppConfig()

        assert config.llm is not None
        assert config.paths is not None

        assert config.paths.project_root.exists()

    def test_configuration_with_all_env_vars(self) -> None:
        """Test with all environment variables set."""
        with patch.dict(
            os.environ,
            {
                "PIAG_API_KEY": "piag-key",
                "OPENAI_API_KEY": "openai-key",
                "PIAG_API_URL": "https://custom.piag.example.com/v1/chat",
            },
            clear=False,
        ):
            config = AppConfig(_env_file=None)
            assert config.llm.piag_api_key == "piag-key"
            assert config.llm.openai_api_key == "openai-key"
            assert "custom.piag.example.com" in str(config.llm.piag_api_url)

    def test_partial_configuration(self) -> None:
        """Test with only some environment variables set."""
        with patch.dict(
            os.environ,
            {"PIAG_API_KEY": "partial-key"},
            clear=False,
        ):
            config = AppConfig(_env_file=None)
            assert config.llm.piag_api_key == "partial-key"
            assert config.llm.openai_api_key is None
