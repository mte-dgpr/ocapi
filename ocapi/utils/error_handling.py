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
"""
Helpers for centralised OCAPI error handling.

Provides utilities to convert third-party or generic exceptions into typed
OCAPI exceptions, and to enrich error messages with additional context.
"""
from contextlib import contextmanager
from typing import Iterator, Type, TypeVar

from ocapi.exceptions import OcapiError

_E = TypeVar("_E", bound=OcapiError)


@contextmanager
def wrap_errors(exc_class: Type[_E], message: str = "") -> Iterator[None]:
    """Context manager that converts any non-OCAPI exception into ``exc_class``.

    Exceptions that already inherit from OcapiError are re-raised unchanged.

    Example::

        with wrap_errors(InputOutputError, "Cannot read file"):
            content = path.read_text()
    """
    try:
        yield
    except OcapiError:
        raise
    except Exception as exc:
        raise exc_class(message or str(exc)) from exc


def format_error_context(exc: Exception, context: str) -> str:
    """Return an error message enriched with additional context.

    Example::

        msg = format_error_context(e, f"while processing {filename}")
        _LOGGER.error(msg)
    """
    return f"{context}: {exc}"
