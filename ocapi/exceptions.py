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
Hiérarchie centralisée des exceptions OCAPI.

Toutes les exceptions métier héritent de OcapiError, ce qui permet aux
appelants de discriminer précisément les erreurs ou d'utiliser un catch-all
unique (except OcapiError).

Exceptions qui héritent aussi de ValueError
────────────────────────────────────────────
InvalidArticleIdError et InvalidArreteIdError héritent de (OcapiError, ValueError)
afin de rester compatibles avec les @field_validator de Pydantic v2, qui n'encapsule
dans ValidationError que les ValueError et AssertionError.
"""


class OcapiError(Exception):
    """Classe de base pour toutes les exceptions OCAPI."""


# ── Validation des identifiants ──────────────────────────────────────────────


class InvalidArticleIdError(OcapiError, ValueError):
    """Format d'article_id invalide.

    Hérite de ValueError pour rester compatible avec les @field_validator Pydantic.
    """


class InvalidArreteIdError(OcapiError, ValueError):
    """Format d'arrete_id invalide (attendu YYYY-MM-DD).

    Hérite de ValueError pour rester compatible avec les @field_validator Pydantic.
    """


# ── Format de fichier ─────────────────────────────────────────────────────────


class InvalidFileFormatError(OcapiError):
    """Erreur de format de fichier : nom invalide, structure HTML manquante
    ou version Arrêtify non supportée."""


# ── LLM ───────────────────────────────────────────────────────────────────────


class LLMError(OcapiError):
    """Classe de base pour toutes les erreurs liées au LLM."""


class LLMConfigError(LLMError):
    """Configuration LLM invalide (provider inconnu, clés manquantes, etc.)."""


class LLMNetworkError(LLMError):
    """Échec réseau lors d'un appel LLM (timeout, HTTP 5xx, retries épuisés)."""


class LLMResponseError(LLMError):
    """Réponse LLM invalide ou non parsable (structure JSON inattendue)."""


# ── Opérations ────────────────────────────────────────────────────────────────


class OperationError(OcapiError):
    """Erreur lors de la construction ou de l'application d'une opération."""


# ── Graphe d'opérations ───────────────────────────────────────────────────────


class GraphError(OcapiError):
    """Erreur lors de la construction ou de la résolution du graphe d'opérations."""


class NodeNotFoundError(GraphError):
    """Section/article introuvable dans l'arrêté lors de la construction du graphe."""


# ── Entrées / Sorties ─────────────────────────────────────────────────────────


class InputOutputError(OcapiError):
    """Erreur d'entrée/sortie (répertoire inexistant, écriture impossible, etc.)."""
