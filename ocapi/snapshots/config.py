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
"""Configuration for snapshot test cases (ICPE fixtures)."""

from pathlib import Path

# Base path: project root (parent of ocapi package)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Snapshot cases: (arretes_dir, consolidation_dir)
# Each case runs pipeline with --no-detection using pre-loaded operations (no LLM).
# Run `ocapi generate-snapshot-fixtures` once (with LLM) to create operations.json
# for ICPEs that don't have them yet.
SNAPSHOT_CASES: list[tuple[Path, Path]] = [
    (
        _PROJECT_ROOT / "snapshots" / "arretes_html" / "0003013459",
        _PROJECT_ROOT / "snapshots" / "arretes_consolidation" / "0003013459",
    ),
    (
        _PROJECT_ROOT / "snapshots" / "arretes_html" / "0005302394",
        _PROJECT_ROOT / "snapshots" / "arretes_consolidation" / "0005302394",
    ),
    (
        _PROJECT_ROOT / "snapshots" / "arretes_html" / "0005800425",
        _PROJECT_ROOT / "snapshots" / "arretes_consolidation" / "0005800425",
    ),
    (
        _PROJECT_ROOT / "snapshots" / "arretes_html" / "0005804239",
        _PROJECT_ROOT / "snapshots" / "arretes_consolidation" / "0005804239",
    ),
]
