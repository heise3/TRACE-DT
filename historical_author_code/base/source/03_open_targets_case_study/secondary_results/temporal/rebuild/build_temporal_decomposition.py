#!/usr/bin/env python3
"""Rebuild the ordered 26.03-to-26.06 temporal decomposition.

The only scientific inputs are the two supplied derived
``legal_unit_operator_status_matrix.parquet`` files.  Previously frozen
decomposition tables are never read.  For each exact disease-ID context and
specification, the deterministic top-B symmetric difference is partitioned in
the declared order:

1. target--context pair availability;
2. eligibility/provenance state;
3. membership in either release's exact cutoff-score boundary block;
4. residual score order.

The four classes are disjoint and exhaustive by construction.  They are an
ordered descriptive bookkeeping estimand, not a causal or permutation-
invariant attribution.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import polars as pl


BUDGET = 50
RELEASE_HISTORICAL = "26.03"
RELEASE_CURRENT = "26.06"
SCORED = "SCORED"
ABSENT = "ABSENT_PAIR"

# Display metadata only. These exact Open Targets names are frozen for the five
# cross-release exact-ID contexts. They do not enter any score, state, list, or
# decomposition calculation. Synthetic/unit-test contexts fall back to the
# supplied qualification label.
OPEN_TARGETS_DISEASE_NAME_BY_ID = {
    "MONDO_0001187": "urinary bladder cancer",
    "MONDO_0005499": "brain glioma",
    "MONDO_0002974": "cervical cancer",
    "MONDO_0002229": "ovarian epithelial tumor",
    "MONDO_0002108": "thyroid cancer",
}

REQUIRED_COLUMNS = (
    "candidate_id",
    "context_name",
    "diseaseId",
    "targetId",
    "realization_id",
    "operator_code",
    "operator_status",
    "operator_score",
    "selected_top50",
)

CELL_COLUMNS = (
    "candidate_id",
    "context_name",
    "qualification_context_name",
    "diseaseId",
    "realization_id",
    "operator_code",
    "pairs_26_03",
    "pairs_26_06",
    "pair_additions",
    "pair_removals",
    "shared_scored_pairs",
    "substitution_deterministic",
    "substitution_expected_uniform_tie",
    "substitution_lower_bound",
    "substitution_upper_bound",
    "shared_scored_universe_substitution_deterministic",
    "pair_availability_contribution",
    "state_transition_contribution",
    "cutoff_boundary_membership_contribution",
    "score_order_contribution",
    "contribution_sum",
)

CONTEXT_COLUMNS = (
    "candidate_id",
    "context_name",
    "qualification_context_name",
    "diseaseId",
    "specifications",
    "mean_substitution_deterministic",
    "mean_substitution_expected_uniform_tie",
    "mean_substitution_lower_bound",
    "mean_substitution_upper_bound",
    "mean_shared_scored_universe_substitution",
    "mean_pair_availability_contribution",
    "mean_state_transition_contribution",
    "mean_cutoff_boundary_membership_contribution",
    "mean_score_order_contribution",
)

MISMATCH_COLUMNS = (
    "candidate_id",
    "context_name",
    "qualification_context_name",
    "diseaseId",
    "realization_id",
    "operator_code",
    "targetId",
    "selected_release",
    "decomposition_layer",
    "present_26_03",
    "present_26_06",
    "status_26_03",
    "status_26_06",
    "cutoff_boundary_member_26_03",
    "cutoff_boundary_member_26_06",
)


@dataclass(frozen=True)
class Cell:
    candidate_id: str
    context_name: str
    disease_id: str
    realization_id: str
    operator_code: str
    present: frozenset[str]
    status: Mapping[str, str]
    scores: Mapping[str, float]
    deterministic: frozenset[str]
    strict_above: frozenset[str]
    tied: frozenset[str]
    remaining_seats: int
    cutoff_score: float

    @property
    def scored(self) -> frozenset[str]:
        return frozenset(self.scores)

    @property
    def tie_probability(self) -> float:
        return self.remaining_seats / len(self.tied)


@dataclass(frozen=True)
class ReleaseData:
    cells: Mapping[tuple[str, str, str], Cell]
    contexts: Mapping[tuple[str, str], str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _format_float(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError(f"Non-finite output value: {value!r}")
    rounded = round(float(value), 12)
    if rounded == 0:
        rounded = 0.0
    return format(rounded, ".12g")


def _normalise_output_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        key: _format_float(value) if isinstance(value, float) else value
        for key, value in row.items()
    }


def _write_tsv(path: Path, rows: Sequence[Mapping[str, object]], columns: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        # The frozen R17 tables use CRLF.  Preserve that serialization so an
        # independently rebuilt scientific table can also be checked bytewise.
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(_normalise_output_row(row))


def _write_gzip_tsv(
    path: Path, rows: Sequence[Mapping[str, object]], columns: Sequence[str]
) -> None:
    # mtime=0 makes the compressed audit ledger byte-reproducible.
    with path.open("wb") as raw_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=list(columns), delimiter="\t", lineterminator="\r\n"
                )
                writer.writeheader()
                for row in rows:
                    writer.writerow(_normalise_output_row(row))


def _cell_from_records(records: Sequence[Mapping[str, object]], budget: int) -> Cell:
    if not records:
        raise ValueError("Cannot build an empty context--specification cell")
    first = records[0]
    identity = (
        str(first["candidate_id"]),
        str(first["context_name"]),
        str(first["diseaseId"]),
        str(first["realization_id"]),
        str(first["operator_code"]),
    )
    status: dict[str, str] = {}
    scores: dict[str, float] = {}
    submitted_selected: set[str] = set()
    for record in records:
        current_identity = (
            str(record["candidate_id"]),
            str(record["context_name"]),
            str(record["diseaseId"]),
            str(record["realization_id"]),
            str(record["operator_code"]),
        )
        if current_identity != identity:
            raise ValueError(f"Mixed cell records: {identity!r} versus {current_identity!r}")
        target = str(record["targetId"])
        if target in status:
            raise ValueError(f"Duplicate target in cell {identity!r}: {target}")
        state = str(record["operator_status"])
        status[target] = state
        raw_score = record["operator_score"]
        if state == SCORED:
            if raw_score is None:
                raise ValueError(f"SCORED target lacks score: {identity!r}/{target}")
            score = float(raw_score)
            if not math.isfinite(score):
                raise ValueError(f"SCORED target has non-finite score: {identity!r}/{target}")
            scores[target] = score
        if bool(record["selected_top50"]):
            submitted_selected.add(target)

    if len(scores) < budget:
        raise ValueError(f"{identity!r}: {len(scores)} scored candidates < B={budget}")
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    cutoff = ordered[budget - 1][1]
    strict_above = frozenset(target for target, score in ordered if score > cutoff)
    tied = frozenset(target for target, score in ordered if score == cutoff)
    remaining = budget - len(strict_above)
    deterministic = strict_above | frozenset(sorted(tied)[:remaining])
    if submitted_selected != deterministic:
        missing = sorted(deterministic - submitted_selected)[:3]
        extra = sorted(submitted_selected - deterministic)[:3]
        raise ValueError(
            f"Frozen deterministic membership mismatch for {identity!r}: "
            f"missing={missing}, extra={extra}"
        )
    if not 0 <= remaining <= len(tied):
        raise RuntimeError(f"Invalid cutoff-tie contract for {identity!r}")
    return Cell(
        candidate_id=identity[0],
        context_name=identity[1],
        disease_id=identity[2],
        realization_id=identity[3],
        operator_code=identity[4],
        present=frozenset(status),
        status=status,
        scores=scores,
        deterministic=deterministic,
        strict_above=strict_above,
        tied=tied,
        remaining_seats=remaining,
        cutoff_score=cutoff,
    )


def build_release_from_records(
    records: Iterable[Mapping[str, object]], budget: int = BUDGET
) -> ReleaseData:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    contexts: dict[tuple[str, str], str] = {}
    for record in records:
        key = (
            str(record["candidate_id"]),
            str(record["diseaseId"]),
            str(record["realization_id"]),
        )
        grouped[key].append(record)
        context_key = (key[0], key[1])
        name = str(record["context_name"])
        previous = contexts.setdefault(context_key, name)
        if previous != name:
            raise ValueError(f"Context-name mismatch for {context_key!r}: {previous!r} vs {name!r}")
    if not grouped:
        raise ValueError("No cells found in release input")
    cells = {key: _cell_from_records(grouped[key], budget) for key in sorted(grouped)}
    return ReleaseData(cells=cells, contexts=contexts)


def load_release(
    path: Path,
    budget: int = BUDGET,
    candidate_ids: frozenset[str] | None = None,
) -> ReleaseData:
    if not path.is_file():
        raise FileNotFoundError(path)
    scan = pl.scan_parquet(path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(scan.collect_schema().names()))
    if missing:
        raise ValueError(f"Missing matrix columns in {path}: {missing}")
    if candidate_ids is not None:
        scan = scan.filter(pl.col("candidate_id").is_in(sorted(candidate_ids)))
    frame = scan.select(REQUIRED_COLUMNS).collect()
    return build_release_from_records(frame.iter_rows(named=True), budget=budget)


def exact_intersection_bounds(a: Cell, b: Cell) -> tuple[int, int]:
    """Return the sharp minimum and maximum legal top-B intersection."""
    ga, gb, ta, tb = a.strict_above, b.strict_above, a.tied, b.tied
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
        raise RuntimeError(f"No legal tie allocation for {a.candidate_id}/{a.realization_id}")
    return base + int(best_min), base + int(best_max)


def expected_intersection(a: Cell, b: Cell) -> float:
    pa, pb = a.tie_probability, b.tie_probability
    return (
        len(a.strict_above & b.strict_above)
        + pa * len(a.tied & b.strict_above)
        + pb * len(a.strict_above & b.tied)
        + pa * pb * len(a.tied & b.tied)
    )


def _top_from_scores(scores: Mapping[str, float], budget: int) -> frozenset[str]:
    if len(scores) < budget:
        raise ValueError(f"Shared scored universe has {len(scores)} candidates < B={budget}")
    return frozenset(
        target for target, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:budget]
    )


def _classify_mismatch(
    target: str,
    selected_release: str,
    historical: Cell,
    current: Cell,
) -> str:
    other = current if selected_release == RELEASE_HISTORICAL else historical
    if target not in other.present:
        return "PAIR_AVAILABILITY"
    if other.status[target] != SCORED:
        return "STATE_TRANSITION"
    if target in historical.tied or target in current.tied:
        return "CUTOFF_BOUNDARY_MEMBERSHIP"
    return "SCORE_ORDER"


def decompose_cell(
    historical: Cell,
    current: Cell,
    budget: int = BUDGET,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    identity_h = (historical.candidate_id, historical.disease_id, historical.realization_id)
    identity_c = (current.candidate_id, current.disease_id, current.realization_id)
    if identity_h != identity_c:
        raise ValueError(f"Cannot compare different cells: {identity_h!r} versus {identity_c!r}")
    if historical.operator_code != current.operator_code:
        raise ValueError(f"Operator-code mismatch for {identity_h!r}")
    if len(historical.deterministic) != budget or len(current.deterministic) != budget:
        raise ValueError(f"Non-capacity-{budget} deterministic list for {identity_h!r}")

    l_h = historical.deterministic
    l_c = current.deterministic
    mismatch: list[tuple[str, str]] = [
        *((target, RELEASE_HISTORICAL) for target in l_h - l_c),
        *((target, RELEASE_CURRENT) for target in l_c - l_h),
    ]
    mismatch.sort(key=lambda item: (item[0], item[1]))
    counts: Counter[str] = Counter()
    mismatch_rows: list[dict[str, object]] = []
    exact_context_name = OPEN_TARGETS_DISEASE_NAME_BY_ID.get(
        current.disease_id, current.context_name
    )
    for target, selected_release in mismatch:
        layer = _classify_mismatch(target, selected_release, historical, current)
        counts[layer] += 1
        mismatch_rows.append(
            {
                "candidate_id": historical.candidate_id,
                "context_name": exact_context_name,
                "qualification_context_name": current.context_name,
                "diseaseId": historical.disease_id,
                "realization_id": historical.realization_id,
                "operator_code": historical.operator_code,
                "targetId": target,
                "selected_release": selected_release,
                "decomposition_layer": layer,
                "present_26_03": target in historical.present,
                "present_26_06": target in current.present,
                "status_26_03": historical.status.get(target, ABSENT),
                "status_26_06": current.status.get(target, ABSENT),
                "cutoff_boundary_member_26_03": target in historical.tied,
                "cutoff_boundary_member_26_06": target in current.tied,
            }
        )

    deterministic_i = len(l_h & l_c)
    min_i, max_i = exact_intersection_bounds(historical, current)
    expected_i = expected_intersection(historical, current)
    common_scored = historical.scored & current.scored
    common_h = _top_from_scores(
        {target: historical.scores[target] for target in common_scored}, budget
    )
    common_c = _top_from_scores(
        {target: current.scores[target] for target in common_scored}, budget
    )
    denominator = 2 * budget
    contributions = {
        "PAIR_AVAILABILITY": counts["PAIR_AVAILABILITY"] / denominator,
        "STATE_TRANSITION": counts["STATE_TRANSITION"] / denominator,
        "CUTOFF_BOUNDARY_MEMBERSHIP": counts["CUTOFF_BOUNDARY_MEMBERSHIP"]
        / denominator,
        "SCORE_ORDER": counts["SCORE_ORDER"] / denominator,
    }
    deterministic_f = 1.0 - deterministic_i / budget
    contribution_sum = sum(contributions.values())
    if abs(contribution_sum - deterministic_f) > 1e-12:
        raise RuntimeError(
            f"Decomposition does not sum for {identity_h!r}: {contribution_sum} != {deterministic_f}"
        )
    row: dict[str, object] = {
        "candidate_id": historical.candidate_id,
        "context_name": exact_context_name,
        "qualification_context_name": current.context_name,
        "diseaseId": historical.disease_id,
        "realization_id": historical.realization_id,
        "operator_code": historical.operator_code,
        "pairs_26_03": len(historical.present),
        "pairs_26_06": len(current.present),
        "pair_additions": len(current.present - historical.present),
        "pair_removals": len(historical.present - current.present),
        "shared_scored_pairs": len(common_scored),
        "substitution_deterministic": deterministic_f,
        "substitution_expected_uniform_tie": 1.0 - expected_i / budget,
        "substitution_lower_bound": 1.0 - max_i / budget,
        "substitution_upper_bound": 1.0 - min_i / budget,
        "shared_scored_universe_substitution_deterministic": 1.0
        - len(common_h & common_c) / budget,
        "pair_availability_contribution": contributions["PAIR_AVAILABILITY"],
        "state_transition_contribution": contributions["STATE_TRANSITION"],
        "cutoff_boundary_membership_contribution": contributions[
            "CUTOFF_BOUNDARY_MEMBERSHIP"
        ],
        "score_order_contribution": contributions["SCORE_ORDER"],
        "contribution_sum": contribution_sum,
    }
    return row, mismatch_rows


def build_temporal_tables(
    historical: ReleaseData,
    current: ReleaseData,
    budget: int = BUDGET,
    expected_specifications: int | None = 32,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    shared_keys = sorted(set(historical.cells) & set(current.cells))
    if not shared_keys:
        raise ValueError("No exact shared context--specification cells")
    if set(historical.cells) != set(shared_keys):
        extras = sorted(set(historical.cells) - set(shared_keys))[:3]
        raise ValueError(f"Historical exact matrix has non-addressable cells: {extras}")

    cell_rows: list[dict[str, object]] = []
    mismatch_rows: list[dict[str, object]] = []
    for key in shared_keys:
        row, ledgers = decompose_cell(historical.cells[key], current.cells[key], budget=budget)
        cell_rows.append(row)
        mismatch_rows.extend(ledgers)

    by_context: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in cell_rows:
        by_context[(str(row["candidate_id"]), str(row["diseaseId"]))].append(row)
    context_rows: list[dict[str, object]] = []
    mean_map = (
        ("mean_substitution_deterministic", "substitution_deterministic"),
        ("mean_substitution_expected_uniform_tie", "substitution_expected_uniform_tie"),
        ("mean_substitution_lower_bound", "substitution_lower_bound"),
        ("mean_substitution_upper_bound", "substitution_upper_bound"),
        (
            "mean_shared_scored_universe_substitution",
            "shared_scored_universe_substitution_deterministic",
        ),
        ("mean_pair_availability_contribution", "pair_availability_contribution"),
        ("mean_state_transition_contribution", "state_transition_contribution"),
        (
            "mean_cutoff_boundary_membership_contribution",
            "cutoff_boundary_membership_contribution",
        ),
        ("mean_score_order_contribution", "score_order_contribution"),
    )
    for context_key in sorted(by_context):
        rows = sorted(by_context[context_key], key=lambda row: str(row["realization_id"]))
        if expected_specifications is not None and len(rows) != expected_specifications:
            raise ValueError(
                f"Expected {expected_specifications} specifications for {context_key!r}, "
                f"found {len(rows)}"
            )
        output: dict[str, object] = {
            "candidate_id": rows[0]["candidate_id"],
            "context_name": rows[0]["context_name"],
            "qualification_context_name": rows[0]["qualification_context_name"],
            "diseaseId": rows[0]["diseaseId"],
            "specifications": len(rows),
        }
        for output_name, source_name in mean_map:
            output[output_name] = sum(float(row[source_name]) for row in rows) / len(rows)
        context_rows.append(output)

    return cell_rows, context_rows, mismatch_rows


def run(
    historical_matrix: Path,
    current_matrix: Path,
    output_dir: Path,
    budget: int = BUDGET,
) -> dict[str, object]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    historical = load_release(historical_matrix, budget=budget)
    exact_candidate_ids = frozenset(candidate_id for candidate_id, _ in historical.contexts)
    current = load_release(current_matrix, budget=budget, candidate_ids=exact_candidate_ids)
    cell_rows, context_rows, mismatch_rows = build_temporal_tables(
        historical, current, budget=budget
    )

    cell_path = output_dir / "R17_TEMPORAL_CELL_DECOMPOSITION_160.tsv"
    context_path = output_dir / "R17_TEMPORAL_CONTEXT_DECOMPOSITION.tsv"
    mismatch_path = output_dir / "R17_TEMPORAL_MISMATCH_TARGETS.tsv.gz"
    _write_tsv(cell_path, cell_rows, CELL_COLUMNS)
    _write_tsv(context_path, context_rows, CONTEXT_COLUMNS)
    _write_gzip_tsv(mismatch_path, mismatch_rows, MISMATCH_COLUMNS)

    all_nonnegative = all(
        float(row[column]) >= 0
        for row in cell_rows
        for column in (
            "pair_availability_contribution",
            "state_transition_contribution",
            "cutoff_boundary_membership_contribution",
            "score_order_contribution",
        )
    )
    all_sums_exact = all(
        abs(float(row["contribution_sum"]) - float(row["substitution_deterministic"]))
        <= 1e-12
        for row in cell_rows
    )
    bladder = next(row for row in context_rows if row["candidate_id"] == "CCTX001")
    receipt: dict[str, object] = {
        "analysis": "V12 executable exact-ID 26.03-to-26.06 ordered temporal decomposition",
        "decision": "PASS" if len(cell_rows) == 160 and len(context_rows) == 5 and all_nonnegative and all_sums_exact else "FAIL",
        "scientific_inputs": {
            "historical_matrix_sha256": _sha256(historical_matrix),
            "current_matrix_sha256": _sha256(current_matrix),
            "frozen_decomposition_outputs_read_as_input": False,
        },
        "budget": budget,
        "exact_id_contexts": len(context_rows),
        "context_specification_cells": len(cell_rows),
        "mismatch_ledger_rows": len(mismatch_rows),
        "contributions_nonnegative": all_nonnegative,
        "decomposition_sums_to_deterministic_F": all_sums_exact,
        "bladder_component_means": {
            "pair_availability": bladder["mean_pair_availability_contribution"],
            "state_transition": bladder["mean_state_transition_contribution"],
            "cutoff_boundary_membership": bladder[
                "mean_cutoff_boundary_membership_contribution"
            ],
            "score_order": bladder["mean_score_order_contribution"],
        },
        "cutoff_boundary_semantics": (
            "Membership in either release's exact cutoff-score block; the block "
            "may be singleton or repeated and this component is not a measure of "
            "set-valued tie ambiguity."
        ),
        "context_name_semantics": (
            "context_name is the exact Open Targets disease name; "
            "qualification_context_name retains the narrower coverage label."
        ),
        "outputs": {
            cell_path.name: {"rows": len(cell_rows), "sha256": _sha256(cell_path)},
            context_path.name: {"rows": len(context_rows), "sha256": _sha256(context_path)},
            mismatch_path.name: {"rows": len(mismatch_rows), "sha256": _sha256(mismatch_path)},
        },
        "scope_boundary": (
            "Ordered descriptive bookkeeping for the five exact-disease-ID contexts "
            "in Open Targets 26.03 and 26.06; not causal attribution and not a "
            "general estimator of release instability."
        ),
    }
    receipt_path = output_dir / "R26_V12_TEMPORAL_DECOMPOSITION_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if receipt["decision"] != "PASS":
        raise RuntimeError("V12_TEMPORAL_DECOMPOSITION_FAIL")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild the ordered temporal decomposition from two supplied derived matrices."
    )
    parser.add_argument("--historical-matrix", required=True, type=Path)
    parser.add_argument("--current-matrix", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--budget", type=int, default=BUDGET)
    args = parser.parse_args()
    receipt = run(
        historical_matrix=args.historical_matrix,
        current_matrix=args.current_matrix,
        output_dir=args.output_dir,
        budget=args.budget,
    )
    print(receipt["decision"])
    print(f"context_specification_cells={receipt['context_specification_cells']}")
    print(f"exact_id_contexts={receipt['exact_id_contexts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
