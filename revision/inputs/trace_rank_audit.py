#!/usr/bin/env python3
"""Platform-agnostic, tie-aware audit for fixed-capacity ranked lists.

Input TSV columns:
    context_id, candidate_id, specification_id, score

Additional columns are ignored. A row is a scored candidate under one
context–specification cell. Candidate identifiers are used only as a
deterministic tie rule; necessary/possible and exact-bound outputs remain the
scientific objects.

This generic engine audits ranked score tables only. Evidence eligibility,
provenance resolution, factor-registry construction, and cross-release
identifier addressability are adapter-level workflows and are deliberately not
implemented by this command-line program.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from itertools import combinations
from pathlib import Path


REQUIRED = {"context_id", "candidate_id", "specification_id", "score"}
__version__ = "1.2.1"

CELL_COLUMNS = (
    "context_id",
    "specification_id",
    "candidate_n",
    "budget",
    "cutoff_score",
    "necessary_n",
    "tie_block_n",
    "remaining_tie_seats",
    "possible_n",
    "boundary_set_valued",
)
PAIRWISE_COLUMNS = (
    "context_id",
    "specification_a",
    "specification_b",
    "candidate_a_n",
    "candidate_b_n",
    "candidate_shared_n",
    "candidate_union_n",
    "intersection_expected_chance",
    "intersection_deterministic",
    "intersection_expected_uniform_tie",
    "intersection_minimum",
    "intersection_maximum",
    "substitution_deterministic",
    "substitution_expected_uniform_tie",
    "substitution_lower_bound",
    "substitution_upper_bound",
    "chance_adjusted_stability_deterministic",
)
MEMBERSHIP_COLUMNS = (
    "context_id",
    "specification_id",
    "candidate_id",
    "score",
    "deterministic_selected",
    "necessary_selected",
    "possible_selected",
    "uniform_tie_selection_probability",
)


def validate_tie_tolerance(value: str | float) -> float:
    """Return a finite, non-negative tie tolerance.

    Python float conversion accepts strings such as nan and inf. Those values
    are not legal audit parameters because comparisons against them do not
    define a finite boundary and Python's default JSON encoder would serialize
    them using non-standard tokens.
    """
    try:
        tolerance = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Tie tolerance must be a finite non-negative number"
        ) from exc
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Tie tolerance must be a finite non-negative number")
    return tolerance


def validate_receipt_completed_utc(value: str | None) -> str | None:
    """Validate an optional timezone-aware ISO-8601 UTC receipt timestamp."""
    if value is None:
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(
            "Receipt completion timestamp must be an ISO-8601 UTC timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "Receipt completion timestamp must be an ISO-8601 UTC timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(
            "Receipt completion timestamp must be timezone-aware UTC"
        )
    return value


def validate_identifier(field: str, value: str | None, line_number: int) -> str:
    """Reject empty, padded, or control-bearing identifiers before output."""
    if value is None or not value:
        raise ValueError(f"Empty {field} at line {line_number}")
    if value != value.strip():
        raise ValueError(
            f"Leading or trailing whitespace in {field} at line {line_number}"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"Control character in {field} at line {line_number}")
    return value


def integerize_proportional_budget(candidate_n: int, proportion: str | float) -> int:
    """Return the frozen proportional-sensitivity capacity.

    The historical sensitivity analysis used ``max(1, floor(q * N))``, where
    ``N`` is the scored candidate-pool size for a context and ``q`` is the
    requested proportion. ``Fraction(str(q))`` avoids binary-floating-point
    ambiguity at exact integer boundaries. This helper documents and tests
    that software contract; the primary command-line audit continues to accept
    an explicit integer ``--budget``.
    """
    if candidate_n < 1:
        raise ValueError("candidate_n must be a positive integer")
    q = Fraction(str(proportion))
    if q <= 0 or q > 1:
        raise ValueError("proportion must satisfy 0 < proportion <= 1")
    return max(1, (candidate_n * q.numerator) // q.denominator)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Cell:
    context_id: str
    specification_id: str
    scored: frozenset[str]
    strict_above: frozenset[str]
    tied: frozenset[str]
    deterministic: frozenset[str]
    remaining_seats: int
    cutoff_score: float

    @property
    def tie_probability(self) -> float:
        return self.remaining_seats / len(self.tied)

    @property
    def necessary(self) -> frozenset[str]:
        """Candidates present in every legal capacity-B realization.

        Candidates strictly above the cutoff are always necessary.  When all
        members of the boundary block are required to fill the remaining
        seats, the boundary is not set-valued and every boundary member is
        necessary as well.
        """
        if self.remaining_seats == len(self.tied):
            return self.strict_above | self.tied
        return self.strict_above

    @property
    def guaranteed(self) -> frozenset[str]:
        """Deprecated Python-level alias for :attr:`necessary`.

        Version 1.2 renamed the public scientific object because "necessary"
        states the quantifier explicitly: membership in every legal list.
        TSV outputs use only ``necessary_*`` names.
        """
        warnings.warn(
            "Cell.guaranteed is deprecated; use Cell.necessary for membership "
            "in every legal capacity-B realization.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.necessary

    @property
    def possible(self) -> frozenset[str]:
        return self.strict_above | self.tied


def build_cell(
    context_id: str,
    specification_id: str,
    scores: dict[str, float],
    budget: int,
    tie_tolerance: float = 0.0,
) -> Cell:
    tie_tolerance = validate_tie_tolerance(tie_tolerance)
    if len(scores) < budget:
        raise ValueError(
            f"{context_id}/{specification_id}: {len(scores)} scores < B={budget}"
        )
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    cutoff = ordered[budget - 1][1]
    strict_above = frozenset(
        candidate for candidate, score in ordered if score > cutoff + tie_tolerance
    )
    tied = frozenset(
        candidate
        for candidate, score in ordered
        if abs(score - cutoff) <= tie_tolerance
    )
    # A reproducible operational realization uses score first and candidate ID
    # second. Under a non-zero tolerance, all members of the tolerance-defined
    # boundary are treated as exchangeable for selection.
    deterministic = strict_above | frozenset(
        sorted(tied)[: budget - len(strict_above)]
    )
    remaining = budget - len(strict_above)
    if not 0 <= remaining <= len(tied):
        raise RuntimeError("Invalid cutoff-tie contract")
    return Cell(
        context_id=context_id,
        specification_id=specification_id,
        scored=frozenset(scores),
        strict_above=strict_above,
        tied=tied,
        deterministic=deterministic,
        remaining_seats=remaining,
        cutoff_score=cutoff,
    )


def exact_intersection_bounds(a: Cell, b: Cell) -> tuple[int, int]:
    """Return sharp minimum and maximum legal top-B intersection.

    The candidate universe is partitioned into strict-above/strict-above,
    strict-above/boundary, boundary/strict-above, boundary/boundary, and
    cell-specific boundary categories.
    The two nested loops enumerate only the numbers selected from the shared
    tie category; closed-form capacity limits determine all other category
    contributions. Consequently, the bounds are exact without enumerating the
    combinatorial family of admissible lists. With r_a and r_b remaining tie
    seats, time complexity is O(min(|T_a∩T_b|,r_a) *
    min(|T_a∩T_b|,r_b)) after O(|U_a∪U_b|) set construction.
    """
    # ``strict_above`` and ``tied`` are disjoint allocation categories.  Do
    # not substitute the derived ``necessary`` set here: when every boundary
    # member is required, necessary overlaps the allocation category by
    # definition and would double-count intersections.
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
        raise RuntimeError(
            f"No feasible assignment: {a.context_id}, "
            f"{a.specification_id} vs {b.specification_id}"
        )
    return base + int(best_min), base + int(best_max)


def expected_intersection(a: Cell, b: Cell) -> float:
    pa, pb = a.tie_probability, b.tie_probability
    return (
        len(a.strict_above & b.strict_above)
        + pa * len(a.tied & b.strict_above)
        + pb * len(a.strict_above & b.tied)
        + pa * pb * len(a.tied & b.tied)
    )


def load_scores(path: Path) -> dict[tuple[str, str], dict[str, float]]:
    cells: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError(
                f"Missing columns: {sorted(REQUIRED - set(reader.fieldnames or []))}"
            )
        for line_number, row in enumerate(reader, start=2):
            context_id = validate_identifier(
                "context_id", row["context_id"], line_number
            )
            specification_id = validate_identifier(
                "specification_id", row["specification_id"], line_number
            )
            candidate = validate_identifier(
                "candidate_id", row["candidate_id"], line_number
            )
            key = (context_id, specification_id)
            if candidate in cells[key]:
                raise ValueError(f"Duplicate candidate at line {line_number}: {key}")
            try:
                score = float(row["score"])
            except ValueError as exc:
                raise ValueError(f"Non-numeric score at line {line_number}") from exc
            if not math.isfinite(score):
                raise ValueError(f"Non-finite score at line {line_number}")
            cells[key][candidate] = score
    if not cells:
        raise ValueError(
            "Input contains no scored candidate rows; refusing to emit an empty PASS audit"
        )
    return cells


def write_tsv(
    path: Path,
    rows: list[dict[str, object]],
    fieldnames: tuple[str, ...],
) -> None:
    """Write a declared-schema TSV, including a header for a zero-row table."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def run(
    input_path: Path,
    output_dir: Path,
    budget: int,
    tie_tolerance: float = 0.0,
    emit_target_membership: bool = True,
    receipt_completed_utc: str | None = None,
) -> dict[str, object]:
    if budget <= 0:
        raise ValueError("Budget must be positive")
    tie_tolerance = validate_tie_tolerance(tie_tolerance)
    receipt_completed_utc = validate_receipt_completed_utc(receipt_completed_utc)
    # Refuse to merge a new run with any pre-existing output.  In particular,
    # a second run with --skip-target-membership must never leave a stale
    # target_membership.tsv from an earlier run while claiming that the file
    # was not emitted.  Existing *empty* directories remain valid so callers
    # can pre-create an isolated destination.
    if output_dir.exists():
        existing = sorted(path.name for path in output_dir.iterdir())
        if existing:
            preview = ", ".join(existing[:5])
            suffix = " ..." if len(existing) > 5 else ""
            raise FileExistsError(
                f"Output directory is not empty: {output_dir} "
                f"({preview}{suffix}). Use a new empty directory."
            )
    raw = load_scores(input_path)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=False)
    cells = {
        key: build_cell(key[0], key[1], scores, budget, tie_tolerance)
        for key, scores in raw.items()
    }
    by_context: dict[str, list[Cell]] = defaultdict(list)
    for cell in cells.values():
        by_context[cell.context_id].append(cell)

    cell_rows: list[dict[str, object]] = []
    membership_rows: list[dict[str, object]] = []
    for cell in sorted(
        cells.values(), key=lambda value: (value.context_id, value.specification_id)
    ):
        cell_rows.append(
            {
                "context_id": cell.context_id,
                "specification_id": cell.specification_id,
                "candidate_n": len(cell.scored),
                "budget": budget,
                "cutoff_score": cell.cutoff_score,
                "necessary_n": len(cell.necessary),
                "tie_block_n": len(cell.tied),
                "remaining_tie_seats": cell.remaining_seats,
                "possible_n": len(cell.possible),
                "boundary_set_valued": int(len(cell.tied) > cell.remaining_seats),
            }
        )
        for candidate in sorted(cell.scored) if emit_target_membership else ():
            membership_rows.append(
                {
                    "context_id": cell.context_id,
                    "specification_id": cell.specification_id,
                    "candidate_id": candidate,
                    "score": raw[(cell.context_id, cell.specification_id)][candidate],
                    "deterministic_selected": int(candidate in cell.deterministic),
                    "necessary_selected": int(candidate in cell.necessary),
                    "possible_selected": int(candidate in cell.possible),
                    "uniform_tie_selection_probability": (
                        1.0
                        if candidate in cell.strict_above
                        else cell.tie_probability
                        if candidate in cell.tied
                        else 0.0
                    ),
                }
            )

    pair_rows: list[dict[str, object]] = []
    for context_id, context_cells in sorted(by_context.items()):
        for a, b in combinations(
            sorted(context_cells, key=lambda value: value.specification_id), 2
        ):
            min_i, max_i = exact_intersection_bounds(a, b)
            expected_i = expected_intersection(a, b)
            deterministic_i = len(a.deterministic & b.deterministic)
            scored_a_n = len(a.scored)
            scored_b_n = len(b.scored)
            scored_shared_n = len(a.scored & b.scored)
            scored_union_n = len(a.scored | b.scored)
            # Under independent uniform top-B sampling from each cell's own
            # scored universe, only shared candidates can overlap. This
            # reduces to B^2/N when both scored universes are identical.
            chance_i = (
                scored_shared_n
                * (budget / scored_a_n)
                * (budget / scored_b_n)
            )
            pair_rows.append(
                {
                    "context_id": context_id,
                    "specification_a": a.specification_id,
                    "specification_b": b.specification_id,
                    "candidate_a_n": scored_a_n,
                    "candidate_b_n": scored_b_n,
                    "candidate_shared_n": scored_shared_n,
                    "candidate_union_n": scored_union_n,
                    "intersection_expected_chance": chance_i,
                    "intersection_deterministic": deterministic_i,
                    "intersection_expected_uniform_tie": expected_i,
                    "intersection_minimum": min_i,
                    "intersection_maximum": max_i,
                    "substitution_deterministic": 1 - deterministic_i / budget,
                    "substitution_expected_uniform_tie": 1 - expected_i / budget,
                    "substitution_lower_bound": 1 - max_i / budget,
                    "substitution_upper_bound": 1 - min_i / budget,
                    "chance_adjusted_stability_deterministic": (
                        (deterministic_i - chance_i) / (budget - chance_i)
                        if chance_i < budget
                        else 1.0
                    ),
                }
            )

    write_tsv(output_dir / "cell_contract.tsv", cell_rows, CELL_COLUMNS)
    # A context may legally contain a single specification.  It then has no
    # unordered comparison, but pairwise_audit.tsv remains a valid declared-
    # schema table rather than an absent file or a headerless zero-byte file.
    write_tsv(output_dir / "pairwise_audit.tsv", pair_rows, PAIRWISE_COLUMNS)
    if emit_target_membership:
        write_tsv(
            output_dir / "target_membership.tsv",
            membership_rows,
            MEMBERSHIP_COLUMNS,
        )
    bounds_valid = all(
        row["substitution_lower_bound"]
        <= row["substitution_deterministic"]
        <= row["substitution_upper_bound"]
        and row["substitution_lower_bound"]
        <= row["substitution_expected_uniform_tie"]
        <= row["substitution_upper_bound"]
        for row in pair_rows
    )
    summary = {
        "gate": "PASS" if bounds_valid else "FAIL",
        "input_sha256": sha256(input_path),
        "budget": budget,
        "tie_tolerance": tie_tolerance,
        "engine_version": __version__,
        "target_membership_emitted": emit_target_membership,
        "contexts": len(by_context),
        "cells": len(cells),
        "pairwise_comparisons": len(pair_rows),
        "bounds_valid": bounds_valid,
        "completed_utc": receipt_completed_utc or datetime.now(timezone.utc).isoformat(),
    }
    receipt_json = json.dumps(summary, indent=2, allow_nan=False) + "\n"
    (output_dir / "audit_receipt.json").write_text(receipt_json, encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--budget", type=int, default=50)
    parser.add_argument(
        "--tie-tolerance",
        default="0.0",
        help="Absolute tolerance around the unrounded Bth score (default: exact ties)",
    )
    parser.add_argument(
        "--skip-target-membership",
        action="store_true",
        help="Omit the large target-level file while retaining cell and pairwise audits",
    )
    parser.add_argument(
        "--receipt-completed-utc",
        default=None,
        help=(
            "Optional explicit ISO-8601 timestamp for byte-reproducible audit receipts; "
            "omit it for the actual completion time"
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    if args.budget <= 0:
        raise ValueError("Budget must be positive")
    tie_tolerance = validate_tie_tolerance(args.tie_tolerance)
    summary = run(
        args.input,
        args.output_dir,
        args.budget,
        tie_tolerance,
        emit_target_membership=not args.skip_target_membership,
        receipt_completed_utc=args.receipt_completed_utc,
    )
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0 if summary["gate"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        # User/input contract failures are expected CLI outcomes, not internal
        # crashes.  Emit one stable diagnostic line and a non-zero status
        # without exposing a Python traceback to reviewers or workflow logs.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
