#!/usr/bin/env python3
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
"""Evaluate LLM operation detection against ground-truth annotations.

Usage (from repo root):
  python scripts/evaluate_detection.py --model openai_gpt5mini
  python scripts/evaluate_detection.py --model mistral_medium --aiot 0003013459
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ocapi.step_chunking.step_chunking import step_chunking  # noqa: E402
from ocapi.step_detection import step_detection as step_detection_module  # noqa: E402
from ocapi.step_detection.step_detection import step_detection  # noqa: E402
from ocapi.types import Operation  # noqa: E402
from ocapi.utils.io_utils import load_arrete_files  # noqa: E402
from ocapi.utils.llm_utils import config_model_llm  # noqa: E402
from ocapi.utils.logging_utils import get_logger, initialize_root_logger  # noqa: E402

_LOGGER = get_logger(__name__)

_GROUND_TRUTH_DIR = _PROJECT_ROOT / "examples" / "ground-truth"
_ARRETES_HTML_DIR = _PROJECT_ROOT / "examples" / "arretes_html"

_VALID_OP_TYPES = {"ADD", "REPLACE", "REMOVE"}

# (source_arrete, source_article, target_arrete, target_article, operation_type)
OperationKey = tuple[str, str, str, str, str]


def _operation_key_from_dict(op: dict) -> OperationKey:
    return (
        op["source_id"]["arrete_id"],
        op["source_id"]["article_id"],
        op["target_id"]["arrete_id"],
        op["target_id"]["article_id"],
        op["operation_type"],
    )


def _operation_key(op: Operation) -> OperationKey:
    return (
        op.source_id.arrete_id,
        op.source_id.article_id,
        op.target_id.arrete_id,
        op.target_id.article_id,
        op.operation_type.value,
    )


def load_ground_truth(aiot: str) -> list[OperationKey]:
    """Load ground-truth operations for an AIOT, filtering out AUTRE."""
    gt_path = _GROUND_TRUTH_DIR / aiot / "operations.json"
    raw = json.loads(gt_path.read_text(encoding="utf-8"))
    return [_operation_key_from_dict(op) for op in raw if op["operation_type"] in _VALID_OP_TYPES]


def compare_operations(
    detected: list[OperationKey],
    ground_truth: list[OperationKey],
) -> tuple[int, int, int]:
    """Compare detected operations with ground-truth using multiset matching.

    Returns (true_positives, false_positives, false_negatives).
    """
    detected_counts = Counter(detected)
    gt_counts = Counter(ground_truth)

    tp = sum(min(detected_counts[k], gt_counts[k]) for k in detected_counts if k in gt_counts)
    fp = sum(detected_counts.values()) - tp
    fn = sum(gt_counts.values()) - tp
    return tp, fp, fn


@dataclass
class Scores:
    precision: float
    recall: float
    f1: float


def compute_scores(tp: int, fp: int, fn: int) -> Scores:
    """Compute precision, recall, and F1-score from raw counts."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return Scores(precision=precision, recall=recall, f1=f1)


def run_detection_for_aiot(aiot: str, model_key: str) -> list[Operation]:
    """Run chunking + detection on all arrêtés of an AIOT."""
    arretes_dir = _ARRETES_HTML_DIR / aiot
    arrete_files = load_arrete_files(arretes_dir, aiot)
    if not arrete_files:
        _LOGGER.warning(f"No arrêtés loaded for {aiot}")
        return []

    step_detection_module.LLM_CFG = config_model_llm(model_key)

    start_date = arrete_files[0].id
    all_ops: list[Operation] = []
    for arrete_file in arrete_files:
        if arrete_file.id <= start_date:
            continue
        docs, img_map = step_chunking(arrete_file)
        detected_ops = step_detection(docs, arrete_file.id, img_map)
        all_ops.extend(detected_ops)
        _LOGGER.info(f"  {arrete_file.id}: {len(detected_ops)} operations detected")
    return all_ops


def _available_aiots() -> list[str]:
    if not _GROUND_TRUTH_DIR.exists():
        return []
    return sorted(d.name for d in _GROUND_TRUTH_DIR.iterdir() if d.is_dir())


@dataclass
class AiotResult:
    aiot: str
    gt_count: int
    detected_count: int
    tp: int
    fp: int
    fn: int
    scores: Scores


