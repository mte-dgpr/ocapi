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

from ocapi.types import ArreteFile, ArticlesContentMap, NodeId


def make_contenu_permis(versions: list[ArticlesContentMap], arrete_files: list[ArreteFile]) -> str:
    """
    Génère le contenu consolidé du permis à partir des versions calculées.

    1. Part de l'AP initial (arrete_files[0])
    2. Pour chaque article de l'AP initial, applique la dernière version si elle existe
    3. Retourne le HTML consolidé (sans header)
    """
    if not arrete_files:
        return ""

    ap_initial = arrete_files[0]
    consolidated_soup = BeautifulSoup(str(ap_initial.soup), "html.parser")
    main = consolidated_soup.find("main")
    if main is None:
        return ""

    latest_map = versions[-1] if versions else {}
    sections = main.find_all("section", attrs={"data-spec": "section"})

    for section in sections:
        article_id = section.get("data-number")
        if not article_id:
            continue
        try:
            node_id = NodeId(arrete_id=ap_initial.id, article_id=article_id)
        except ValueError:
            continue
        content = latest_map.get(node_id)
        if content:
            section.replace_with(BeautifulSoup(content, "html.parser"))

    return str(main)
