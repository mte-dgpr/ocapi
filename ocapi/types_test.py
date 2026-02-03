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
import unittest

from .types import _BaseModelWithConfig


class TestBaseModelWithConfig(unittest.TestCase):

    def test_serialize_model_excludes_none(self) -> None:
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
