"""Dependency-free reference implementation of released-score B01 components.

The production one-component-at-a-time analysis is distributed separately as
``workflow/run_b01_component_ablation.py``.  This module exposes the exact
within-datasource and across-datasource formulas on a small transparent input
so reviewers can exercise every B01 perturbation without Open Targets files.
It does not claim to replace the Arrow production workflow.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import fsum


H1000 = fsum(1.0 / (index * index) for index in range(1, 1001))


def weighted_harmonic(
    values: Sequence[float], *, fixed_normalizer: bool
) -> float:
    """Return the descending inverse-square weighted sum used by B01."""

    ordered = sorted((float(value) for value in values), reverse=True)
    if not ordered:
        raise ValueError("weighted_harmonic requires a nonempty vector")
    numerator = fsum(
        value / (index * index) for index, value in enumerate(ordered, 1)
    )
    denominator = (
        H1000
        if fixed_normalizer
        else fsum(1.0 / (index * index) for index in range(1, len(ordered) + 1))
    )
    return numerator / denominator


def b01_component_scores(
    rows_by_datasource: Mapping[str, Sequence[float]],
    datasource_weights: Mapping[str, float],
) -> dict[str, float]:
    """Compute B01 and its five frozen one-component perturbations.

    Within each datasource the released construction retains at most 50 rows,
    sorts them descending, and divides the inverse-square weighted numerator by
    H1000.  The resulting datasource scores are multiplied by official weights;
    the across-datasource step repeats the fixed-H1000 operation.  Every
    ``ABL_*`` value changes exactly one component from that anchor.
    """

    if set(rows_by_datasource) != set(datasource_weights):
        raise ValueError("datasource score and weight keys must match exactly")
    released_ds: dict[str, float] = {}
    observed_ds: dict[str, float] = {}
    maximum_ds: dict[str, float] = {}
    for datasource, values in rows_by_datasource.items():
        retained = sorted((float(value) for value in values), reverse=True)[:50]
        if not retained:
            raise ValueError(f"datasource {datasource!r} has no retained score")
        released_ds[datasource] = weighted_harmonic(
            retained, fixed_normalizer=True
        )
        observed_ds[datasource] = weighted_harmonic(
            retained, fixed_normalizer=False
        )
        maximum_ds[datasource] = retained[0]

    official_weighted = [
        released_ds[key] * float(datasource_weights[key])
        for key in sorted(released_ds)
    ]
    equal_weighted = [released_ds[key] for key in sorted(released_ds)]
    maximum_weighted = [
        maximum_ds[key] * float(datasource_weights[key])
        for key in sorted(released_ds)
    ]
    observed_within_weighted = [
        observed_ds[key] * float(datasource_weights[key])
        for key in sorted(released_ds)
    ]
    return {
        "B01_EXACT_REPLAY": weighted_harmonic(
            official_weighted, fixed_normalizer=True
        ),
        "ABL_WEIGHT_EQUAL_ONLY": weighted_harmonic(
            equal_weighted, fixed_normalizer=True
        ),
        "ABL_UPPER_NORMALIZER_OBSERVED_ONLY": weighted_harmonic(
            official_weighted, fixed_normalizer=False
        ),
        "ABL_UPPER_ARITHMETIC_WEIGHTED_ONLY": fsum(official_weighted)
        / len(official_weighted),
        "ABL_WITHIN_MAX_ONLY": weighted_harmonic(
            maximum_weighted, fixed_normalizer=True
        ),
        "ABL_WITHIN_OBSERVED_HARMONIC_ONLY": weighted_harmonic(
            observed_within_weighted, fixed_normalizer=True
        ),
    }
