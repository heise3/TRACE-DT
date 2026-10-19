#!/usr/bin/env python
"""TRACE-DT R17 tie-aware primary reconstruction.

This script treats each top-B result as a set-valued decision:
G contains scores strictly above the cutoff and r remaining seats are selected
from the exact cutoff-tie block T. It reports deterministic, exact-bound, and
uniform-tie expected identity substitution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

import numpy as np
import pandas as pd


BUDGET = 50
EXPECTED_R16_GLOBAL_F = 0.4385834502103733


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(float).ne(0)
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
    )


@dataclass(frozen=True)
class Cell:
    context_id: str
    context_name: str
    disease_id: str
    realization_id: str
    operator_code: str
    guaranteed: frozenset[str]
    tied: frozenset[str]
    deterministic: frozenset[str]
    remaining_seats: int
    cutoff_score: float
    scored_count: int

    @property
    def tie_probability(self) -> float:
        return self.remaining_seats / len(self.tied)

    @property
    def possible(self) -> frozenset[str]:
        return self.guaranteed | self.tied


def build_cell(
    frame: pd.DataFrame,
    *,
    context_id: str,
    context_name: str,
    disease_id: str,
    realization_id: str,
    operator_code: str,
    score_col: str,
    selected_col: str | None,
    target_col: str = "targetId",
) -> Cell:
    scored = frame.loc[np.isfinite(frame[score_col].to_numpy(dtype=float))].copy()
    if len(scored) < BUDGET:
        raise ValueError(
            f"{context_id}/{realization_id}: only {len(scored)} finite scores for B={BUDGET}"
        )
    if selected_col is None:
        scored = scored.sort_values(
            [score_col, target_col],
            ascending=[False, True],
            kind="mergesort",
        )
        deterministic = frozenset(scored.iloc[:BUDGET][target_col].astype(str))
    else:
        deterministic = frozenset(
            scored.loc[as_bool(scored[selected_col]), target_col].astype(str)
        )
    if len(deterministic) != BUDGET:
        raise ValueError(
            f"{context_id}/{realization_id}: deterministic size={len(deterministic)}"
        )
    cutoff = float(
        scored.sort_values(
            [score_col, target_col],
            ascending=[False, True],
            kind="mergesort",
        ).iloc[BUDGET - 1][score_col]
    )
    guaranteed = frozenset(
        scored.loc[scored[score_col] > cutoff, target_col].astype(str)
    )
    tied = frozenset(
        scored.loc[scored[score_col] == cutoff, target_col].astype(str)
    )
    remaining = BUDGET - len(guaranteed)
    if remaining < 0 or remaining > len(tied):
        raise ValueError(
            f"{context_id}/{realization_id}: invalid tie contract "
            f"|G|={len(guaranteed)}, |T|={len(tied)}, r={remaining}"
        )
    if not guaranteed.issubset(deterministic):
        raise ValueError(f"{context_id}/{realization_id}: deterministic omits G")
    if not deterministic.issubset(guaranteed | tied):
        raise ValueError(
            f"{context_id}/{realization_id}: deterministic contains score below cutoff"
        )
    return Cell(
        context_id=context_id,
        context_name=context_name,
        disease_id=disease_id,
        realization_id=realization_id,
        operator_code=str(operator_code).zfill(5),
        guaranteed=guaranteed,
        tied=tied,
        deterministic=deterministic,
        remaining_seats=remaining,
        cutoff_score=cutoff,
        scored_count=len(scored),
    )


def exact_intersection_bounds(a: Cell, b: Cell) -> Tuple[int, int]:
    """Exact min/max intersection across all legal choices inside T_a and T_b."""
    ga, gb, ta, tb = a.guaranteed, b.guaranteed, a.tied, b.tied
    base = len(ga & gb)
    c = len(ga & tb)
    d = len(ta & gb)
    h = len(ta & tb)
    a_other = len(ta - gb - tb)
    b_other = len(tb - ga - ta)

    best_min = math.inf
    best_max = -math.inf
    for h_a in range(min(h, a.remaining_seats) + 1):
        rem_a = a.remaining_seats - h_a
        low_d = max(0, rem_a - a_other)
        high_d = min(d, rem_a)
        if low_d > high_d:
            continue
        for h_b in range(min(h, b.remaining_seats) + 1):
            rem_b = b.remaining_seats - h_b
            low_c = max(0, rem_b - b_other)
            high_c = min(c, rem_b)
            if low_c > high_c:
                continue
            min_h_overlap = max(0, h_a + h_b - h)
            max_h_overlap = min(h_a, h_b)
            best_min = min(best_min, low_d + low_c + min_h_overlap)
            best_max = max(best_max, high_d + high_c + max_h_overlap)
    if not math.isfinite(best_min) or not math.isfinite(best_max):
        raise RuntimeError(
            f"No feasible tie assignment for {a.context_id} "
            f"{a.realization_id} vs {b.realization_id}"
        )
    return base + int(best_min), base + int(best_max)


def expected_intersection(a: Cell, b: Cell) -> float:
    pa = a.tie_probability
    pb = b.tie_probability
    return (
        len(a.guaranteed & b.guaranteed)
        + pa * len(a.tied & b.guaranteed)
        + pb * len(a.guaranteed & b.tied)
        + pa * pb * len(a.tied & b.tied)
    )


def bit_distance(code_a: str, code_b: str, indexes: Sequence[int]) -> int:
    return sum(code_a[i] != code_b[i] for i in indexes)


def pair_record(a: Cell, b: Cell, comparison_family: str) -> dict:
    min_i, max_i = exact_intersection_bounds(a, b)
    expected_i = expected_intersection(a, b)
    deterministic_i = len(a.deterministic & b.deterministic)
    code_a = a.operator_code
    code_b = b.operator_code
    full_distance = (
        bit_distance(code_a, code_b, range(5))
        if code_a not in {"B01"} and code_b not in {"B01"}
        else np.nan
    )
    active_distance = (
        bit_distance(code_a, code_b, range(1, 5))
        if code_a not in {"B01"} and code_b not in {"B01"}
        else np.nan
    )
    differing = (
        [f"O{i + 1}" for i in range(5) if code_a[i] != code_b[i]]
        if code_a not in {"B01"} and code_b not in {"B01"}
        else []
    )
    return {
        "comparison_family": comparison_family,
        "candidate_id": a.context_id,
        "context_name": a.context_name,
        "diseaseId": a.disease_id,
        "realization_a": a.realization_id,
        "operator_code_a": code_a,
        "realization_b": b.realization_id,
        "operator_code_b": code_b,
        "hamming_distance_5": full_distance,
        "active_distance_O2_O5": active_distance,
        "direct_toggle_factor": differing[0] if len(differing) == 1 else "",
        "O2_stratum": (
            int(code_a[1])
            if len(differing) == 1
            and differing[0] in {"O3", "O4", "O5"}
            and code_a[1] == code_b[1]
            else np.nan
        ),
        "intersection_deterministic": deterministic_i,
        "intersection_expected_uniform_tie": expected_i,
        "intersection_minimum": min_i,
        "intersection_maximum": max_i,
        "substitution_deterministic": 1 - deterministic_i / BUDGET,
        "substitution_expected_uniform_tie": 1 - expected_i / BUDGET,
        "substitution_lower_bound": 1 - max_i / BUDGET,
        "substitution_upper_bound": 1 - min_i / BUDGET,
        "a_guaranteed": len(a.guaranteed),
        "a_tie_block": len(a.tied),
        "a_remaining_seats": a.remaining_seats,
        "b_guaranteed": len(b.guaranteed),
        "b_tie_block": len(b.tied),
        "b_remaining_seats": b.remaining_seats,
    }


def output_hashes(paths: Iterable[Path]) -> Mapping[str, str]:
    return {path.name: sha256_file(path) for path in paths}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument(
        "--append-matrix",
        action="append",
        default=[],
        type=Path,
        help="Optional additional context matrix; may be supplied more than once.",
    )
    parser.add_argument("--baseline-metrics", required=True, type=Path)
    parser.add_argument(
        "--append-baseline-metrics",
        action="append",
        default=[],
        type=Path,
        help="Optional additional context baseline; may be supplied more than once.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--expected-deterministic-global",
        default=str(EXPECTED_R16_GLOBAL_F),
        help="Expected deterministic global F, or 'none' for a counterfactual run.",
    )
    parser.add_argument(
        "--expected-contexts",
        type=int,
        default=23,
        help="Expected number of context-specific 32-specification blocks.",
    )
    parser.add_argument("--gate-label", default="R17_TIE")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    matrix_cols = [
        "candidate_id",
        "context_name",
        "diseaseId",
        "targetId",
        "realization_id",
        "operator_code",
        "operator_status",
        "operator_score",
        "selected_top50",
    ]
    matrix_paths = [args.matrix, *args.append_matrix]
    matrix = pd.concat(
        [pd.read_parquet(path, columns=matrix_cols) for path in matrix_paths],
        ignore_index=True,
    )
    analysis_units = matrix[
        ["candidate_id", "diseaseId", "targetId"]
    ].drop_duplicates()
    expected_matrix_rows = len(analysis_units) * 32
    if len(matrix) != expected_matrix_rows:
        raise ValueError(
            f"Expected {expected_matrix_rows:,} matrix rows from "
            f"{len(analysis_units):,} analysis units x 32, observed {len(matrix):,}"
        )
    observed_contexts = int(matrix["candidate_id"].nunique())
    if observed_contexts != args.expected_contexts:
        raise ValueError(
            f"Expected {args.expected_contexts} contexts, observed {observed_contexts}"
        )
    matrix["operator_code"] = (
        matrix["operator_code"].astype("string").str.zfill(5)
    )
    matrix["selected_top50"] = as_bool(matrix["selected_top50"])

    cells: Dict[Tuple[str, str], Cell] = {}
    cell_rows: List[dict] = []
    target_parts: List[pd.DataFrame] = []
    for (context_id, realization_id), frame in matrix.groupby(
        ["candidate_id", "realization_id"], sort=True, observed=True
    ):
        scored = frame.loc[
            frame["operator_status"].astype(str).str.upper() == "SCORED"
        ].copy()
        cell = build_cell(
            scored,
            context_id=str(context_id),
            context_name=str(frame["context_name"].iloc[0]),
            disease_id=str(frame["diseaseId"].iloc[0]),
            realization_id=str(realization_id),
            operator_code=str(frame["operator_code"].iloc[0]),
            score_col="operator_score",
            selected_col="selected_top50",
        )
        cells[(cell.context_id, cell.realization_id)] = cell
        tie_probability = cell.tie_probability
        cell_rows.append(
            {
                "candidate_id": cell.context_id,
                "context_name": cell.context_name,
                "diseaseId": cell.disease_id,
                "realization_id": cell.realization_id,
                "operator_code": cell.operator_code,
                "scored_count": cell.scored_count,
                "cutoff_score": cell.cutoff_score,
                "guaranteed_members": len(cell.guaranteed),
                "cutoff_tie_block_size": len(cell.tied),
                "remaining_tie_seats": cell.remaining_seats,
                "tie_probability_per_member": tie_probability,
                "possible_members": len(cell.possible),
                "exact_cutoff_tie": len(cell.tied) > cell.remaining_seats,
            }
        )
        piece = frame[
            ["candidate_id", "context_name", "diseaseId", "targetId"]
        ].copy()
        targets = piece["targetId"].astype(str)
        piece["evaluable"] = (
            frame["operator_status"].astype(str).str.upper().eq("SCORED").to_numpy()
        )
        piece["selected_deterministic"] = frame["selected_top50"].to_numpy(dtype=bool)
        piece["selected_guaranteed"] = targets.isin(cell.guaranteed)
        piece["selected_possible"] = targets.isin(cell.possible)
        piece["selected_expected"] = np.where(
            targets.isin(cell.guaranteed),
            1.0,
            np.where(targets.isin(cell.tied), tie_probability, 0.0),
        )
        piece["cutoff_tie_member"] = targets.isin(cell.tied)
        target_parts.append(piece)

    expected_cells = args.expected_contexts * 32
    if len(cells) != expected_cells:
        raise ValueError(f"Expected {expected_cells} cells, observed {len(cells)}")
    cell_table = pd.DataFrame(cell_rows).sort_values(
        ["candidate_id", "realization_id"]
    )

    target_long = pd.concat(target_parts, ignore_index=True)
    target_table = (
        target_long.groupby(
            ["candidate_id", "context_name", "diseaseId", "targetId"],
            sort=True,
            observed=True,
            as_index=False,
        )
        .agg(
            evaluable_specifications=("evaluable", "sum"),
            deterministic_selection_count=("selected_deterministic", "sum"),
            guaranteed_selection_count=("selected_guaranteed", "sum"),
            possible_selection_count=("selected_possible", "sum"),
            expected_selection_count_uniform_tie=("selected_expected", "sum"),
            cutoff_tie_membership_count=("cutoff_tie_member", "sum"),
        )
    )
    del target_long, target_parts

    pair_rows: List[dict] = []
    by_context: Dict[str, List[Cell]] = {}
    for cell in cells.values():
        by_context.setdefault(cell.context_id, []).append(cell)
    for context_id, context_cells in sorted(by_context.items()):
        context_cells = sorted(context_cells, key=lambda x: x.realization_id)
        if len(context_cells) != 32:
            raise ValueError(f"{context_id}: expected 32 cells")
        for a, b in combinations(context_cells, 2):
            pair_rows.append(pair_record(a, b, "within_32_specifications"))
    pair_table = pd.DataFrame(pair_rows)
    expected_pair_rows = args.expected_contexts * 496
    if len(pair_table) != expected_pair_rows:
        raise ValueError(
            f"Expected {expected_pair_rows:,} pairs, observed {len(pair_table):,}"
        )

    baseline_paths = [args.baseline_metrics, *args.append_baseline_metrics]
    baseline = pd.concat(
        [pd.read_parquet(path) for path in baseline_paths],
        ignore_index=True,
    )
    baseline["t0_hard_negative"] = as_bool(baseline["t0_hard_negative"])
    baseline["common_baseline_abstention"] = as_bool(
        baseline["common_baseline_abstention"]
    )
    b01_cells: Dict[str, Cell] = {}
    for context_id, frame in baseline.groupby("candidate_id", sort=True):
        eligible = frame.loc[
            frame["t0_hard_negative"]
            & ~frame["common_baseline_abstention"]
            & np.isfinite(frame["associationScore"].to_numpy(dtype=float))
        ].copy()
        b01_cells[str(context_id)] = build_cell(
            eligible,
            context_id=str(context_id),
            context_name=str(frame["context_name"].iloc[0]),
            disease_id=str(frame["diseaseId"].iloc[0]),
            realization_id="B01",
            operator_code="B01",
            score_col="associationScore",
            selected_col=None,
        )
    if len(b01_cells) != args.expected_contexts:
        raise ValueError(
            f"Expected {args.expected_contexts} B01 cells, observed {len(b01_cells)}"
        )
    b01_rows: List[dict] = []
    for context_id, context_cells in sorted(by_context.items()):
        b01 = b01_cells[context_id]
        for cell in sorted(context_cells, key=lambda x: x.realization_id):
            b01_rows.append(pair_record(cell, b01, "specification_vs_B01"))
    b01_table = pd.DataFrame(b01_rows)
    if len(b01_table) != expected_cells:
        raise ValueError(
            f"Expected {expected_cells} B01 comparisons, observed {len(b01_table)}"
        )

    metric_cols = [
        "substitution_deterministic",
        "substitution_expected_uniform_tie",
        "substitution_lower_bound",
        "substitution_upper_bound",
    ]
    global_rows = []
    for family, frame in [
        ("all_496_pairs_per_context", pair_table),
        ("direct_toggle_distance_1", pair_table.loc[pair_table["hamming_distance_5"] == 1]),
        (
            "active_direct_toggle_O2_O5",
            pair_table.loc[pair_table["direct_toggle_factor"].isin(["O2", "O3", "O4", "O5"])],
        ),
        ("specification_vs_B01", b01_table),
    ]:
        row = {"summary_family": family, "n_rows": len(frame)}
        for col in metric_cols:
            row[f"mean_{col}"] = float(frame[col].mean())
            row[f"median_{col}"] = float(frame[col].median())
            row[f"minimum_{col}"] = float(frame[col].min())
            row[f"maximum_{col}"] = float(frame[col].max())
        global_rows.append(row)
    global_table = pd.DataFrame(global_rows)

    distance_table = (
        pair_table.groupby(
            ["hamming_distance_5", "active_distance_O2_O5"],
            as_index=False,
            observed=True,
        )[metric_cols]
        .agg(["count", "mean", "median", "min", "max"])
    )
    distance_table.columns = [
        "_".join(str(x) for x in col if str(x) != "").rstrip("_")
        for col in distance_table.columns.to_flat_index()
    ]

    direct_table = (
        pair_table.loc[pair_table["direct_toggle_factor"] != ""]
        .groupby("direct_toggle_factor", as_index=False, observed=True)[metric_cols]
        .agg(["count", "mean", "median", "min", "max"])
    )
    direct_table.columns = [
        "_".join(str(x) for x in col if str(x) != "").rstrip("_")
        for col in direct_table.columns.to_flat_index()
    ]

    conditioned = (
        pair_table.loc[
            pair_table["direct_toggle_factor"].isin(["O3", "O4", "O5"])
            & pair_table["O2_stratum"].notna()
        ]
        .groupby(
            ["direct_toggle_factor", "O2_stratum"],
            as_index=False,
            observed=True,
        )[metric_cols]
        .agg(["count", "mean", "median", "min", "max"])
    )
    conditioned.columns = [
        "_".join(str(x) for x in col if str(x) != "").rstrip("_")
        for col in conditioned.columns.to_flat_index()
    ]

    tolerance = 1e-12
    deterministic_global = float(pair_table["substitution_deterministic"].mean())
    bounds_ok = bool(
        (
            pair_table["substitution_lower_bound"]
            <= pair_table["substitution_deterministic"] + tolerance
        ).all()
        and (
            pair_table["substitution_deterministic"]
            <= pair_table["substitution_upper_bound"] + tolerance
        ).all()
        and (
            pair_table["substitution_lower_bound"]
            <= pair_table["substitution_expected_uniform_tie"] + tolerance
        ).all()
        and (
            pair_table["substitution_expected_uniform_tie"]
            <= pair_table["substitution_upper_bound"] + tolerance
        ).all()
    )
    expected_global = (
        None
        if str(args.expected_deterministic_global).strip().lower() == "none"
        else float(args.expected_deterministic_global)
    )
    reproduce_ok = (
        True
        if expected_global is None
        else abs(deterministic_global - expected_global) < 1e-12
    )

    lookup_expected = (
        conditioned.set_index(["direct_toggle_factor", "O2_stratum"])[
            "substitution_expected_uniform_tie_mean"
        ]
        .to_dict()
    )
    lookup_lower = (
        conditioned.set_index(["direct_toggle_factor", "O2_stratum"])[
            "substitution_lower_bound_mean"
        ]
        .to_dict()
    )
    o4_ds = float(lookup_expected.get(("O4", 0.0), np.nan))
    o4_lineage = float(lookup_expected.get(("O4", 1.0), np.nan))
    o5_ds = float(lookup_expected.get(("O5", 0.0), np.nan))
    o5_lineage = float(lookup_expected.get(("O5", 1.0), np.nan))
    o4_ds_lower = float(lookup_lower.get(("O4", 0.0), np.nan))
    o4_lineage_lower = float(lookup_lower.get(("O4", 1.0), np.nan))
    o5_ds_lower = float(lookup_lower.get(("O5", 0.0), np.nan))
    o5_lineage_lower = float(lookup_lower.get(("O5", 1.0), np.nan))
    structure_ok = bool(
        np.isfinite(
            [o4_ds_lower, o4_lineage_lower, o5_ds_lower, o5_lineage_lower]
        ).all()
        and o4_ds_lower > o4_lineage_lower
        and o5_lineage_lower > o5_ds_lower
        and o4_ds_lower >= 0.10
        and o5_lineage_lower >= 0.10
    )
    gate_state = "CONTINUE" if bounds_ok and reproduce_ok and structure_ok else "PIVOT_SCOPE"
    gate_table = pd.DataFrame(
        [
            {
                "gate": args.gate_label,
                "status": gate_state,
                "cells": len(cell_table),
                "within_context_pairs": len(pair_table),
                "b01_comparisons": len(b01_table),
                "deterministic_global_F": deterministic_global,
                "expected_deterministic_global_F_for_parity": expected_global,
                "expected_uniform_tie_global_F": float(
                    pair_table["substitution_expected_uniform_tie"].mean()
                ),
                "mean_lower_bound_global_F": float(
                    pair_table["substitution_lower_bound"].mean()
                ),
                "mean_upper_bound_global_F": float(
                    pair_table["substitution_upper_bound"].mean()
                ),
                "reproduces_R16": reproduce_ok,
                "all_estimates_within_exact_bounds": bounds_ok,
                "O4_expected_O2_datasource": o4_ds,
                "O4_expected_O2_lineage": o4_lineage,
                "O5_expected_O2_datasource": o5_ds,
                "O5_expected_O2_lineage": o5_lineage,
                "O4_unavoidable_lower_bound_O2_datasource": o4_ds_lower,
                "O4_unavoidable_lower_bound_O2_lineage": o4_lineage_lower,
                "O5_unavoidable_lower_bound_O2_datasource": o5_ds_lower,
                "O5_unavoidable_lower_bound_O2_lineage": o5_lineage_lower,
                "O2_conditioned_O4_O5_structure_survives_exact_lower_bound": structure_ok,
            }
        ]
    )

    outputs = {
        "R17_TIE_CELL_CONTRACT.tsv": cell_table,
        "R17_TIE_AWARE_PAIRWISE_11408.tsv": pair_table,
        "R17_TIE_AWARE_B01_COMPARISONS.tsv": b01_table,
        "R17_TIE_AWARE_GLOBAL_SUMMARY.tsv": global_table,
        "R17_TIE_AWARE_DISTANCE_SUMMARY.tsv": distance_table,
        "R17_TIE_AWARE_DIRECT_TOGGLE_SUMMARY.tsv": direct_table,
        "R17_TIE_AWARE_O2_CONDITIONED_SUMMARY.tsv": conditioned,
        "R17_TIE_AWARE_GATE.tsv": gate_table,
    }
    written: List[Path] = []
    for name, frame in outputs.items():
        path = args.output_dir / name
        frame.to_csv(path, sep="\t", index=False, float_format="%.12g")
        written.append(path)
    target_parquet = args.output_dir / "R17_TIE_AWARE_TARGET_SELECTION.parquet"
    target_table.to_parquet(target_parquet, index=False, compression="zstd")
    written.append(target_parquet)
    target_tsv = args.output_dir / "R17_TIE_AWARE_TARGET_SELECTION.tsv.gz"
    target_table.to_csv(
        target_tsv,
        sep="\t",
        index=False,
        compression={"method": "gzip", "compresslevel": 6},
        float_format="%.12g",
    )
    written.append(target_tsv)

    receipt = {
        "analysis": "TRACE-DT R17 tie-aware primary reconstruction",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "gate": gate_state,
        "gate_label": args.gate_label,
        "input_matrix": str(args.matrix),
        "input_matrix_sha256": sha256_file(args.matrix),
        "input_baseline_metrics": str(args.baseline_metrics),
        "input_baseline_metrics_sha256": sha256_file(args.baseline_metrics),
        "rows": {
            "matrix": int(len(matrix)),
            "cells": int(len(cell_table)),
            "within_context_pairs": int(len(pair_table)),
            "b01_comparisons": int(len(b01_table)),
            "target_context_pairs": int(len(target_table)),
        },
        "output_sha256": output_hashes(written),
    }
    receipt_path = args.output_dir / "R17_TIE_AWARE_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if gate_state == "CONTINUE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
