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
<<<<<<< HEAD
import tempfile
import unittest
from pathlib import Path

=======
from pathlib import Path

import pytest

>>>>>>> 048dc4d46b16e03bccdd4deb353d67746262c02f
from ocapi.main import arrete_to_ArreteFile
from ocapi.types import ArreteFile


<<<<<<< HEAD
class TestArreteToArreteFile(unittest.TestCase):
    def test_valid_filename(self) -> None:
        # Créer un fichier temporaire avec le bon format
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, prefix="2023-01-15_APC_source"
        ) as f:
            f.write("<html><body>Test content</body></html>")
            temp_path = Path(f.name)

        try:
            arrete_file = arrete_to_ArreteFile(0, temp_path)
            assert isinstance(arrete_file, ArreteFile)
            assert arrete_file.id == "2023-01-15"
            assert "2023-01-15_APC_source" in arrete_file.filename
        finally:
            temp_path.unlink()

    def test_invalid_filename(self) -> None:
        # Créer un fichier temporaire avec un nom au mauvais format (sans underscore)
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "invalidfilename.html"
            temp_path.write_text("<html><body>Test content</body></html>", encoding="utf-8")

            with self.assertRaises(ValueError):
                arrete_to_ArreteFile(0, temp_path)
=======
class TestArreteToArreteFile:
    def test_valid_filename(self, tmp_path: Path) -> None:
        test_file = tmp_path / "2023-01-15_APC_source.html"
        test_file.write_text("<html><body>Test</body></html>", encoding="utf-8")

        arrete_file = arrete_to_ArreteFile(0, test_file)

        assert isinstance(arrete_file, ArreteFile)
        assert arrete_file.id == "2023-01-15"
        assert arrete_file.filename == "2023-01-15_APC_source"

    def test_invalid_filename(self, tmp_path: Path) -> None:
        test_file = tmp_path / "invalidfilename.html"
        test_file.write_text("<html></html>", encoding="utf-8")

        with pytest.raises(ValueError):
            arrete_to_ArreteFile(0, test_file)
>>>>>>> 048dc4d46b16e03bccdd4deb353d67746262c02f
