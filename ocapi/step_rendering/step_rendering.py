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
from ocapi.step_rendering.header import make_permit_header
from ocapi.step_rendering.main_content import make_permit_content
from ocapi.step_rendering.other import make_permit_other
from ocapi.types import ArreteFile, ArticleHistory, Operation, Permis
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def step_rendering(
    history: ArticleHistory, operations: list[Operation], arrete_files: list[ArreteFile]
) -> Permis:
    """Assemble the consolidated HTML permit from the history and arrêtés.

    Generates the header (title, sources, visa, motif), the main content
    (articles with their latest version) and the complements (non-modifying
    arrêtés).

    Parameters
    ----------
    history : ArticleHistory
        Article version history produced by ``step_resolution``.
    operations : list[Operation]
        Detected operations, used to annotate article versions.
    arrete_files : list[ArreteFile]
        Source arrêtés sorted chronologically; ``arrete_files[0]`` is the initial AP.

    Returns
    -------
    Permis
        Object containing the HTML of the header, main content and complements.
    """
    _LOGGER.info(f"Rendering: generating permit from {len(history)} modified article(s)")
    contenu_permis = make_permit_content(history, arrete_files, operations)
    header_permis = make_permit_header(arrete_files)
    other_permis = make_permit_other(arrete_files, operations=operations, history=history)
    _LOGGER.debug("Rendering: permit generated successfully")
    return Permis(header=header_permis, contenu=contenu_permis, other=other_permis)
