from __future__ import annotations

import sys
import unittest
from pathlib import Path


ARTIFACT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTIFACT_ROOT / "src"))

from trace_dt.evidence_contracts import (  # noqa: E402
    normalize_text,
    operator_status_with_precedence,
    primary_hard_evidence_exclusion,
    resolve_canonical_key,
    resolve_provenance,
)


class PrimaryHardEvidenceExclusionContractTests(unittest.TestCase):
    def test_gene_burden_resource_score_match_triggers_exclusion(self) -> None:
        result = primary_hard_evidence_exclusion(
            {"resourceScore": 1e-12, "beta": 0.2}, "gene_burden"
        )
        self.assertTrue(result.matches_exclusion)

    def test_gene_burden_does_not_substitute_a_pvalue_field(self) -> None:
        result = primary_hard_evidence_exclusion(
            {"pValue": 1e-20, "beta": 0.2}, "gene_burden"
        )
        self.assertFalse(result.matches_exclusion)

    def test_negative_clinical_stop_prevents_hard_positive_match(self) -> None:
        result = primary_hard_evidence_exclusion(
            {
                "clinicalStage": "PHASE_3",
                "trialStopReasonCategories": ["Negative"],
            },
            "clinical_precedence",
        )
        self.assertFalse(result.matches_exclusion)

    def test_nested_text_is_sorted_unique_and_lowercase(self) -> None:
        self.assertEqual(
            normalize_text(["Likely pathogenic", "Pathogenic", "Pathogenic"], lowercase=True),
            "likely pathogenic|pathogenic",
        )

    def test_primary_hard_positive_is_an_exclusion_state(self) -> None:
        status = operator_status_with_precedence(
            primary_hard_positive=True,
            positive_raw_rows=1,
            invalid_score=False,
            unresolved_key=False,
            unresolved_provenance=False,
            use_independent_key=True,
            use_provenance_grouping=True,
        )
        self.assertEqual(status, "INELIGIBLE_T0_PRIMARY_HARD_EVIDENCE")

    def test_primary_hard_negative_can_remain_scored(self) -> None:
        status = operator_status_with_precedence(
            primary_hard_positive=False,
            positive_raw_rows=1,
            invalid_score=False,
            unresolved_key=False,
            unresolved_provenance=False,
            use_independent_key=True,
            use_provenance_grouping=True,
        )
        self.assertEqual(status, "SCORED")


class CanonicalKeyContractTests(unittest.TestCase):
    def test_first_complete_tier_precedes_fallback(self) -> None:
        result = resolve_canonical_key(
            {"studyId": "S1", "id": "fallback"},
            "clingen",
            "studyId;id",
        )
        self.assertEqual(result.canonical_key, "clingen::studyId::studyId=S1")
        self.assertFalse(result.released_id_fallback)

    def test_composite_tier_uses_fixed_field_order(self) -> None:
        result = resolve_canonical_key(
            {"projectId": "P", "cohortId": "C"},
            "gene_burden",
            "projectId+cohortId;cohortId;id",
        )
        self.assertEqual(
            result.canonical_key,
            "gene_burden::projectId+cohortId::projectId=P&&cohortId=C",
        )

    def test_missing_component_uses_next_complete_tier(self) -> None:
        result = resolve_canonical_key(
            {"projectId": "P", "cohortId": "", "id": "I"},
            "gene_burden",
            "projectId+cohortId;cohortId;projectId;id",
        )
        self.assertEqual(result.key_tier, "projectId")

    def test_executed_key_normalization_preserves_case(self) -> None:
        result = resolve_canonical_key(
            {"literature": ["pmid:2", "PMID:1"]},
            "europepmc",
            "literature;id",
        )
        self.assertIn("PMID:1|pmid:2", result.canonical_key)

    def test_missing_mapping_is_explicit(self) -> None:
        result = resolve_provenance("eva", "eva::id::id=x", {})
        self.assertEqual(result.resolution_status, "MISSING_R05_MAPPING")
        self.assertEqual(result.ancestry_group_id, "")

    def test_provenance_abstention_has_final_precedence(self) -> None:
        status = operator_status_with_precedence(
            primary_hard_positive=True,
            positive_raw_rows=1,
            invalid_score=False,
            unresolved_key=False,
            unresolved_provenance=True,
            use_independent_key=True,
            use_provenance_grouping=True,
        )
        self.assertEqual(status, "ABSTAIN_UNRESOLVED_ANCESTRY")


if __name__ == "__main__":
    unittest.main()
