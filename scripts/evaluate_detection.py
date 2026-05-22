#!/usr/bin/env python3
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
"""Evaluate LLM operation detection against ground-truth annotations.

Usage (from repo root):
  python scripts/evaluate_detection.py --model openai_gpt5mini
  python scripts/evaluate_detection.py --model mistral_medium --aiot 0003013459
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402

from ocapi.llm_utils import (  # noqa: E402
    TokenUsage,
    config_model_llm,
    get_accumulated_usage,
    reset_accumulated_usage,
)
from ocapi.step_detection import step_detection as step_detection_module  # noqa: E402
from ocapi.step_detection.step_detection import step_detection  # noqa: E402
from ocapi.types import Operation  # noqa: E402
from ocapi.utils.io_utils import load_arrete_files, load_operations, save_operations  # noqa: E402
from ocapi.utils.logging_utils import get_logger, initialize_root_logger  # noqa: E402

_LOGGER = get_logger(__name__)

_GROUND_TRUTH_DIR = _PROJECT_ROOT / "snapshots" / "ground-truth"
_ARRETES_HTML_DIR = _PROJECT_ROOT / "snapshots" / "arretes_html"

_VALID_OP_TYPES = {"ADD", "REPLACE", "REMOVE"}

# Cost per 1M tokens (USD): {model_id: (input_cost, output_cost)}
_COST_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "mte-api-piag-mistral-medium-latest": (2.00, 6.00),
    "mistral-medium-2508": (0.40, 2.00),
    "mistral-medium-3-5": (1.50, 7.50),
    "mistral-large-2512": (0.50, 1.50),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-haiku-4-20250414": (0.80, 4.00),
    "claude-opus-4-6": (5.00, 25.00),
    "gemini-2.5-pro": (2.50, 10.00),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-3.1-flash-lite-preview": (0.25, 1.50),
    "gemini-3.1-pro-preview": (4.00, 18.00),
}


def _compute_cost(model_id: str, usage: TokenUsage) -> float:
    """Compute cost in USD from token usage."""
    rates = _COST_PER_1M_TOKENS.get(model_id, (0.0, 0.0))
    return (usage.prompt_tokens * rates[0] + usage.completion_tokens * rates[1]) / 1_000_000


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
        detected_ops = step_detection(arrete_file)
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
    elapsed_seconds: float = 0.0
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: float = 0.0


def _write_xlsx(
    results: list[AiotResult],
    overall: Scores,
    total_tp: int,
    total_fp: int,
    total_fn: int,
    model_key: str,
    output_path: Path,
) -> None:

    wb = Workbook()
    ws = wb.active
    ws.title = "Résultats"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    pct_fmt = "0.0%"

    headers = [
        "AIOT",
        "Ground-truth",
        "Détectées",
        "TP",
        "FP",
        "FN",
        "Precision",
        "Recall",
        "F1",
        "Temps (s)",
        "Tokens in",
        "Tokens out",
        "Coût ($)",
    ]
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
        ws.cell(row=row_idx, column=10, value=round(r.elapsed_seconds, 1))
        ws.cell(row=row_idx, column=11, value=r.usage.prompt_tokens)
        ws.cell(row=row_idx, column=12, value=r.usage.completion_tokens)
        ws.cell(row=row_idx, column=13, value=round(r.cost_usd, 4)).number_format = "0.0000"

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
    total_time = sum(r.elapsed_seconds for r in results)
    total_cost = sum(r.cost_usd for r in results)
    total_in = sum(r.usage.prompt_tokens for r in results)
    total_out = sum(r.usage.completion_tokens for r in results)
    ws.cell(row=total_row, column=10, value=round(total_time, 1)).font = total_font
    ws.cell(row=total_row, column=11, value=total_in).font = total_font
    ws.cell(row=total_row, column=12, value=total_out).font = total_font
    c = ws.cell(row=total_row, column=13, value=round(total_cost, 4))
    c.number_format = "0.0000"
    c.font = total_font

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = 14

    wb.save(output_path)


def _print_and_accumulate(
    r: AiotResult,
    total_tp: int,
    total_fp: int,
    total_fn: int,
) -> tuple[int, int, int]:
    print(f"\n--- {r.aiot} ---")
    print(f"  Ground-truth: {r.gt_count}  |  Detected: {r.detected_count}")
    print(f"  TP={r.tp}  FP={r.fp}  FN={r.fn}")
    print(f"  Precision: {r.scores.precision:.3f}")
    print(f"  Recall:    {r.scores.recall:.3f}")
    print(f"  F1:        {r.scores.f1:.3f}")
    return total_tp + r.tp, total_fp + r.fp, total_fn + r.fn


def _run_score_mode(args: argparse.Namespace) -> int:
    """Recompute metrics from existing ops.json files without any LLM call."""
    ops_dir: Path = args.ops_dir

    # Determine which AIOTs to score: either from --aiot or all subdirs with ops.json
    if args.aiot:
        aiots = list(args.aiot)
    else:
        if not ops_dir.exists():
            print(f"--ops-dir not found: {ops_dir}", file=sys.stderr)
            return 1
        aiots = sorted(
            d.name for d in ops_dir.iterdir() if d.is_dir() and (d / "operations.json").exists()
        )

    if not aiots:
        print(f"No operations.json found in {ops_dir}", file=sys.stderr)
        return 1

    _LOGGER.info(f"Score mode — ops-dir: {ops_dir}")
    _LOGGER.info(f"AIOTs: {', '.join(aiots)}")

    total_tp, total_fp, total_fn = 0, 0, 0
    results: list[AiotResult] = []

    for aiot in aiots:
        _LOGGER.info(f"\n{'=' * 50}")
        _LOGGER.info(f"AIOT: {aiot}")
        _LOGGER.info(f"{'=' * 50}")

        gt_keys = load_ground_truth(aiot)
        detected_ops = load_operations(ops_dir / aiot)
        detected_keys = [_operation_key(op) for op in detected_ops]
        _LOGGER.info(f"Ground-truth: {len(gt_keys)}  |  Loaded ops: {len(detected_keys)}")

        tp, fp, fn = compare_operations(detected_keys, gt_keys)
        scores = compute_scores(tp, fp, fn)

        r = AiotResult(aiot, len(gt_keys), len(detected_keys), tp, fp, fn, scores)
        results.append(r)
        total_tp, total_fp, total_fn = _print_and_accumulate(r, total_tp, total_fp, total_fn)

    overall = compute_scores(total_tp, total_fp, total_fn)
    print(f"\n{'=' * 50}")
    print(f"OVERALL (score mode — {args.model})")
    print(f"{'=' * 50}")
    print(f"  TP={total_tp}  FP={total_fp}  FN={total_fn}")
    print(f"  Precision: {overall.precision:.3f}")
    print(f"  Recall:    {overall.recall:.3f}")
    print(f"  F1:        {overall.f1:.3f}")

    if args.xlsx is not False:
        xlsx_path = args.xlsx
        if xlsx_path is None:
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            xlsx_path = _PROJECT_ROOT / f"eval_{args.model}_score_{ts}.xlsx"
        _write_xlsx(results, overall, total_tp, total_fp, total_fn, args.model, xlsx_path)
        print(f"\nResults exported to {xlsx_path}")

    return 0


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
        "--ops-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "In detection mode: directory where ops.json files are saved after each LLM run. "
            "In score mode (--score): directory from which ops.json files are read."
        ),
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help=(
            "Score mode: recompute metrics from existing ops.json files (no LLM call). "
            "Requires --ops-dir."
        ),
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

    if args.model is None:
        print("--model is required.", file=sys.stderr)
        return 1

    # --- score mode ---
    if args.score:
        if args.ops_dir is None:
            print("--score requires --ops-dir.", file=sys.stderr)
            return 1
        return _run_score_mode(args)

    # --- detection mode ---

    aiots = args.aiot or _available_aiots()
    if not aiots:
        print("No AIOT with ground-truth found.", file=sys.stderr)
        return 1

    model_key = args.model
    _LOGGER.info(f"Model: {model_key}")
    _LOGGER.info(f"AIOTs: {', '.join(aiots)}")

    total_tp, total_fp, total_fn = 0, 0, 0
    results: list[AiotResult] = []

    model_cfg = config_model_llm(model_key)
    model_id = model_cfg.model_name

    for aiot in aiots:
        _LOGGER.info(f"\n{'=' * 50}")
        _LOGGER.info(f"AIOT: {aiot}")
        _LOGGER.info(f"{'=' * 50}")

        gt_keys = load_ground_truth(aiot)
        _LOGGER.info(f"Ground-truth: {len(gt_keys)} operations")

        reset_accumulated_usage()
        t0 = time.monotonic()
        detected_ops = run_detection_for_aiot(aiot, model_key)
        elapsed = time.monotonic() - t0
        usage = get_accumulated_usage()
        cost = _compute_cost(model_id, usage)

        if args.ops_dir is not None:
            out_dir = args.ops_dir / aiot
            save_operations(detected_ops, out_dir)
            _LOGGER.info(f"Ops saved to {out_dir / 'operations.json'}")

        detected_keys = [_operation_key(op) for op in detected_ops]
        _LOGGER.info(f"Detected: {len(detected_keys)} operations")

        tp, fp, fn = compare_operations(detected_keys, gt_keys)
        scores = compute_scores(tp, fp, fn)

        r = AiotResult(
            aiot,
            len(gt_keys),
            len(detected_keys),
            tp,
            fp,
            fn,
            scores,
            elapsed_seconds=elapsed,
            usage=usage,
            cost_usd=cost,
        )
        results.append(r)

        total_tp, total_fp, total_fn = _print_and_accumulate(r, total_tp, total_fp, total_fn)
        print(f"  Time: {elapsed:.1f}s  |  Tokens: {usage.total_tokens}  |  Cost: ${cost:.4f}")

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
