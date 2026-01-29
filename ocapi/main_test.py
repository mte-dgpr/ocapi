import pytest
from pathlib import Path
from ocapi.main import arrete_to_ArreteFile
from ocapi.types import ArreteFile


class TestArreteToArreteFile:
    def test_valid_filename(self, tmp_path: Path):
        test_file = tmp_path / "2023-01-15_APC_source.html"
        test_file.write_text("<html><body>Test</body></html>", encoding="utf-8")

        arrete_file = arrete_to_ArreteFile(0, test_file)

        assert isinstance(arrete_file, ArreteFile)
        assert arrete_file.id == "2023-01-15"
        assert arrete_file.filename == "2023-01-15_APC_source"

    def test_invalid_filename(self, tmp_path: Path):
        test_file = tmp_path / "invalidfilename.html"
        test_file.write_text("<html></html>", encoding="utf-8")

        with pytest.raises(ValueError):
            arrete_to_ArreteFile(0, test_file)