import unittest

from .types import _BaseModelWithConfig


class TestBaseModelWithConfig(unittest.TestCase):

    def test_serialize_model_excludes_none(self):
        class TestModel(_BaseModelWithConfig):
            a: int
            b: str | None = None
            c: float | None = None

        model = TestModel(a=10, b=None, c=3.14)
        serialized = model.serialize_model()
        self.assertEqual(serialized, {"a": 10, "c": 3.14})