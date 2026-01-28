"""
Constantes partagées pour OCAPI.

Ce module sert de couche de compatibilité. Les valeurs configurables
proviennent désormais de ocapi.config.settings.
"""

from pathlib import Path

from ocapi.config import settings

# Project root = repository root (parent of the top-level package directory)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_PATH = PROJECT_ROOT / "data" / "0005804239" / "journaux" / "catalogue_ap.json"
FULL_SECTION = "contenu entier"  # placeholder pour indiquer au LLM d'insérer la section complète

# Valeur issue de la configuration centralisée
DEFAULT_LLM_MODEL = settings.pipeline.default_llm_model
