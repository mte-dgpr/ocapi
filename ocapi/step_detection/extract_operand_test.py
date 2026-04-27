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
import unittest

from ocapi.step_detection.extract_operand import extract_operand_with_images, pick_arretify_section
from ocapi.utils.testing import assert_html_equal
from ocapi.utils.utils import minify_html_fragment


class TestPickArretifySection(unittest.TestCase):
    def test_pick_normal_section(self) -> None:
        html = """
        <section data-spec="section" data-number="1.1">
            Ceci est le contenu de l'article 1.1.
        </section>
        <section data-spec="section" data-number="1.2">
            Ceci est le contenu de l'article 1.2.
        </section>
        """
        result = pick_arretify_section(html=minify_html_fragment(html), source_article="1.2")
        assert result is not None
        expected = """
        <section data-spec="section" data-number="1.2">
            Ceci est le contenu de l'article 1.2.
        </section>
        """
        assert_html_equal(result, minify_html_fragment(expected))

    def test_pick_normal_section_not_found(self) -> None:
        html = '<section data-spec="section" data-number="1.1">Contenu</section>'
        result = pick_arretify_section(html=html, source_article="9.9")
        assert result is None

    def test_pick_appendix_footer(self) -> None:
        html = """
        <footer data-spec="appendix">
            <section data-spec="section" data-number="1.1">Annexe 1.1</section>
        </footer>
        """
        result = pick_arretify_section(html=html, source_article="APPENDIX")
        assert result is not None
        assert "Annexe 1.1" in result
        assert "footer" in result

    def test_pick_appendix_footer_not_found(self) -> None:
        html = "<div>Pas de footer appendix</div>"
        result = pick_arretify_section(html=html, source_article="APPENDIX")
        assert result is None

    def test_pick_appendix_numbered_section(self) -> None:
        html = """
        <footer data-spec="appendix">
            <section data-spec="section" data-number="1.1.1.1">Annexe 1.1.1.1</section>
            <section data-spec="section" data-number="2.1">Annexe 2.1</section>
        </footer>
        """
        result = pick_arretify_section(html=html, source_article="APPENDIX:2.1")
        assert result is not None
        assert "Annexe 2.1" in result
        assert "1.1.1.1" not in result

    def test_pick_appendix_numbered_section_not_found(self) -> None:
        html = """
        <footer data-spec="appendix">
            <section data-spec="section" data-number="1.1">Annexe 1.1</section>
        </footer>
        """
        result = pick_arretify_section(html=html, source_article="APPENDIX:9.9")
        assert result is None

    def test_pick_appendix_numbered_no_footer(self) -> None:
        html = "<div>Pas de footer</div>"
        result = pick_arretify_section(html=html, source_article="APPENDIX:1.1")
        assert result is None


class TestExtractOperand(unittest.TestCase):
    def test_extract_operand_success(self) -> None:
        html = """
        <section data-spec="section" data-number="1.2">
            Voici le nouveau contenu operand de l'article. Inclut une image :
            <img src="image1.png" />
        </section>
        """
        minified_html = minify_html_fragment(html)

        start_marker = "Voici le nouveau "
        end_marker = '<img src="image1.png"/>'
        img_map = {"image1.png": "http://example.com/image1.png"}

        operand = extract_operand_with_images(
            html_block=minified_html,
            source_article="1.2",
            start_marker=start_marker,
            end_marker=end_marker,
            img_map=img_map,
        )
        assert operand is not None
        assert "Voici le nouveau" in operand
        assert "http://example.com/image1.png" in operand
        assert_html_equal(
            operand,
            minify_html_fragment(
                """
                Voici le nouveau contenu operand de l'article. Inclut une image :
                <img src="http://example.com/image1.png"/>
            """
            ),
        )

    def test_extract_operand_start_marker_not_found_logs_warning(self) -> None:
        html = '<section data-spec="section" data-number="1"><p>Contenu</p></section>'

        with self.assertLogs("ocapi.step_detection.extract_operand", level="WARNING") as cm:
            operand = extract_operand_with_images(
                html_block=html,
                source_article="1",
                start_marker="INTROUVABLE",
                end_marker="</p>",
                img_map={},
                operation_id="op-42",
            )

        assert operand is None
        assert any("Start marker not found" in msg for msg in cm.output)
        assert any("op-42" in msg for msg in cm.output)

    def test_extract_operand_end_marker_not_found_logs_warning(self) -> None:
        html = '<section data-spec="section" data-number="1"><p>Contenu</p></section>'

        with self.assertLogs("ocapi.step_detection.extract_operand", level="WARNING") as cm:
            operand = extract_operand_with_images(
                html_block=html,
                source_article="1",
                start_marker="Contenu",
                end_marker="INTROUVABLE",
                img_map={},
                operation_id="op-99",
            )

        assert operand is None
        assert any("End marker not found" in msg for msg in cm.output)
        assert any("op-99" in msg for msg in cm.output)

    def test_extract_operand_no_markers(self) -> None:
        html = """
        <section data-spec="section" data-number="L123-4">
            <p>This is the content of article L123-4.</p>
        </section>
        """
        start_marker = "<p>Non-existent start"
        end_marker = "</p>"

        operand = extract_operand_with_images(
            html_block=minify_html_fragment(html),
            source_article="L123-4",
            start_marker=start_marker,
            end_marker=end_marker,
            img_map={},
        )
        assert operand is None
