import sys
from pathlib import Path

from flake8.main.cli import main as flake8_main


def main() -> None:
    """Wrapper pour accepter 'flake check .' et appliquer les options par défaut."""
    argv = sys.argv[1:]
    if argv and argv[0] == "check":
        argv = argv[1:]
    if not argv:
        argv = ["."]

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    default_args = [
        "--exclude",
        (
            ".git,__pycache__,venv,.venv,build,dist,data,"
            "*_test.py,ocapi/step_detection/*,ocapi/step_rendering/exemple_input_main.py"
        ),
        "--max-line-length",
        "130",
        "--extend-ignore",
        "E203,E701",
        "--extend-select",
        "I,B",
        "--per-file-ignores",
        "__init__.py:F401",
    ]

    # flake8_main appelle sys.exit en interne; on relaie le code retour.
    sys.exit(flake8_main(default_args + argv))
