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
