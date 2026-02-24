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
from bs4 import BeautifulSoup, Tag


def list_top_sections(soup: BeautifulSoup | Tag) -> list[Tag]:
    """
    Itère sur les sections de plus haut niveau dans le document (sans parent section).
    """
    return [sec for sec in soup.find_all("section") if sec.find_parent("section") is None]


def extract_specs(soup: BeautifulSoup, spec: str) -> list[Tag]:
    """Extrait les blocs HTML correspondant à une spec Arrêtify."""
    return [tag for tag in soup.find_all(attrs={"data-spec": spec}) if isinstance(tag, Tag)]


def extract_first_spec_html(soup: BeautifulSoup, spec: str) -> str:
    tags = extract_specs(soup, spec)
    if not tags:
        return ""
    return str(tags[0])


def extract_first_spec_text(soup: BeautifulSoup, spec: str) -> str:
    tags = extract_specs(soup, spec)
    if not tags:
        return ""
    return str(tags[0].get_text(" ", strip=True))


def extract_main(soup: BeautifulSoup) -> str:
    main = soup.find("main")
    if main is None:
        return ""
    return str(main)
