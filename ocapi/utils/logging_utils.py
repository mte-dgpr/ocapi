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
Utilitaires pour la gestion centralisée du logging.

Ce module fournit une fonction `initialize_root_logger` qui configure
le logger racine de l'application avec :
- Format détaillé avec timestamp et nom du module
- Handlers pour console et fichier
- Rotation des fichiers de log par taille et par jour
- Niveaux de logging configurables
"""

import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Format détaillé pour les logs
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def initialize_root_logger(
    level: LogLevel = "INFO",
    log_file: Path | None = None,
    max_bytes: int = 1024 * 1024,  # 1024 KB par défaut
    backup_count: int = 5,
    use_timed_rotation: bool = True,
    console_output: bool = True,
) -> logging.Logger:
    """
    Initialise et configure le logger racine de l'application.

    Cette fonction doit être appelée une seule fois au démarrage de l'application
    (typiquement dans le main ou le CLI).

    Args:
        level: Niveau de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Chemin du fichier de log. Si None, pas de fichier de log.
        max_bytes: Taille maximale d'un fichier de log avant rotation (en octets)
        backup_count: Nombre de fichiers de backup à conserver
        use_timed_rotation: Si True, rotation quotidienne en plus de la rotation par taille
        console_output: Si True, affiche les logs dans la console

    Returns:
        Le logger racine configuré

    Example:
        >>> from ocapi.utils.logging_utils import initialize_root_logger
        >>> from pathlib import Path
        >>> logger = initialize_root_logger(
        ...     level="INFO",
        ...     log_file=Path("logs/ocapi.log"),
        ...     console_output=True
        ... )
        >>> logger.info("Application démarrée")
    """
    # Obtenir le logger racine
    root_logger = logging.getLogger()

    # Définir le niveau
    log_level = getattr(logging, level.upper())
    root_logger.setLevel(log_level)

    # Supprimer les handlers existants pour éviter les doublons
    root_logger.handlers.clear()

    # Formatteur commun
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Handler console
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Handler fichier avec rotation
    if log_file:
        # Créer le répertoire parent si nécessaire
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if use_timed_rotation:
            # Rotation quotidienne + par taille
            file_handler = TimedRotatingFileHandler(
                filename=str(log_file),
                when="midnight",
                interval=1,
                backupCount=backup_count,
                encoding="utf-8",
            )
            # Ajouter aussi la rotation par taille
            # Note: TimedRotatingFileHandler ne supporte pas maxBytes directement
            # On utilise un RotatingFileHandler en plus
            size_handler = RotatingFileHandler(
                filename=str(log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            size_handler.setLevel(log_level)
            size_handler.setFormatter(formatter)
            root_logger.addHandler(size_handler)
        else:
            # Rotation par taille uniquement
            file_handler = RotatingFileHandler(
                filename=str(log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )

        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Obtient un logger pour un module spécifique.

    Cette fonction doit être utilisée dans chaque module pour obtenir
    un logger avec le nom du module.

    Args:
        name: Nom du module (typiquement __name__)

    Returns:
        Logger configuré pour ce module

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Message de log")
    """
    return logging.getLogger(name)


def set_level(level: LogLevel) -> None:
    """
    Change le niveau de logging global.

    Args:
        level: Nouveau niveau de logging

    Example:
        >>> set_level("DEBUG")
    """
    log_level = getattr(logging, level.upper())
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers:
        handler.setLevel(log_level)


__all__ = [
    "initialize_root_logger",
    "get_logger",
    "set_level",
    "LogLevel",
]
