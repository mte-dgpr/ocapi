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

from bs4 import BeautifulSoup

from ocapi.step_rendering.make_main_content import make_permit_content
from ocapi.types import ArreteFile, ArticleHistory


class TestIntegrationWithArticleFilter:
    """Verify superfluous sections are excluded from the consolidated HTML."""

    def test_superfluous_articles_excluded_from_permit(self) -> None:
        html = """
<html><body data-arretify_version="0.1.0">
 <main data-spec="main">
  <section data-spec="section" data-number="1" data-title="DISPOSITIONS GÉNÉRALES">
   <h1 data-spec="section_title">ARTICLE 1 DISPOSITIONS GÉNÉRALES</h1>
   <p>Article important</p>
  </section>
  <section data-spec="section" data-number="2" data-title="FRAIS">
   <h1 data-spec="section_title">ARTICLE 2 FRAIS</h1>
   <p>Article superflu</p>
  </section>
  <section data-spec="section" data-number="3" data-title="SANCTIONS">
   <h1 data-spec="section_title">ARTICLE 3 SANCTIONS</h1>
   <p>Autre article superflu</p>
  </section>
 </main>
</body></html>
"""
        arrete = ArreteFile(
            id="2020-01-01",
            aiot="0001",
            filename="ap_initial",
            soup=BeautifulSoup(html, "html.parser"),
            status=True,
        )
        history: ArticleHistory = {}
        result = make_permit_content(history, [arrete], [])

        assert "Article important" in result
        assert "Article superflu" not in result
        assert "Autre article superflu" not in result
