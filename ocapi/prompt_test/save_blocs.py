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
from pathlib import Path

from ocapi.constants import PROJECT_ROOT
from ocapi.main import arrete_to_ArreteFile
from ocapi.step_chunking.step_chunking import step_chunking
from ocapi.types import ArreteFile


def save_blocs(arrete_file: ArreteFile):
    """
    Sauvegarde les blocs extraits d'un arreté dans des fichiers HTML individuels.
    Utile pour le debugging.
    """
    docs, img_map = step_chunking(arrete_file)
    for i, doc in enumerate(docs):
        bloc_path = (
            Path(__file__).parent / "blocs_test" / f"blocs_{arrete_file.id}_bloc_{i+1:03d}.html"
        )
        with bloc_path.open("w", encoding="utf-8") as f:
            f.write(doc.page_content)
    return img_map


if __name__ == "__main__":
    input_dir = Path(__file__).resolve().parents[2] / "data" / "0005804239" / "arretes_html"
    html_files = sorted(input_dir.glob("*.html"))
    for i, html_file in enumerate(html_files):
        if i == 0:
            continue  # Skip first file (AP initial)
        test_arrete = arrete_to_ArreteFile(html_file)
        save_blocs(test_arrete)
        print(f"Blocs sauvegardés pour l'arrêté {test_arrete.id}")
