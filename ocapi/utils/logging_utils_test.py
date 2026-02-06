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
Tests pour le module de logging centralisé.
"""

import logging
import re
import tempfile
from pathlib import Path

import pytest

from ocapi.utils.logging_utils import get_logger, initialize_root_logger, set_level


class TestGetLogger:
    """Tests pour la fonction get_logger."""

    def test_get_logger(self) -> None:
        """Test que get_logger retourne un logger avec le bon nom."""
        logger = get_logger("test_module")
        assert logger.name == "test_module"
        assert isinstance(logger, logging.Logger)

    def test_multiple_loggers(self) -> None:
        """Test que plusieurs loggers peuvent être utilisés simultanément."""
        initialize_root_logger(level="INFO")

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name == "module1"
        assert logger2.name == "module2"
        assert logger1 is not logger2


class TestInitializeRootLogger:
    """Tests pour la fonction initialize_root_logger."""

    def test_initialize_root_logger_console_only(self) -> None:
        """Test l'initialisation du logger avec console uniquement."""
        logger = initialize_root_logger(
            level="INFO",
            log_file=None,
            console_output=True,
        )

        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1

        # Vérifier qu'il y a au moins un StreamHandler
        has_console_handler = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
        assert has_console_handler

    def test_initialize_root_logger_with_file(self, tmp_path: Path) -> None:
        """Test l'initialisation du logger avec fichier."""
        log_file = tmp_path / "test.log"

        logger = initialize_root_logger(
            level="DEBUG",
            log_file=log_file,
            console_output=False,
        )

        assert logger.level == logging.DEBUG

        # Écrire un message de test
        test_logger = get_logger("test")
        test_logger.info("Test message")

        # Forcer le flush des handlers
        for handler in logger.handlers:
            handler.flush()

        # Vérifier que le fichier existe
        assert log_file.exists()

    def test_logger_rotation_config(self, tmp_path: Path) -> None:
        """Test la configuration de rotation des fichiers de log."""
        log_file = tmp_path / "rotating.log"

        logger = initialize_root_logger(
            level="INFO",
            log_file=log_file,
            max_bytes=1024,
            backup_count=3,
            use_timed_rotation=False,
            console_output=False,
        )

        # Vérifier qu'il y a un RotatingFileHandler
        has_rotating_handler = any(
            h.__class__.__name__ == "RotatingFileHandler" for h in logger.handlers
        )
        assert has_rotating_handler

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_all_log_levels(self, level: str) -> None:
        """Test que tous les niveaux de logging sont acceptés."""
        logger = initialize_root_logger(level=level)  # type: ignore[arg-type]
        expected_level = getattr(logging, level)
        assert logger.level == expected_level


class TestSetLevel:
    """Tests pour la fonction set_level."""

    def test_set_level(self) -> None:
        """Test le changement de niveau de logging."""
        initialize_root_logger(level="INFO")
        root_logger = logging.getLogger()

        assert root_logger.level == logging.INFO

        set_level("DEBUG")
        assert root_logger.level == logging.DEBUG

        set_level("ERROR")
        assert root_logger.level == logging.ERROR


class TestLoggerFunctionality:
    """Tests pour la fonctionnalité du système de logging."""

    def test_logger_levels_in_code(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test que les différents niveaux de logging fonctionnent correctement."""
        logger = get_logger("test_levels")

        with caplog.at_level(logging.DEBUG):
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")

        # Vérifier que tous les messages sont présents
        assert "Debug message" in caplog.text
        assert "Info message" in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text
        assert "Critical message" in caplog.text

    def test_logger_with_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test que l'exception logging fonctionne correctement."""
        logger = get_logger("test_exception")

        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Test error")
            except ValueError:
                logger.exception("An error occurred")

        # Vérifier que le message et la stacktrace sont présents
        assert "An error occurred" in caplog.text
        assert "ValueError" in caplog.text
        assert "Test error" in caplog.text

    def test_log_format(self) -> None:
        """Test que le format des logs contient les informations attendues."""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            log_file = Path(f.name)

        try:
            initialize_root_logger(
                level="INFO",
                log_file=log_file,
                console_output=False,
            )

            logger = get_logger("test.module")
            logger.info("Test format message")

            # Fermer tous les handlers pour libérer le fichier
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                handler.close()
                root_logger.removeHandler(handler)

            # Lire le contenu du fichier
            content = log_file.read_text()

            # Vérifier le format: timestamp - module - level - message
            assert "test.module" in content
            assert "INFO" in content
            assert "Test format message" in content
            # Vérifier qu'il y a un timestamp (format: YYYY-MM-DD HH:MM:SS)
            assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content)

        finally:
            # Supprimer le fichier seulement s'il existe toujours
            if log_file.exists():
                log_file.unlink()
