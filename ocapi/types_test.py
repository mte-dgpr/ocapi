import unittest

from .types import _BaseModelWithConfig


class TestBaseModelWithConfig(unittest.TestCase):

    def test_serialize_model_excludes_none(self):
        class TestModel(_BaseModelWithConfig):
            a: int
            b: str | None = None
            c: float | None = None

        model = TestModel(a=10, b=None, c=3.14)
        serialized = model.model_dump()
        assert "b" not in serialized

