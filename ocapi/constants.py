from pathlib import Path


# Project root = repository root (parent of the top-level package directory)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_PATH = PROJECT_ROOT / "data" / "0005804239" / "journaux" / "catalogue_ap.json"
FULL_SECTION = "contenu entier"  # placeholder pour indiquer au LLM d'insérer la section complète
DEFAULT_LLM_MODEL = "mte-api-piag-mistral-medium-latest"