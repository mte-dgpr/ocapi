#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
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
from ocapi.config import settings
from ocapi.exceptions import OcapiError
from ocapi.llm_utils import config_model_llm
from ocapi.step_rendering.header import make_permit_header
from ocapi.step_rendering.main_content import make_permit_content
from ocapi.step_rendering.other import make_permit_other
from ocapi.types import ArreteFile, ArticleHistory, FileType, Operation, Permis
from ocapi.utils.logging_utils import get_logger

_LOGGER = get_logger(__name__)


def _select_principal_ap(arrete_files: list[ArreteFile]) -> ArreteFile:
    """Pick the arrêté to use as the consolidation base.

    Honours a user-provided ``principal`` flag when set (exactly one arrêté
    must be marked). Otherwise infers it (latest non-abrogated AP_AUTORISATION,
    falling back to the first non-abrogated arrêté) and marks the chosen
    arrêté ``principal=True`` so downstream consumers can rely on the flag.
    """
    principals = [af for af in arrete_files if af.principal]
    if len(principals) > 1:
        ids = ", ".join(af.id for af in principals)
        raise OcapiError(f"Multiple arrêtés flagged as principal: {ids}")
    if len(principals) == 1:
        return principals[0]

    active = [af for af in arrete_files if af.status]
    ap_autorisations = [af for af in active if af.file_type == FileType.AP_AUTORISATION]
    if ap_autorisations:
        chosen = ap_autorisations[-1]
    elif active:
        chosen = active[0]
    else:
        chosen = arrete_files[0]
    chosen.principal = True
    return chosen


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
    ap_principal = _select_principal_ap(arrete_files)
    contenu_permis = make_permit_content(history, arrete_files, operations, ap_principal.id)
    header_permis = make_permit_header(arrete_files)
    other_permis = make_permit_other(arrete_files, operations=operations, history=history)
    _LOGGER.debug("Rendering: permit generated successfully")
    return Permis(header=header_permis, contenu=contenu_permis, other=other_permis)


def permis_to_html(permis: Permis) -> str:
    """Render *permis* using the consolidated permit HTML template."""
    template_path = settings.paths.permis_template_path
    template = template_path.read_text(encoding="utf-8")
    required_tokens = ("{{HEADER}}", "{{CONTENT}}", "{{OTHER}}", "{{GENERATED_BY}}")
    if not all(token in template for token in required_tokens):
        raise ValueError(
            "Invalid consolidated permit HTML template: "
            "placeholders {{HEADER}}, {{CONTENT}}, {{OTHER}} "
            "and {{GENERATED_BY}} are required."
        )
    model_name = config_model_llm().model_name
    return (
        template.replace("{{HEADER}}", permis.header)
        .replace("{{CONTENT}}", permis.contenu)
        .replace("{{OTHER}}", permis.other)
        .replace("{{GENERATED_BY}}", model_name)
    )
