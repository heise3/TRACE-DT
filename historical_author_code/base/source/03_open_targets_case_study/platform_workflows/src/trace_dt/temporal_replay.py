"""Exact-disease-ID temporal comparison for two reconstructed TRACE-DT matrices."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import polars as pl


def _selected(path: Path) -> tuple[
    dict[tuple[str, str, str], set[str]], dict[tuple[str, str], str]
]:
    frame = (
        pl.scan_parquet(path)
        .filter(pl.col("selected_top50"))
        .select(
            "candidate_id",
            "context_name",
            "diseaseId",
            "targetId",
            "realization_id",
            "operator_code",
        )
        .collect()
    )
    selected: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    codes: dict[tuple[str, str], str] = {}
    for row in frame.iter_rows(named=True):
        key = (
            str(row["candidate_id"]),
            str(row["diseaseId"]),
            str(row["realization_id"]),
        )
        selected[key].add(str(row["targetId"]))
        codes[(str(row["realization_id"]), str(row["operator_code"]))] = str(
            row["operator_code"]
        )
    return dict(selected), codes


def _write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError("TEMPORAL_REPLAY_FAIL_NO_EXACT_SHARED_CELLS")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def compare_exact(
    historical_matrix: Path,
    current_matrix: Path,
    output_dir: Path,
) -> dict[str, object]:
    historical, historical_codes = _selected(historical_matrix)
    current, current_codes = _selected(current_matrix)
    if historical_codes != current_codes:
        raise RuntimeError("TEMPORAL_REPLAY_FAIL_SPECIFICATION_CONTRACT_MISMATCH")

    shared_keys = sorted(set(historical) & set(current))
    rows: list[dict[str, object]] = []
    for candidate_id, disease_id, realization_id in shared_keys:
        before = historical[(candidate_id, disease_id, realization_id)]
        after = current[(candidate_id, disease_id, realization_id)]
        evaluable = len(before) == 50 and len(after) == 50
        intersection = len(before & after)
        substitution = 1.0 - intersection / 50.0 if evaluable else math.nan
        operator_code = next(
            code
            for (rid, code), _ in historical_codes.items()
            if rid == realization_id
        )
        rows.append(
            {
                "candidate_id": candidate_id,
                "diseaseId": disease_id,
                "realization_id": realization_id,
                "operator_code": operator_code,
                "selected_historical": len(before),
                "selected_current": len(after),
                "intersection": intersection,
                "temporal_identity_substitution": substitution,
                "evaluable_equal_b50": evaluable,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_tsv(output_dir / "TEMPORAL_EXACT_SAME_SPEC_CELLS.tsv", rows)
    finite = [
        float(row["temporal_identity_substitution"])
        for row in rows
        if math.isfinite(float(row["temporal_identity_substitution"]))
    ]
    shared_contexts = sorted({(row["candidate_id"], row["diseaseId"]) for row in rows})
    receipt: dict[str, object] = {
        "decision": (
            "PASS_EXACT_ID_TEMPORAL_REPLAY"
            if finite and len(rows) == len(shared_contexts) * 32
            else "FAIL_EXACT_ID_TEMPORAL_REPLAY"
        ),
        "shared_exact_contexts": len(shared_contexts),
        "shared_context_specification_cells": len(rows),
        "evaluable_equal_b50_cells": len(finite),
        "mean_temporal_identity_substitution": (
            sum(finite) / len(finite) if finite else None
        ),
        "minimum_temporal_identity_substitution": min(finite) if finite else None,
        "maximum_temporal_identity_substitution": max(finite) if finite else None,
        "join_contract": (
            "exact candidate_id + exact diseaseId + realization_id; "
            "no ontology substitution or cross-reference bridge"
        ),
        "t1_access": "NOT_ACCESSED_NOT_REQUIRED",
    }
    (output_dir / "TEMPORAL_EXACT_REPLAY_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if receipt["decision"] != "PASS_EXACT_ID_TEMPORAL_REPLAY":
        raise RuntimeError(str(receipt["decision"]))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two reconstructed matrices under exact shared disease IDs "
            "and identical realization IDs."
        )
    )
    parser.add_argument("--historical-matrix", required=True, type=Path)
    parser.add_argument("--current-matrix", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    receipt = compare_exact(
        args.historical_matrix,
        args.current_matrix,
        args.output_dir,
    )
    print(receipt["decision"])
    print(f"shared_exact_contexts={receipt['shared_exact_contexts']}")
    print(
        "shared_context_specification_cells="
        f"{receipt['shared_context_specification_cells']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

