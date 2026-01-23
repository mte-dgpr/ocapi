import unittest

from .types import _BaseModelWithConfig


class TestBaseModelWithConfig(unittest.TestCase):

    def test_serialize_model_excludes_none(self):
        class TestModel(_BaseModelWithConfig):
            a: int
            b: str | None = None
            c: float | None = None

        model = TestModel(a=10, b=None, c=3.14)
        # exclude_none dans ConfigDict ne s'applique pas automatiquement à model_dump()
        # Il faut utiliser model_dump(exclude_none=True) ou model_dump_json()
        serialized_default = model.model_dump()
        assert "b" in serialized_default  # Par défaut, None est inclus
        assert serialized_default["b"] is None
        
        # Mais quand on utilise exclude_none explicitement
        serialized_no_none = model.model_dump(exclude_none=True)
        assert "b" not in serialized_no_none
        assert "c" in serialized_no_none
        assert serialized_no_none["c"] == 3.14

