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
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluate_detection import compare_operations, compute_scores, load_ground_truth  # noqa: E402


class TestCompareOperations:
    def test_perfect_match(self):
        ops = [
            ("2023-01-01", "1", "2022-01-01", "2", "REPLACE"),
            ("2023-01-01", "2", "2022-01-01", "3", "ADD"),
        ]
        tp, fp, fn = compare_operations(ops, ops)
        assert (tp, fp, fn) == (2, 0, 0)

    def test_no_overlap(self):
        detected = [("2023-01-01", "1", "2022-01-01", "2", "REPLACE")]
        gt = [("2023-06-01", "5", "2022-01-01", "3", "ADD")]
        tp, fp, fn = compare_operations(detected, gt)
        assert (tp, fp, fn) == (0, 1, 1)

    def test_partial_match(self):
        detected = [
            ("2023-01-01", "1", "2022-01-01", "2", "REPLACE"),
            ("2023-01-01", "3", "2022-01-01", "4", "ADD"),
        ]
        gt = [
            ("2023-01-01", "1", "2022-01-01", "2", "REPLACE"),
            ("2023-01-01", "5", "2022-01-01", "6", "REMOVE"),
        ]
        tp, fp, fn = compare_operations(detected, gt)
        assert (tp, fp, fn) == (1, 1, 1)

    def test_empty_detected(self):
        gt = [("2023-01-01", "1", "2022-01-01", "2", "REPLACE")]
        tp, fp, fn = compare_operations([], gt)
        assert (tp, fp, fn) == (0, 0, 1)

    def test_empty_ground_truth(self):
        detected = [("2023-01-01", "1", "2022-01-01", "2", "REPLACE")]
        tp, fp, fn = compare_operations(detected, [])
        assert (tp, fp, fn) == (0, 1, 0)

    def test_both_empty(self):
        tp, fp, fn = compare_operations([], [])
        assert (tp, fp, fn) == (0, 0, 0)

    def test_duplicate_handling(self):
        key = ("2023-01-01", "1", "2022-01-01", "2", "REPLACE")
        detected = [key, key, key]
        gt = [key, key]
        tp, fp, fn = compare_operations(detected, gt)
        assert (tp, fp, fn) == (2, 1, 0)

    def test_wrong_operation_type_is_fp_and_fn(self):
        detected = [("2023-01-01", "1", "2022-01-01", "2", "ADD")]
        gt = [("2023-01-01", "1", "2022-01-01", "2", "REPLACE")]
        tp, fp, fn = compare_operations(detected, gt)
        assert (tp, fp, fn) == (0, 1, 1)


class TestComputeScores:
    def test_perfect_scores(self):
        s = compute_scores(tp=5, fp=0, fn=0)
        assert s.precision == 1.0
        assert s.recall == 1.0
        assert s.f1 == 1.0

    def test_zero_scores(self):
        s = compute_scores(tp=0, fp=3, fn=2)
        assert s.precision == 0.0
        assert s.recall == 0.0
        assert s.f1 == 0.0

    def test_all_zeros(self):
        s = compute_scores(tp=0, fp=0, fn=0)
        assert s.precision == 0.0
        assert s.recall == 0.0
        assert s.f1 == 0.0

    def test_known_values(self):
        s = compute_scores(tp=4, fp=1, fn=2)
        assert s.precision == pytest.approx(4 / 5)
        assert s.recall == pytest.approx(4 / 6)
        assert s.f1 == pytest.approx(2 * (4 / 5) * (4 / 6) / ((4 / 5) + (4 / 6)))

    def test_precision_only(self):
        s = compute_scores(tp=3, fp=0, fn=5)
        assert s.precision == 1.0
        assert s.recall == pytest.approx(3 / 8)

    def test_recall_only(self):
        s = compute_scores(tp=3, fp=5, fn=0)
        assert s.recall == 1.0
        assert s.precision == pytest.approx(3 / 8)


class TestLoadGroundTruth:
    def test_filters_autre(self, tmp_path):
        ops = [
            {
                "id": "1",
                "source_id": {"arrete_id": "2023-01-01", "article_id": "1"},
                "target_id": {"arrete_id": "2022-01-01", "article_id": "2"},
                "operation_type": "REPLACE",
            },
            {
                "id": "2",
                "source_id": {"arrete_id": "2023-01-01", "article_id": "3"},
                "target_id": {"arrete_id": "2022-01-01", "article_id": "4"},
                "operation_type": "AUTRE",
            },
        ]
        gt_dir = tmp_path / "test_aiot"
        gt_dir.mkdir()
        (gt_dir / "operations.json").write_text(json.dumps(ops))

        import evaluate_detection as mod

        original = mod._GROUND_TRUTH_DIR
        mod._GROUND_TRUTH_DIR = tmp_path
        try:
            keys = load_ground_truth("test_aiot")
        finally:
            mod._GROUND_TRUTH_DIR = original

        assert len(keys) == 1
        assert keys[0] == ("2023-01-01", "1", "2022-01-01", "2", "REPLACE")
