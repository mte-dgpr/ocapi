import unittest
from pathlib import Path
from ocapi.main import arrete_to_ArreteFile
from ocapi.types import ArreteFile


class TestArreteToArreteFile(unittest.TestCase):
    def test_valid_filename(self):
        test_path = Path("2023-01-15_APC_source.html")
        arrete_file = arrete_to_ArreteFile(test_path)
        
        assert isinstance(arrete_file, ArreteFile)
        assert arrete_file.id == "2023-01-15"
        assert arrete_file.filename == "2023-01-15_APC_source"


    def test_invalid_filename(self):
        test_path = Path("invalid_filename.html")
        with self.assertRaises(ValueError):
            arrete_to_ArreteFile(test_path)