#!/usr/bin/env python3
"""Run the transparent Open Targets construction-contract fixture.

The fixture exercises primary-evidence exclusion, canonical-key resolution,
provenance failure, O1--O5 score construction, average-rank percentile ties,
deterministic ranking, and all five B01 component perturbations.  It downloads
nothing and opens no frozen target identities.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from trace_dt.b01_reference import b01_component_scores  # noqa: E402
from trace_dt.evidence_contracts import (  # noqa: E402
    primary_hard_evidence_exclusion,
    resolve_canonical_key,
    resolve_provenance,
)
from trace_dt.scoring_reference import (  # noqa: E402
    CanonicalRecord,
    average_percentile,
    score_context,
)


EXPECTED = {
    "canonical_key_tier": "projectId+cohortId",
    "eligibility_exclusion_true": True,
    "eligibility_exclusion_false": False,
    "o1_changes_target_a_score": True,
    "o2_unresolved_status": "ABSTAIN_UNRESOLVED_ANCESTRY",
    "o3_tied_maximum": [0.875, 0.875, 0.375, 0.375],
    "o3_tied_interior": [0.25, 0.625, 0.625, 1.0],
    "operator_codes_checked": [
        "00000",
        "10000",
        "01000",
        "00100",
        "00010",
        "10010",
        "00001",
    ],
    "b01_variants": [
        "ABL_UPPER_ARITHMETIC_WEIGHTED_ONLY",
        "ABL_UPPER_NORMALIZER_OBSERVED_ONLY",
        "ABL_WEIGHT_EQUAL_ONLY",
        "ABL_WITHIN_MAX_ONLY",
        "ABL_WITHIN_OBSERVED_HARMONIC_ONLY",
        "B01_EXACT_REPLAY",
    ],
}


def build_fixture() -> dict[str, object]:
    hard_true = primary_hard_evidence_exclusion(
        {"resourceScore": 1e-12, "beta": 0.2}, "gene_burden"
    )
    hard_false = primary_hard_evidence_exclusion(
        {"resourceScore": 0.2, "beta": 0.2}, "gene_burden"
    )
    key = resolve_canonical_key(
        {"projectId": "P1", "cohortId": "C1", "id": "fallback"},
        "gene_burden",
        "projectId+cohortId;cohortId;projectId;id",
    )
    missing_provenance = resolve_provenance("ds2", "ds2::key", {})

    records = [
        CanonicalRecord("A", "ds1", "dup", "p1", 0.9),
        CanonicalRecord("A", "ds1", "dup", "p1", 0.4),
        CanonicalRecord("A", "ds2", "a2", "p2", 0.7),
        CanonicalRecord("B", "ds1", "b1", "p1", 0.9),
        CanonicalRecord("B", "ds2", "b2", "p2", 0.2),
        CanonicalRecord("C", "ds1", "c1", "", 0.6),
    ]
    target_ids = ["A", "B", "C", "D"]
    score_runs = {
        code: {
            row.target_id: {
                "status": row.status,
                "score": row.score,
                "rank": row.rank,
                "selected": row.selected_top_k,
            }
            for row in score_context(
                target_ids=target_ids,
                records=records,
                primary_excluded_targets=[],
                operator_code=code,
                top_k=2,
            )
        }
        for code in EXPECTED["operator_codes_checked"]
    }
    b01 = b01_component_scores(
        {"ds1": [0.9, 0.4, 0.2], "ds2": [0.7, 0.2]},
        {"ds1": 1.0, "ds2": 0.5},
    )
    if any(not math.isfinite(value) for value in b01.values()):
        raise AssertionError("non-finite B01 fixture value")

    observed = {
        "canonical_key_tier": key.key_tier,
        "eligibility_exclusion_true": hard_true.matches_exclusion,
        "eligibility_exclusion_false": hard_false.matches_exclusion,
        # O1 is contrasted while O4 uses the rank-weighted harmonic rule.
        # Under O4=max, the lower duplicate is structurally irrelevant and
        # would be an invalid fixture for testing the effect of O1 collapse.
        "o1_changes_target_a_score": (
            score_runs["00010"]["A"]["score"]
            != score_runs["10010"]["A"]["score"]
        ),
        "o2_unresolved_status": score_runs["01000"]["C"]["status"],
        "o3_tied_maximum": average_percentile([1.0, 1.0, 0.0, 0.0]),
        "o3_tied_interior": average_percentile([0.1, 0.5, 0.5, 0.9]),
        "operator_codes_checked": list(score_runs),
        "b01_variants": sorted(b01),
    }
    return {
        "gate": "PASS" if observed == EXPECTED else "FAIL",
        "expected_contract": EXPECTED,
        "observed_contract": observed,
        "canonical_key": key.canonical_key,
        "missing_provenance_status": missing_provenance.resolution_status,
        "score_runs": score_runs,
        "b01_component_scores": b01,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    payload = build_fixture()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.verify and payload["gate"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
