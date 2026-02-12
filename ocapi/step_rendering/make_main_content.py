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

# TODO nowwwwwwww

from bs4 import BeautifulSoup, Tag

from ocapi.types import ArreteFile, ArticleHistory, ArticleVersion, NodeId, Operation, OperationType


def make_contenu_permis(
    history: ArticleHistory, arrete_files: list[ArreteFile], operations: list[Operation]
) -> str:
    """
    Génère le contenu consolidé du permis à partir de l'historique des modifications.

    1. Part de l'AP initial (arrete_files[0])
    2. Pour chaque article de l'AP initial, applique la dernière version depuis l'historique
    3. Retourne le HTML consolidé (sans header)
    """
    # Récupérer l'AP initial
    ap_initial = arrete_files[0]
    ap_initial_id = ap_initial.id

    # Cloner le soup pour ne pas modifier l'original
    consolidated_soup = BeautifulSoup(str(ap_initial.soup), "html.parser")

    # Extraire seulement le body (skip header)
    main = consolidated_soup.find("main")
    if main is None:
        return ""

    # Trouver toutes les sections (articles) dans le body
    sections = main.find_all("section", attrs={"data-spec": "section"})
    operation_by_id = {operation.id: operation for operation in operations}

    for section in sections:
        article_id = section.get("data-number")
        if not article_id or not isinstance(article_id, str):
            continue

        section.replace_with(
            make_section_version(
                original_section=section,
                article_id=article_id,
                history=history,
                ap_initial_id=ap_initial_id,
                operation_by_id=operation_by_id,
            )
        )

    return str(main)


def make_section_version(
    original_section: Tag,
    article_id: str,
    history: ArticleHistory,
    ap_initial_id: str,
    operation_by_id: dict[str, Operation],
) -> Tag:
    """
    Construit une SectionVersion contenant le contenu consolidé d'un article.
    Ajoute les attributs:
    - data-is_modified
    - data-date_version
    """
    key = NodeId(arrete_id=ap_initial_id, article_id=article_id)
    section_version_soup = BeautifulSoup(str(original_section), "html.parser")
    section_version = section_version_soup.find("section")
    if section_version is None:
        return original_section

    section_version["data-spec"] = "section_version"

    if key not in history:
        section_version["data-is_modified"] = "false"
        section_version["data-date_version"] = ap_initial_id
        return section_version

    versions = history[key]
    history_html = _build_section_history_html(versions=versions, operation_by_id=operation_by_id)
    latest_version = versions[-1]
    latest_operation_id = latest_version.get("operation_id")
    latest_operation = (
        operation_by_id.get(str(latest_operation_id)) if latest_operation_id else None
    )
    latest_date_version = (
        latest_operation.source_id.arrete_id if latest_operation else ap_initial_id
    )

    section_version["data-is_modified"] = "true"
    section_version["data-date_version"] = latest_date_version
    section_version.clear()

    if _is_abrogated(latest_version=latest_version, operation_by_id=operation_by_id):
        consolidated_content = f"{history_html}<p><em>Article abrogé</em></p>"
    else:
        latest_content = latest_version.get("content", "")
        consolidated_content = (
            f"{history_html}{latest_content if isinstance(latest_content, str) else ''}"
        )

    consolidated_soup = BeautifulSoup(consolidated_content, "html.parser")
    for child in list(consolidated_soup.contents):
        section_version.append(child)
    return section_version


def _build_section_history_html(
    versions: list[ArticleVersion],
    operation_by_id: dict[str, Operation],
) -> str:
    history_parts = [
        '<div data-spec="section_version_history" style="color: red; margin-bottom: 1rem;">'
    ]
    for index, version in enumerate(versions):
        operation_id = version.get("operation_id")
        operation = operation_by_id.get(str(operation_id)) if operation_id else None
        if index == 0:
            if operation:
                history_parts.append(
                    (
                        "<p><strong>Article créé par l'arrêté "
                        f"{operation.source_id.arrete_id}</strong></p>"
                    )
                )
            else:
                history_parts.append("<p><strong>Article créé par l'arrêté initial</strong></p>")
            continue

        if not operation:
            continue
        operation_label = (
            "modifié"
            if operation.operation_type == OperationType.REPLACE
            else "abrogé" if operation.operation_type == OperationType.REMOVE else "créé"
        )
        history_parts.append(
            f"<p><strong>Article {operation_label} par l'article "
            f"{operation.source_id.article_id} de l'arrêté "
            f"{operation.source_id.arrete_id}</strong></p>"
        )
        previous_version = versions[index - 1]
        previous_content = previous_version.get("content", "")
        history_parts.append(
            f"""
            <details style="margin-left: 1rem; margin-top: 0.5rem; margin-bottom: 0.5rem;">
             <summary style="cursor: pointer; font-weight: bold;">Voir l'ancienne version</summary>
             <div
              style="color: red; border-left: 3px solid red; padding-left: 1rem;
              margin-top: 0.5rem;"
             >
              {previous_content}
             </div>
            </details>
"""
        )
    history_parts.append("</div>")
    return "".join(history_parts)


def _is_abrogated(
    latest_version: ArticleVersion,
    operation_by_id: dict[str, Operation],
) -> bool:
    operation_id = latest_version.get("operation_id")
    if not operation_id:
        return False
    latest_operation = operation_by_id.get(str(operation_id))
    if not latest_operation:
        return False
    return latest_operation.operation_type == OperationType.REMOVE
