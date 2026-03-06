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
Helpers pour la gestion centralisée des erreurs OCAPI.

Fournit des utilitaires pour convertir des exceptions tierces ou génériques
en exceptions OCAPI typées, et pour enrichir les messages d'erreur avec du
contexte supplémentaire.
"""
from contextlib import contextmanager
from typing import Iterator, Type, TypeVar

from ocapi.exceptions import OcapiError

_E = TypeVar("_E", bound=OcapiError)


@contextmanager
def wrap_errors(exc_class: Type[_E], message: str = "") -> Iterator[None]:
    """Context manager qui convertit toute exception non-OCAPI en `exc_class`.

    Les exceptions qui héritent déjà de OcapiError sont laissées se propager
    sans modification.

    Exemple::

        with wrap_errors(InputOutputError, "Impossible de lire le fichier"):
            content = path.read_text()
    """
    try:
        yield
    except OcapiError:
        raise
    except Exception as exc:
        raise exc_class(message or str(exc)) from exc


def format_error_context(exc: Exception, context: str) -> str:
    """Retourne un message d'erreur enrichi avec un contexte supplémentaire.

    Exemple::

        msg = format_error_context(e, f"lors du traitement de {filename}")
        _LOGGER.error(msg)
    """
    return f"{context}: {exc}"
