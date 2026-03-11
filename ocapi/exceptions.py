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
Centralised exception hierarchy for OCAPI.

All domain exceptions inherit from OcapiError, allowing callers to either
discriminate precisely or use a single catch-all (except OcapiError).

Exceptions that also inherit from ValueError
────────────────────────────────────────────
InvalidArticleIdError and InvalidArreteIdError inherit from (OcapiError, ValueError)
to remain compatible with Pydantic v2 @field_validator, which only wraps
ValueError and AssertionError into ValidationError.
"""


class OcapiError(Exception):
    """Base class for all OCAPI exceptions."""


# ── Identifier validation ──────────────────────────────────────────────────────


class InvalidArticleIdError(OcapiError, ValueError):
    """Invalid article_id format.

    Inherits from ValueError to remain compatible with Pydantic @field_validator.
    """


class InvalidArreteIdError(OcapiError, ValueError):
    """Invalid arrete_id format (expected YYYY-MM-DD).

    Inherits from ValueError to remain compatible with Pydantic @field_validator.
    """


# ── File format ───────────────────────────────────────────────────────────────


class InvalidFileFormatError(OcapiError):
    """File format error: invalid name, missing HTML structure, or unsupported Arrêtify version."""


# ── LLM ───────────────────────────────────────────────────────────────────────


class LLMError(OcapiError):
    """Base class for all LLM-related errors."""


class LLMConfigError(LLMError):
    """Invalid LLM configuration (unknown provider, missing keys, etc.)."""


class LLMNetworkError(LLMError):
    """Network failure during an LLM call (timeout, HTTP 5xx, retries exhausted)."""


class LLMResponseError(LLMError):
    """Invalid or unparsable LLM response (unexpected JSON structure)."""


# ── Operations ────────────────────────────────────────────────────────────────


class OperationError(OcapiError):
    """Error during the construction or application of an operation."""


# ── Operations graph ──────────────────────────────────────────────────────────


class GraphError(OcapiError):
    """Error during the construction or resolution of the operations graph."""


class NodeNotFoundError(GraphError):
    """Section/article not found in the arrêté during graph construction."""


# ── Input / Output ────────────────────────────────────────────────────────────


class InputOutputError(OcapiError):
    """Input/output error (non-existent directory, write failure, etc.)."""
