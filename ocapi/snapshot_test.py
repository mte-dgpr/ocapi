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
"""Snapshot tests: non-regression on real ICPE cases without LLM."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from ocapi.pipeline import run_pipeline
from ocapi.snapshot import SNAPSHOT_CASES
from ocapi.step_rendering.step_rendering import permis_to_html
from ocapi.utils.io_utils import (
    article_history_to_json_dict,
    load_arrete_files,
    load_operations,
    write_json_output,
)
from ocapi.utils.testing import normalize_html
from ocapi.utils.utils import strip_none_values

# Set UPDATE_SNAPSHOTS=1 to regenerate expected snapshots
UPDATE_SNAPSHOTS = os.environ.get("UPDATE_SNAPSHOTS", "").strip() in ("1", "true", "yes")


def _run_snapshot_pipeline(
    arretes_dir: Path, consolidation_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Run the pipeline and return (ops_json, history_json, permis_html)."""
    aiot = arretes_dir.name
    arrete_files = load_arrete_files(arretes_dir, aiot)
    operations = load_operations(consolidation_dir)

    ops, history, _arretes, permis = run_pipeline(
        arrete_files,
        enable_detection=False,
        enable_rendering=True,
        enable_llm=False,
        operations=operations,
    )

    ops_json = strip_none_values([op.model_dump(mode="json") for op in ops])
    history_json = strip_none_values(article_history_to_json_dict(history))
    permis_html = permis_to_html(permis) if permis else ""
    return ops_json, history_json, permis_html


@pytest.mark.snapshot
@pytest.mark.parametrize("arretes_dir,consolidation_dir", SNAPSHOT_CASES)
def test_snapshot_pipeline_output(
    arretes_dir: Path, consolidation_dir: Path, tmp_path: Path
) -> None:
    """Run pipeline with pre-loaded operations (no LLM) and compare outputs exactly."""
    if not arretes_dir.exists() or not consolidation_dir.exists():
        pytest.skip(f"Snapshot fixtures not found: {arretes_dir} or {consolidation_dir}")

    aiot = arretes_dir.name
    arrete_files = load_arrete_files(arretes_dir, aiot)
    if not arrete_files:
        pytest.skip(f"No arrêtés loaded for {aiot} (incompatible Arrêtify version)")

    ops_json, history_json, permis_html = _run_snapshot_pipeline(arretes_dir, consolidation_dir)

    snapshot_dir = consolidation_dir

    if UPDATE_SNAPSHOTS:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for filename, data in [("operations.json", ops_json), ("history.json", history_json)]:
            write_json_output(data, snapshot_dir / filename, sort_keys=True)
        if permis_html:
            (snapshot_dir / "permis.html").write_text(
                normalize_html(permis_html), encoding="utf-8", newline="\n"
            )
        pytest.skip("Snapshots updated. Run without UPDATE_SNAPSHOTS=1 to verify.")

    if not snapshot_dir.exists():
        pytest.skip(
            f"Expected snapshots not found: {snapshot_dir}. "
            "Run with UPDATE_SNAPSHOTS=1 to generate."
        )

    for filename, actual_data in [("operations.json", ops_json), ("history.json", history_json)]:
        expected_path = snapshot_dir / filename
        if expected_path.exists():
            expected = strip_none_values(json.loads(expected_path.read_text(encoding="utf-8")))
            assert actual_data == expected, f"Snapshot mismatch: {filename}"

    expected_html_path = snapshot_dir / "permis.html"
    if expected_html_path.exists() and permis_html:
        expected_html = expected_html_path.read_text(encoding="utf-8")
        assert normalize_html(permis_html) == normalize_html(
            expected_html
        ), "Snapshot mismatch: permis.html"


@pytest.mark.snapshot
@pytest.mark.parametrize("arretes_dir,consolidation_dir", SNAPSHOT_CASES)
def test_snapshot_pipeline_is_deterministic(arretes_dir: Path, consolidation_dir: Path) -> None:
    """Run the pipeline twice and verify that outputs are identical."""
    if not arretes_dir.exists() or not consolidation_dir.exists():
        pytest.skip(f"Snapshot fixtures not found: {arretes_dir} or {consolidation_dir}")

    aiot = arretes_dir.name
    arrete_files = load_arrete_files(arretes_dir, aiot)
    if not arrete_files:
        pytest.skip(f"No arrêtés loaded for {aiot} (incompatible Arrêtify version)")

    ops_1, history_1, html_1 = _run_snapshot_pipeline(arretes_dir, consolidation_dir)
    ops_2, history_2, html_2 = _run_snapshot_pipeline(arretes_dir, consolidation_dir)

    assert ops_1 == ops_2, "operations.json differs between runs"
    assert history_1 == history_2, "history.json differs between runs"
    assert normalize_html(html_1) == normalize_html(html_2), "permis.html differs between runs"
