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
"""Snapshot tests: non-regression on real ICPE cases without LLM."""

import json
import os
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ocapi.pipeline import run_pipeline
from ocapi.snapshots.config import SNAPSHOT_CASES
from ocapi.snapshots.llm_mock import mock_call_llm_api_for_subtarget
from ocapi.utils.io_utils import article_history_to_json_dict, load_arrete_files, load_operations

# Set UPDATE_SNAPSHOTS=1 to regenerate expected snapshots
UPDATE_SNAPSHOTS = os.environ.get("UPDATE_SNAPSHOTS", "").strip() in ("1", "true", "yes")


def _normalize_html_whitespace(html: str) -> str:
    """Normalize HTML whitespace for stable comparison across environments."""
    return re.sub(r"\s+", " ", html).strip()


def _strip_content_for_structure(obj: Any) -> Any:
    """Drop ``content`` values to ignore LLM-mock noise.

    The mock LLM returns the target article unchanged but its output varies
    depending on the (non-deterministic) graph traversal order, creating
    cascading content diffs.  Structural fields (keys, operation_id,
    status_code, version) are kept and fully compared.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in sorted(obj.items()):
            if k == "content":
                continue
            out[k] = _strip_content_for_structure(v)
        return out
    if isinstance(obj, list):
        return [_strip_content_for_structure(x) for x in obj]
    return obj


def _normalize_snapshot(obj: Any) -> Any:
    """Normalise a snapshot object for deterministic comparison."""
    stripped = _strip_content_for_structure(obj)
    if isinstance(stripped, dict):
        return dict(sorted(stripped.items()))
    return stripped


def _strip_none_values(obj: Any) -> Any:
    """Recursively drop ``None`` values so snapshot JSON matches across Pydantic versions."""
    if isinstance(obj, dict):
        return {k: _strip_none_values(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none_values(x) for x in obj]
    return obj


@pytest.mark.snapshot
@pytest.mark.parametrize("arretes_dir,consolidation_dir", SNAPSHOT_CASES)
def test_snapshot_pipeline_output(
    arretes_dir: Path, consolidation_dir: Path, tmp_path: Path
) -> None:
    """Run pipeline with pre-loaded operations (no LLM) and compare outputs."""
    if not arretes_dir.exists() or not consolidation_dir.exists():
        pytest.skip(f"Snapshot fixtures not found: {arretes_dir} or {consolidation_dir}")

    aiot = arretes_dir.name
    arrete_files = load_arrete_files(arretes_dir, aiot)
    if not arrete_files:
        pytest.skip(f"No arrêtés loaded for {aiot} (incompatible Arrêtify version)")
    operations = load_operations(consolidation_dir)

    with patch(
        "ocapi.step_resolution.apply_ops.call_llm_api",
        side_effect=mock_call_llm_api_for_subtarget,
    ):
        ops, history, _arretes, permis = run_pipeline(
            arrete_files,
            enable_detection=False,
            enable_rendering=True,
            operations=operations,
        )

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    ops_dict = [op.model_dump(mode="json") for op in ops]
    with (output_dir / "operations.json").open("w", encoding="utf-8") as f:
        json.dump(ops_dict, f, ensure_ascii=False, indent=2)

    with (output_dir / "history.json").open("w", encoding="utf-8") as f:
        json.dump(article_history_to_json_dict(history), f, ensure_ascii=False, indent=2)

    if permis:
        (output_dir / "permis.html").write_text(permis.to_html(), encoding="utf-8")

    snapshot_dir = consolidation_dir

    if UPDATE_SNAPSHOTS:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for filename in ["operations.json", "history.json"]:
            data = json.loads((output_dir / filename).read_text(encoding="utf-8"))
            (snapshot_dir / filename).write_text(
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
            )
        if permis:
            (snapshot_dir / "permis.html").write_bytes((output_dir / "permis.html").read_bytes())
        pytest.skip("Snapshots updated. Run without UPDATE_SNAPSHOTS=1 to verify.")

    if not snapshot_dir.exists():
        pytest.skip(
            f"Expected snapshots not found: {snapshot_dir}. "
            "Run with UPDATE_SNAPSHOTS=1 to generate."
        )

    for filename in ["operations.json", "history.json"]:
        expected_path = snapshot_dir / filename
        if expected_path.exists():
            expected = _strip_none_values(json.loads(expected_path.read_text(encoding="utf-8")))
            actual = _strip_none_values(
                json.loads((output_dir / filename).read_text(encoding="utf-8"))
            )
            assert _normalize_snapshot(actual) == _normalize_snapshot(
                expected
            ), f"Snapshot mismatch: {filename}"

    if permis:
        actual_html = (output_dir / "permis.html").read_text(encoding="utf-8")
        assert len(actual_html) > 0, "permis.html is empty"
        assert "data-spec" in actual_html, "permis.html has no data-spec attributes"
