"""Small, dependency-free reference implementation of the TRACE-DT score core.

The production reconstruction CLI is the R/Arrow workflow in
``workflow/reconstruct_release_matrix.R`` because it must preserve the nested
Open Targets field normalization used by the executed analysis.  This module
implements the same five scoring dimensions on already canonicalized records.
It is intentionally small enough to exercise with transparent fixtures.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Iterable, Mapping, Sequence


SCORED = "SCORED"
PRIMARY_EXCLUDED = "INELIGIBLE_T0_PRIMARY_HARD_EVIDENCE"
NO_POSITIVE = "ABSTAIN_NO_POSITIVE_RAW_EVIDENCE"
INVALID_SCORE = "ABSTAIN_INVALID_SCORE"
UNRESOLVED_KEY = "ABSTAIN_UNRESOLVED_INDEPENDENT_KEY"
UNRESOLVED_PROVENANCE = "ABSTAIN_UNRESOLVED_ANCESTRY"


@dataclass(frozen=True)
class CanonicalRecord:
    target_id: str
    datasource_id: str
    canonical_key: str
    provenance_group_id: str
    score: float


@dataclass(frozen=True)
class ScoreResult:
    target_id: str
    status: str
    score: float | None
    rank: int | None
    selected_top_k: bool


def harmonic_normalized(values: Sequence[float]) -> float:
    ordered = sorted((float(value) for value in values), reverse=True)
    if not ordered:
        raise ValueError("harmonic_normalized requires at least one value")
    weights = [1.0 / (index * index) for index in range(1, len(ordered) + 1)]
    return sum(value * weight for value, weight in zip(ordered, weights)) / sum(
        weights
    )


def average_percentile(values: Sequence[float]) -> list[float]:
    """Return R ``rank(ties.method='average') / n`` percentiles."""

    indexed = sorted(enumerate(float(value) for value in values), key=lambda x: x[1])
    out = [0.0] * len(indexed)
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        percentile = average_rank / len(indexed)
        for original_index, _ in indexed[start:end]:
            out[original_index] = percentile
        start = end
    return out


def _bits(operator_code: str) -> tuple[int, int, int, int, int]:
    if len(operator_code) != 5 or any(bit not in "01" for bit in operator_code):
        raise ValueError("operator_code must be a five-character binary string")
    return tuple(int(bit) for bit in operator_code)  # type: ignore[return-value]


def score_context(
    *,
    target_ids: Iterable[str],
    records: Iterable[CanonicalRecord],
    primary_excluded_targets: Iterable[str],
    operator_code: str,
    top_k: int = 50,
) -> list[ScoreResult]:
    """Score one context under one five-bit specification.

    State precedence is deliberately identical to the executed matrix:
    primary-hard-evidence exclusion is assigned before missing/invalid states,
    and unresolved O2 provenance is assigned last.  Thus an excluded pair with
    unresolved provenance is represented as provenance-abstained when O2=1.
    """

    o1, o2, o3, o4, o5 = _bits(operator_code)
    targets = sorted(set(target_ids))
    rows = list(records)
    excluded = set(primary_excluded_targets)
    by_target: dict[str, list[CanonicalRecord]] = defaultdict(list)
    for row in rows:
        by_target[row.target_id].append(row)

    working_scores = [row.score for row in rows]
    if o3:
        by_source_indices: dict[str, list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            by_source_indices[row.datasource_id].append(index)
        for indices in by_source_indices.values():
            percentiles = average_percentile([rows[index].score for index in indices])
            for index, percentile in zip(indices, percentiles):
                working_scores[index] = percentile

    invalid_targets = {
        row.target_id
        for row, score in zip(rows, working_scores)
        if not isfinite(score) or score <= 0 or score > 1
    }
    unresolved_key_targets = {
        row.target_id for row in rows if o1 and not row.canonical_key
    }
    unresolved_provenance_targets = {
        row.target_id for row in rows if o2 and not row.provenance_group_id
    }

    unit_values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row, score in zip(rows, working_scores):
        group_id = (
            f"ANCESTRY::{row.provenance_group_id}"
            if o2
            else f"DATASOURCE::{row.datasource_id}"
        )
        key = row.canonical_key if o1 else f"ROW::{len(unit_values)}"
        unit_values[(row.target_id, group_id, key)].append(score)

    grouped_units: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (target, group_id, _), values in unit_values.items():
        grouped_units[(target, group_id)].append(max(values) if o1 else values[0])

    group_scores: dict[str, list[float]] = defaultdict(list)
    for (target, _), values in grouped_units.items():
        group_scores[target].append(
            harmonic_normalized(values) if o4 else max(values)
        )

    target_scores = {
        target: harmonic_normalized(values) if o5 else mean(sorted(values, reverse=True))
        for target, values in group_scores.items()
    }

    statuses: dict[str, str] = {target: SCORED for target in targets}
    for target in targets:
        if target in excluded:
            statuses[target] = PRIMARY_EXCLUDED
        if not by_target.get(target):
            statuses[target] = NO_POSITIVE
        if target in invalid_targets:
            statuses[target] = INVALID_SCORE
        if target in unresolved_key_targets:
            statuses[target] = UNRESOLVED_KEY
        if target in unresolved_provenance_targets:
            statuses[target] = UNRESOLVED_PROVENANCE

    ranked = sorted(
        (
            (target, target_scores[target])
            for target in targets
            if statuses[target] == SCORED
            and target not in excluded
            and target in target_scores
            and isfinite(target_scores[target])
            and target_scores[target] > 0
        ),
        key=lambda item: (-item[1], item[0]),
    )
    rank_by_target = {target: index for index, (target, _) in enumerate(ranked, 1)}
    results = [
        ScoreResult(
            target_id=target,
            status=statuses[target],
            score=target_scores.get(target) if statuses[target] == SCORED else None,
            rank=rank_by_target.get(target),
            selected_top_k=rank_by_target.get(target, top_k + 1) <= top_k,
        )
        for target in targets
    ]
    return results


def specification_codes() -> tuple[str, ...]:
    return tuple(format(value, "05b") for value in range(32))

