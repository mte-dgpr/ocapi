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
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import evaluate_detection as mod  # noqa: E402
from evaluate_detection import compare_operations, compute_scores, load_ground_truth  # noqa: E402

from ocapi.llm_utils import TokenUsage  # noqa: E402


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

        original = mod._GROUND_TRUTH_DIR
        mod._GROUND_TRUTH_DIR = tmp_path
        try:
            keys = load_ground_truth("test_aiot")
        finally:
            mod._GROUND_TRUTH_DIR = original

        assert len(keys) == 1
        assert keys[0] == ("2023-01-01", "1", "2022-01-01", "2", "REPLACE")


class TestAiotResultUsageSnapshot:
    def test_usage_is_copied_to_avoid_mutation(self) -> None:
        usage = TokenUsage(prompt_tokens=11, completion_tokens=5)

        result = mod.AiotResult(
            aiot="0001234567",
            gt_count=1,
            detected_count=2,
            validated_count=2,
            tp=1,
            fp=0,
            fn=0,
            scores=mod.Scores(precision=1.0, recall=1.0, f1=1.0),
            usage=usage,
        )

        usage.prompt_tokens = 99
        usage.completion_tokens = 77

        assert result.usage.prompt_tokens == 11
        assert result.usage.completion_tokens == 5


class TestValidatedOperationKeys:
    def test_validated_keys_keep_only_non_low_severity_ops(self):
        low_severity_op = {
            "source_id": {"arrete_id": "2023-01-01", "article_id": "1"},
            "target_id": {"arrete_id": "2022-01-01", "article_id": "2"},
            "operation_type": "REMOVE",
        }
        valid_op = {
            "source_id": {"arrete_id": "2023-02-01", "article_id": "3"},
            "target_id": {"arrete_id": "2022-02-01", "article_id": "4"},
            "operation_type": "REPLACE",
        }
        detected_ops = [low_severity_op, valid_op]
        arrete_files = [object()]

        with (
            patch.object(
                mod,
                "build_graph",
                return_value=(None, None, None, detected_ops),
            ) as build_graph_mock,
            patch.object(
                mod,
                "is_low_severity_op",
                side_effect=lambda op: op == low_severity_op,
            ),
        ):
            validated_keys, validated_ops = mod._validated_operation_keys(
                detected_ops, arrete_files
            )

        assert build_graph_mock.call_args.args == (detected_ops, arrete_files)
        assert validated_ops == [valid_op]
        assert validated_keys == [("2023-02-01", "3", "2022-02-01", "4", "REPLACE")]


class TestRunScoreMode:
    def _make_ops_file(self, path: Path) -> None:
        ops = [
            {
                "id": "op-1",
                "source_id": {"arrete_id": "2023-01-01", "article_id": "1"},
                "target_id": {"arrete_id": "2022-01-01", "article_id": "2"},
                "operation_type": "REPLACE",
            }
        ]
        path.mkdir(parents=True, exist_ok=True)
        (path / "operations.json").write_text(json.dumps(ops))

    def _make_gt_file(self, path: Path) -> None:
        self._make_ops_file(path)

    def test_ops_dir_is_a_file_returns_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ):
        ops_dir = tmp_path / "ops.json"
        ops_dir.write_text("not a directory")

        args = mod.argparse.Namespace(
            aiot=None,
            model="some_model",
            save_score=False,
        )
        with caplog.at_level("ERROR"):
            result = mod._run_score_mode(args, ops_dir)

        assert result == 1
        assert "not a directory" in caplog.text

    def test_explicit_aiot_missing_operations_json_returns_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ):
        ops_dir = tmp_path / "ops"
        ops_dir.mkdir()

        args = mod.argparse.Namespace(
            aiot=["missing_aiot"],
            model="some_model",
            save_score=False,
        )
        with caplog.at_level("ERROR"):
            result = mod._run_score_mode(args, ops_dir)

        assert result == 1
        assert "missing_aiot" in caplog.text
        assert "operations.json" in caplog.text

    def test_explicit_aiot_with_existing_operations_json_succeeds(self, tmp_path: Path):
        ops_dir = tmp_path / "ops"
        gt_dir = tmp_path / "gt"
        aiot = "0001234567"

        self._make_ops_file(ops_dir / aiot)
        self._make_gt_file(gt_dir / aiot)

        args = mod.argparse.Namespace(
            aiot=[aiot],
            model="some_model",
            save_score=False,
        )

        original_gt = mod._GROUND_TRUTH_DIR
        original_arretes = mod._ARRETES_HTML_DIR
        mod._GROUND_TRUTH_DIR = gt_dir
        mod._ARRETES_HTML_DIR = tmp_path / "arretes_html_nonexistent"
        try:
            result = mod._run_score_mode(args, ops_dir)
        finally:
            mod._GROUND_TRUTH_DIR = original_gt
            mod._ARRETES_HTML_DIR = original_arretes

        assert result == 0
