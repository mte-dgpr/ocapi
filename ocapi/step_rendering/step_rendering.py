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
from ocapi.step_rendering.make_header import make_permit_header
from ocapi.step_rendering.make_main_content import make_permit_content
from ocapi.step_rendering.make_other import make_permit_other
from ocapi.types import ArreteFile, ArticleHistory, Operation, Permis
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def step_rendering(
    history: ArticleHistory, operations: list[Operation], arrete_files: list[ArreteFile]
) -> Permis:
    """Assemble le permis consolidé HTML à partir de l'historique et des arrêtés.

    Génère le header (title, sources, visa, motif), le contenu principal
    (articles avec leur dernière version) et les compléments (arrêtés non
    modificatifs).

    Parameters
    ----------
    history : ArticleHistory
        Historique des versions par article produit par `step_resolution`.
    operations : list[Operation]
        Opérations détectées, utilisées pour annoter les versions d'articles.
    arrete_files : list[ArreteFile]
        Arrêtés sources triés chronologiquement ; `arrete_files[0]` est l'AP initial.

    Returns
    -------
    Permis
        Objet contenant le HTML du header, du contenu principal et des compléments.
    """
    _LOGGER.info(f"Rendering: génération du permis à partir de {len(history)} article(s) modifiés")
    contenu_permis = make_permit_content(history, arrete_files, operations)
    header_permis = make_permit_header(arrete_files)
    other_permis = make_permit_other(arrete_files, operations=operations)
    _LOGGER.debug("Rendering: permis généré avec succès")
    return Permis(header=header_permis, contenu=contenu_permis, other=other_permis)