def _write_xlsx(
    results: list[AiotResult],
    overall: Scores,
    total_tp: int,
    total_fp: int,
    total_fn: int,
    model_key: str,
    output_path: Path,
) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Résultats"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    pct_fmt = "0.0%"

    headers = ["AIOT", "Ground-truth", "Détectées", "TP", "FP", "FN", "Precision", "Recall", "F1"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for row_idx, r in enumerate(results, 2):
        ws.cell(row=row_idx, column=1, value=r.aiot)
        ws.cell(row=row_idx, column=2, value=r.gt_count)
        ws.cell(row=row_idx, column=3, value=r.detected_count)
        ws.cell(row=row_idx, column=4, value=r.tp)
        ws.cell(row=row_idx, column=5, value=r.fp)
        ws.cell(row=row_idx, column=6, value=r.fn)
        ws.cell(row=row_idx, column=7, value=r.scores.precision).number_format = pct_fmt
        ws.cell(row=row_idx, column=8, value=r.scores.recall).number_format = pct_fmt
        ws.cell(row=row_idx, column=9, value=r.scores.f1).number_format = pct_fmt

    total_row = len(results) + 2
    total_font = Font(bold=True)
    ws.cell(row=total_row, column=1, value="TOTAL").font = total_font
    ws.cell(row=total_row, column=4, value=total_tp).font = total_font
    ws.cell(row=total_row, column=5, value=total_fp).font = total_font
    ws.cell(row=total_row, column=6, value=total_fn).font = total_font
    ws.cell(row=total_row, column=7, value=overall.precision).number_format = pct_fmt
    ws.cell(row=total_row, column=7).font = total_font
    ws.cell(row=total_row, column=8, value=overall.recall).number_format = pct_fmt
    ws.cell(row=total_row, column=8).font = total_font
    ws.cell(row=total_row, column=9, value=overall.f1).number_format = pct_fmt
    ws.cell(row=total_row, column=9).font = total_font

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = 14

    wb.save(output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate LLM operation detection against ground-truth.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model key from config/llm_models.json (e.g. openai_gpt5mini, mistral_medium)",
    )
    parser.add_argument(
        "--aiot",
        nargs="*",
        help="AIOT(s) to evaluate (default: all available ground-truth AIOTs)",
    )
    parser.add_argument(
        "--xlsx",
        type=Path,
        nargs="?",
        const=None,
        default=False,
        help="Export results to XLSX (optional path; default: eval_<model>_<date>.xlsx)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args(argv)

    initialize_root_logger(level="DEBUG" if args.verbose else "INFO", console_output=True)

    aiots = args.aiot or _available_aiots()
    if not aiots:
        print("No AIOT with ground-truth found.", file=sys.stderr)
        return 1

    model_key = args.model
    _LOGGER.info(f"Model: {model_key}")
    _LOGGER.info(f"AIOTs: {', '.join(aiots)}")

    total_tp, total_fp, total_fn = 0, 0, 0
    results: list[AiotResult] = []

    for aiot in aiots:
        _LOGGER.info(f"\n{'=' * 50}")
        _LOGGER.info(f"AIOT: {aiot}")
        _LOGGER.info(f"{'=' * 50}")

        gt_keys = load_ground_truth(aiot)
        _LOGGER.info(f"Ground-truth: {len(gt_keys)} operations")

        detected_ops = run_detection_for_aiot(aiot, model_key)
        detected_keys = [_operation_key(op) for op in detected_ops]
        _LOGGER.info(f"Detected: {len(detected_keys)} operations")

        tp, fp, fn = compare_operations(detected_keys, gt_keys)
        scores = compute_scores(tp, fp, fn)

        results.append(AiotResult(aiot, len(gt_keys), len(detected_keys), tp, fp, fn, scores))

        print(f"\n--- {aiot} ---")
        print(f"  Ground-truth: {len(gt_keys)}  |  Detected: {len(detected_keys)}")
        print(f"  TP={tp}  FP={fp}  FN={fn}")
        print(f"  Precision: {scores.precision:.3f}")
        print(f"  Recall:    {scores.recall:.3f}")
        print(f"  F1:        {scores.f1:.3f}")

        total_tp += tp
        total_fp += fp
        total_fn += fn

    overall = compute_scores(total_tp, total_fp, total_fn)
    print(f"\n{'=' * 50}")
    print(f"OVERALL ({model_key})")
    print(f"{'=' * 50}")
    print(f"  TP={total_tp}  FP={total_fp}  FN={total_fn}")
    print(f"  Precision: {overall.precision:.3f}")
    print(f"  Recall:    {overall.recall:.3f}")
    print(f"  F1:        {overall.f1:.3f}")

    if args.xlsx is not False:
        xlsx_path = args.xlsx
        if xlsx_path is None:
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            xlsx_path = _PROJECT_ROOT / f"eval_{model_key}_{ts}.xlsx"
        _write_xlsx(results, overall, total_tp, total_fp, total_fn, model_key, xlsx_path)
        print(f"\nResults exported to {xlsx_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
