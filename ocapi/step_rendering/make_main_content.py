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

from bs4 import BeautifulSoup

from ocapi.types import ArreteFile, ArticleHistory, NodeId, Operation, OperationType


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

    # Trouver toutes les sections (articles) dans le body
    sections = main.find_all("section", attrs={"data-spec": "section"})

    for section in sections:
        article_id = section.get("data-number")
        if not article_id:
            continue

        section.replace_with(
            make_consolidated_section(section, article_id, operations, history, ap_initial_id)
        )

    return str(main)


def make_consolidated_section(
    original_section: BeautifulSoup,
    article_id: str,
    operations: list[Operation],
    history: ArticleHistory,
    arrete_id: str,
) -> BeautifulSoup:
    """
    Génère la section consolidée pour un article donné en utilisant l'historique.
    Affiche en rouge l'historique des modifications puis le contenu actuel.
    """
    key = NodeId(arrete_id=arrete_id, article_id=article_id)
    if key not in history:
        return original_section  # Pas de modifications, retourner l'original

    # Récupérer toutes les versions de l'article
    versions = history[key]

    # Construire l'historique des modifications
    history_html = '<div style="color: red; margin-bottom: 1rem;">'

    for i, version in enumerate(versions):
        op_id = version["operation_id"]

        if i == 0:
            # Première version = création
            if op_id:
                op = next((o for o in operations if o.id == op_id), None)
                if op:
                    history_html += (
                        f"<p><strong>Article créé par l'arrêté "
                        f"{op.source_id.arrete_id}</strong></p>"
                    )
                else:
                    history_html += "<p><strong>Article créé par l'arrêté initial</strong></p>"
            else:
                history_html += "<p><strong>Article créé par l'arrêté initial</strong></p>"
        else:
            # Versions suivantes = modifications
            if op_id:
                op = next((o for o in operations if o.id == op_id), None)
                if op:
                    op_type_text = (
                        "modifié"
                        if op.operation_type == OperationType.REPLACE
                        else "abrogé" if op.operation_type == OperationType.REMOVE else "créé"
                    )
                    source_article = (
                        f"Article {op.source_id.article_id}"
                        if op.source_id.article_id
                        else "l'arrêté"
                    )
                    history_html += (
                        f"<p><strong>Article {op_type_text} par {source_article} "
                        f"de l'arrêté {op.source_id.arrete_id}</strong></p>"
                    )

                    # Ajouter un menu déroulant avec l'ancienne version
                    if i > 0:  # Il y a une version précédente
                        previous_version = versions[i - 1]
                        history_html += f"""
                        <details style="margin-left: 1rem; margin-top: 0.5rem;
                                        margin-bottom: 0.5rem;">
                         <summary style="cursor: pointer; font-weight: bold;">
                          Voir l'ancienne version
                         </summary>
                         <div style="color: red; border-left: 3px solid red;
                                     padding-left: 1rem; margin-top: 0.5rem;">
                          {previous_version['content']}
                         </div>
                        </details>
                        """

    history_html += "</div>"

    # Récupérer la dernière version de l'article
    latest_version = versions[-1]

    # Vérifier si l'article est abrogé (dernière opération est REMOVE)
    last_op_id = latest_version["operation_id"]
    is_abrogated = False
    if last_op_id:
        last_op = next((o for o in operations if o.id == last_op_id), None)
        if last_op and last_op.operation_type == OperationType.REMOVE:
            is_abrogated = True

    # Construire le contenu consolidé
    if is_abrogated:
        consolidated_content = f"{history_html}<p><em>Article abrogé</em></p>"
    else:
        consolidated_content = f"{history_html}{latest_version['content']}"

    # Retourner le contenu consolidé sous forme de BeautifulSoup
    return BeautifulSoup(consolidated_content, "html.parser")
