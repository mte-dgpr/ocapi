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
import re
import unicodedata
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class IdCounter:
    value: int = 0


def make_id(counter: IdCounter) -> str:
    counter.value += 1
    return str(counter.value)


def minify_html_fragment(html: str) -> str:
    """
    Minification légère et normalisation Unicode pour un fragment HTML.
    - supprime <script>/<style>
    - normalize Unicode
    - enlève espaces entre balises et runs d'espaces
    """
    s = str(html or "")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"(?is)<script.*?>.*?</script>", "", s)
    s = re.sub(r"(?is)<style.*?>.*?</style>", "", s)
    s = re.sub(r">\s+<", "><", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def _assert_html_equal(minified_html1: str, minified_html2: str) -> None:
    """Compare deux HTML en normalisant les espaces blancs"""
    soup1 = BeautifulSoup(minified_html1, "html.parser")
    soup2 = BeautifulSoup(minified_html2, "html.parser")
    assert soup1.prettify() == soup2.prettify()
