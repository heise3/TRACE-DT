from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


ARTIFACT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTIFACT_ROOT / "src"))

from trace_dt.scoring_reference import (  # noqa: E402
    PRIMARY_EXCLUDED,
    UNRESOLVED_PROVENANCE,
    CanonicalRecord,
    average_percentile,
    harmonic_normalized,
    score_context,
    specification_codes,
)


class ScoringReferenceTests(unittest.TestCase):
    def test_contract_has_exactly_32_codes(self) -> None:
        codes = specification_codes()
        self.assertEqual(len(codes), 32)
        self.assertEqual(codes[0], "00000")
        self.assertEqual(codes[-1], "11111")

    def test_average_percentile_matches_r_average_rank(self) -> None:
        self.assertEqual(average_percentile([1.0, 1.0, 3.0]), [0.5, 0.5, 1.0])

    def test_average_percentile_tied_maximum_is_below_one(self) -> None:
        observed = average_percentile([1.0, 1.0, 0.0, 0.0])
        self.assertEqual(observed, [0.875, 0.875, 0.375, 0.375])

    def test_average_percentile_tied_interior_uses_mean_rank(self) -> None:
        observed = average_percentile([0.1, 0.5, 0.5, 0.9])
        self.assertEqual(observed, [0.25, 0.625, 0.625, 1.0])

    def test_harmonic_normalization(self) -> None:
        expected = (1.0 + 0.5 / 4.0) / (1.0 + 1.0 / 4.0)
        self.assertTrue(math.isclose(harmonic_normalized([0.5, 1.0]), expected))

    def test_primary_hard_positive_is_excluded_not_scored(self) -> None:
        result = score_context(
            target_ids=["A"],
            records=[
                CanonicalRecord("A", "ds", "key", "prov", 0.9),
            ],
            primary_excluded_targets=["A"],
            operator_code="00000",
            top_k=1,
        )[0]
        self.assertEqual(result.status, PRIMARY_EXCLUDED)
        self.assertIsNone(result.score)
        self.assertFalse(result.selected_top_k)

    def test_unresolved_o2_provenance_has_terminal_precedence(self) -> None:
        result = score_context(
            target_ids=["A"],
            records=[
                CanonicalRecord("A", "ds", "key", "", 0.9),
            ],
            primary_excluded_targets=["A"],
            operator_code="01000",
            top_k=1,
        )[0]
        self.assertEqual(result.status, UNRESOLVED_PROVENANCE)
        self.assertIsNone(result.score)
        self.assertFalse(result.selected_top_k)

    def test_score_order_and_target_id_tie_break(self) -> None:
        results = score_context(
            target_ids=["B", "A", "C"],
            records=[
                CanonicalRecord("A", "ds", "a", "pa", 0.8),
                CanonicalRecord("B", "ds", "b", "pb", 0.8),
                CanonicalRecord("C", "ds", "c", "pc", 0.7),
            ],
            primary_excluded_targets=[],
            operator_code="00000",
            top_k=2,
        )
        lookup = {row.target_id: row for row in results}
        self.assertEqual(lookup["A"].rank, 1)
        self.assertEqual(lookup["B"].rank, 2)
        self.assertEqual(lookup["C"].rank, 3)
        self.assertTrue(lookup["A"].selected_top_k)
        self.assertTrue(lookup["B"].selected_top_k)
        self.assertFalse(lookup["C"].selected_top_k)


if __name__ == "__main__":
    unittest.main()
