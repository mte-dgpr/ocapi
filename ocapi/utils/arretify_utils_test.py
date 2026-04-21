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

from ocapi.utils.arretify_utils import extract_and_strip_images, extract_specs
from ocapi.utils.utils import _assert_html_equal, minify_html_fragment


def test_extract_specs_returns_only_requested_data_spec() -> None:
    soup = BeautifulSoup(
        """
<html><body>
 <div data-spec="visa">visa 1</div>
 <div data-spec="motifs">motif 1</div>
 <p data-spec="visa">visa 2</p>
</body></html>
""",
        "html.parser",
    )

    visa_tags = extract_specs(soup, "visa")

    assert len(visa_tags) == 2
    assert [tag.get_text(strip=True) for tag in visa_tags] == ["visa 1", "visa 2"]


def test_extract_specs_returns_empty_list_when_missing_spec() -> None:
    soup = BeautifulSoup("<html><body><div>sans spec</div></body></html>", "html.parser")

    assert extract_specs(soup, "visa") == []


def test_extract_and_strip_images() -> None:
    """Verify that image src attributes are replaced by tokens and that the map is correct."""
    html_content = """
    <p>Here is an image: <img src="http://example.com/image1.png" alt="Image 1"></p>
    <p>Another image: <img src="http://example.com/image2.jpg" alt="Image 2"></p>
    """
    modified_html, img_map = extract_and_strip_images(minify_html_fragment(html_content))

    expected_modified_html = """
    <p>Here is an image: <img src="IMG_000" alt="Image 1"></p>
    <p>Another image: <img src="IMG_001" alt="Image 2"></p>
    """
    expected_img_map = {
        "IMG_000": "http://example.com/image1.png",
        "IMG_001": "http://example.com/image2.jpg",
    }

    _assert_html_equal(modified_html, minify_html_fragment(expected_modified_html))
    assert img_map == expected_img_map
