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
import pytest

from .exceptions import (
    GraphError,
    InputOutputError,
    InvalidArreteIdError,
    InvalidArticleIdError,
    InvalidFileFormatError,
    LLMConfigError,
    LLMError,
    LLMNetworkError,
    LLMResponseError,
    NodeNotFoundError,
    OcapiError,
    OperationError,
)


class TestOcapiErrorHierarchy:
    """Vérifie que la hiérarchie d'héritage est correcte."""

    def test_all_errors_inherit_from_ocapi_error(self) -> None:
        for cls in (
            InvalidArticleIdError,
            InvalidArreteIdError,
            InvalidFileFormatError,
            LLMError,
            LLMConfigError,
            LLMNetworkError,
            LLMResponseError,
            OperationError,
            GraphError,
            NodeNotFoundError,
            InputOutputError,
        ):
            assert issubclass(cls, OcapiError), f"{cls.__name__} should inherit OcapiError"

    def test_llm_subclasses_inherit_llm_error(self) -> None:
        for cls in (LLMConfigError, LLMNetworkError, LLMResponseError):
            assert issubclass(cls, LLMError), f"{cls.__name__} should inherit LLMError"

    def test_node_not_found_inherits_graph_error(self) -> None:
        assert issubclass(NodeNotFoundError, GraphError)

    def test_id_errors_also_inherit_value_error(self) -> None:
        """InvalidArticleIdError et InvalidArreteIdError héritent de ValueError
        pour rester compatibles avec les @field_validator Pydantic."""
        assert issubclass(InvalidArticleIdError, ValueError)
        assert issubclass(InvalidArreteIdError, ValueError)

    def test_other_errors_do_not_inherit_value_error(self) -> None:
        for cls in (
            InvalidFileFormatError,
            LLMError,
            LLMConfigError,
            LLMNetworkError,
            LLMResponseError,
            OperationError,
            GraphError,
            NodeNotFoundError,
            InputOutputError,
        ):
            assert not issubclass(cls, ValueError), f"{cls.__name__} should NOT inherit ValueError"

    def test_node_not_found_caught_as_graph_error(self) -> None:
        with pytest.raises(GraphError):
            raise NodeNotFoundError("section 1.2 not found")

    def test_id_errors_caught_as_value_error(self) -> None:
        with pytest.raises(ValueError):
            raise InvalidArticleIdError("bad article id")
        with pytest.raises(ValueError):
            raise InvalidArreteIdError("bad arrete id")


def test_error_message_preserved() -> None:
    msg = "invalid format for identifier"
    assert str(InvalidArreteIdError(msg)) == msg


def test_chained_exception() -> None:
    cause = ValueError("cause originale")
    exc = InvalidFileFormatError("wrapper")
    try:
        raise exc from cause
    except InvalidFileFormatError as caught:
        assert caught.__cause__ is cause
