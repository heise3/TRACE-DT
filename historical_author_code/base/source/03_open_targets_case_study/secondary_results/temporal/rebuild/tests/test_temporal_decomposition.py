#!/usr/bin/env python3
"""Executable acceptance tests for the V12 temporal decomposition patch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import random
import sys
import tempfile
from pathlib import Path


PATCH_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PATCH_ROOT / "build_temporal_decomposition.py"
SPEC = importlib.util.spec_from_file_location("temporal_decomposition", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot import {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

EXPECTED_CELL_SHA256 = "424c080e0fa1a5bf1a4f542bd7142e286499c5272908936bed6f0d7117820ad9"
EXPECTED_CONTEXT_SHA256 = "0214245e4d1d32da1df3e91c39061dddf466b0604f76546223a6b9527fc7fb60"
EXPECTED_BLADDER = {
    "mean_pair_availability_contribution": 0.42125,
    "mean_state_transition_contribution": 0.0125,
    "mean_cutoff_boundary_membership_contribution": 0.085625,
    "mean_score_order_contribution": 0.446875,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def record(
    target: str,
    status: str,
    score: float | None,
    selected: bool,
) -> dict[str, object]:
    return {
        "candidate_id": "CCTX_TEST",
        "context_name": "synthetic exact context",
        "diseaseId": "TEST_1",
        "targetId": target,
        "realization_id": "R01",
        "operator_code": "00000",
        "operator_status": status,
        "operator_score": score,
        "selected_top50": selected,
    }


def test_row_order_invariance() -> None:
    historical_records = [
        record("A", "SCORED", 10.0, True),
        record("R", "SCORED", 9.0, True),
        record("X", "SCORED", 8.0, True),
        record("T", "SCORED", 7.0, True),
        record("B", "SCORED", 6.0, False),
        record("C", "SCORED", 6.0, False),
        record("S", "SCORED", 5.0, False),
        record("Y", "INELIGIBLE_T0_PRIMARY_HARD_EVIDENCE", None, False),
    ]
    current_records = [
        record("A", "SCORED", 10.0, True),
        record("Y", "SCORED", 9.0, True),
        record("S", "SCORED", 8.0, True),
        record("B", "SCORED", 7.0, True),
        record("C", "SCORED", 7.0, False),
        record("T", "SCORED", 7.0, False),
        record("R", "SCORED", 6.0, False),
    ]

    baseline_h = MODULE.build_release_from_records(historical_records, budget=4)
    baseline_c = MODULE.build_release_from_records(current_records, budget=4)
    baseline = MODULE.build_temporal_tables(
        baseline_h, baseline_c, budget=4, expected_specifications=1
    )
    cell = baseline[0][0]
    expected = {
        "pair_availability_contribution": 1 / 8,
        "state_transition_contribution": 1 / 8,
        "cutoff_boundary_membership_contribution": 2 / 8,
        "score_order_contribution": 2 / 8,
        "substitution_deterministic": 6 / 8,
    }
    for key, value in expected.items():
        if abs(float(cell[key]) - value) > 1e-12:
            raise AssertionError(f"Synthetic ordered layer mismatch for {key}: {cell[key]} != {value}")

    for seed in range(20):
        shuffled_h = historical_records.copy()
        shuffled_c = current_records.copy()
        random.Random(seed).shuffle(shuffled_h)
        random.Random(seed + 1000).shuffle(shuffled_c)
        observed = MODULE.build_temporal_tables(
            MODULE.build_release_from_records(shuffled_h, budget=4),
            MODULE.build_release_from_records(shuffled_c, budget=4),
            budget=4,
            expected_specifications=1,
        )
        if observed != baseline:
            raise AssertionError(f"Input-row order changed decomposition at seed {seed}")


def test_full_rebuild(historical_matrix: Path, current_matrix: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="trace_dt_v12_temporal_") as temporary:
        output_dir = Path(temporary) / "outputs"
        receipt = MODULE.run(historical_matrix, current_matrix, output_dir, budget=50)
        if receipt["decision"] != "PASS":
            raise AssertionError(receipt)
        cell_path = output_dir / "R17_TEMPORAL_CELL_DECOMPOSITION_160.tsv"
        context_path = output_dir / "R17_TEMPORAL_CONTEXT_DECOMPOSITION.tsv"
        if sha256(cell_path) != EXPECTED_CELL_SHA256:
            raise AssertionError("160-row table does not match the corrected semantic serialization")
        if sha256(context_path) != EXPECTED_CONTEXT_SHA256:
            raise AssertionError("Five-context table does not match the corrected semantic serialization")

        cell_rows = read_tsv(cell_path)
        context_rows = read_tsv(context_path)
        if len(cell_rows) != 160 or len(context_rows) != 5:
            raise AssertionError(f"Unexpected output dimensions: {len(cell_rows)}, {len(context_rows)}")
        contribution_columns = (
            "pair_availability_contribution",
            "state_transition_contribution",
            "cutoff_boundary_membership_contribution",
            "score_order_contribution",
        )
        for row in cell_rows:
            values = [float(row[column]) for column in contribution_columns]
            if any(value < 0 for value in values):
                raise AssertionError(f"Negative contribution: {row}")
            if abs(sum(values) - float(row["substitution_deterministic"])) > 1e-12:
                raise AssertionError(f"Component sum failure: {row}")

        bladder = next(row for row in context_rows if row["candidate_id"] == "CCTX001")
        for column, expected in EXPECTED_BLADDER.items():
            if abs(float(bladder[column]) - expected) > 1e-12:
                raise AssertionError(f"Bladder mean mismatch for {column}: {bladder[column]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical-matrix", required=True, type=Path)
    parser.add_argument("--current-matrix", required=True, type=Path)
    args = parser.parse_args()
    test_row_order_invariance()
    test_full_rebuild(args.historical_matrix, args.current_matrix)
    print("PASS: ordered synthetic classification")
    print("PASS: input-row order invariance (20 permutations)")
    print("PASS: nonnegative components and exact F sum (160/160)")
    print("PASS: bladder means 0.42125/0.0125/0.085625/0.446875")
    print("PASS: numerical values preserved under corrected semantic field labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
