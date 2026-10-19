"""Publication-facing implementations of TRACE-DT evidence contracts.

The functions in this module are path-free and deterministic. They reproduce
the rule logic used for the version-locked Open Targets 26.06 analysis; they
do not download data, rank targets, or access prospective outcome data.

The 12-source Boolean predicates identify primary-hard-positive evidence. A
matching row excludes its target-cancer pair from the scored hard-negative
pool; it is not an eligibility or nomination predicate.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping


PRIMARY_HARD_EVIDENCE_DATASOURCES = frozenset(
    {
        "cancer_gene_census",
        "clingen",
        "clinical_precedence",
        "eva",
        "eva_somatic",
        "gene2phenotype",
        "gene_burden",
        "genomics_england",
        "gwas_credible_sets",
        "intogen",
        "orphanet",
        "uniprot_variants",
    }
)
# Backward-compatible internal alias for historical scripts. Reader-facing
# code should use PRIMARY_HARD_EVIDENCE_DATASOURCES.
PRIMARY_DATASOURCES = PRIMARY_HARD_EVIDENCE_DATASOURCES


@dataclass(frozen=True)
class PrimaryHardEvidenceResult:
    matches_exclusion: bool
    hard_class: str
    reason: str

    @property
    def eligible(self) -> bool:
        """Historical field alias; means matches_exclusion, not nomination eligibility."""

        return self.matches_exclusion


@dataclass(frozen=True)
class CanonicalKeyResult:
    canonical_key: str
    key_tier: str
    released_id_fallback: bool


@dataclass(frozen=True)
class ProvenanceResult:
    ancestry_group_id: str
    resolution_status: str
    forced_abstention_reason: str


def _flatten(value: Any) -> Iterable[Any]:
    if value is None:
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _flatten(nested)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            yield from _flatten(nested)
        return
    yield value


def normalize_text(value: Any, *, lowercase: bool) -> str:
    """Normalize scalar or nested fields exactly as the distributed contract.

    Empty and null values are removed. Nested values are trimmed, deduplicated,
    sorted, and joined with ``|``. Primary-evidence predicates lowercase text;
    canonical-key construction intentionally preserves case because the
    executed R implementation did so.
    """

    values: list[str] = []
    for item in _flatten(value):
        text = str(item).strip()
        if not text or text.lower() in {"nan", "none"}:
            continue
        values.append(text.lower() if lowercase else text)
    if not values:
        return ""
    return "|".join(sorted(set(values)))


def numeric_value(record: Mapping[str, Any], field_name: str) -> float:
    value = record.get(field_name)
    if value is None:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def contains_token(normalized_value: str, tokens: Iterable[str]) -> bool:
    observed = set(normalized_value.split("|")) if normalized_value else set()
    return any(token in observed for token in tokens)


def primary_hard_evidence_exclusion(
    record: Mapping[str, Any], datasource_id: str
) -> PrimaryHardEvidenceResult:
    """Apply the executed v1 row-level primary-hard exclusion rule.

    Missing predicate fields normalize to empty text or non-finite numeric
    values and therefore fail their datasource rule. ``evidenceDate`` is not a
    predicate in the executed v1 code; the publication contract reports this
    separately from the stricter registry wording. A ``True`` result means the
    row is primary-hard-positive and its pair is excluded from scoring.
    """

    confidence = normalize_text(record.get("confidence"), lowercase=True)
    significance = normalize_text(
        record.get("clinicalSignificances"), lowercase=True
    )
    origin = normalize_text(record.get("alleleOrigins"), lowercase=True)
    stage = normalize_text(record.get("clinicalStage"), lowercase=True).upper()
    stop_categories = normalize_text(
        record.get("trialStopReasonCategories"), lowercase=True
    )
    driver_methods = normalize_text(
        record.get("significantDriverMethods"), lowercase=True
    )
    resource_score = numeric_value(record, "resourceScore")
    # This assignment is intentional: Open Targets gene_burden resourceScore
    # is the raw p-value used by the executed v1 rule.
    p_value = numeric_value(record, "resourceScore")
    beta = numeric_value(record, "beta")
    odds_ratio = numeric_value(record, "oddsRatio")

    if datasource_id == "clinical_precedence":
        permitted_stage = stage in {
            "PHASE_2",
            "PHASE_2_3",
            "PHASE_3",
            "PHASE_4",
            "PREAPPROVAL",
            "APPROVAL",
        }
        prohibited_stop = contains_token(
            stop_categories, {"negative", "safety_sideeffects"}
        )
        eligible = permitted_stage and not prohibited_stop
        return PrimaryHardEvidenceResult(
            eligible,
            "CLINICAL",
            (
                "QUALIFY_PHASE_II_PLUS_OR_REGULATORY_WITHOUT_NEGATIVE_OR_SAFETY_STOP"
                if eligible
                else "FAIL_STAGE_OR_STOP_REASON"
            ),
        )

    if datasource_id == "clingen":
        eligible = confidence in {"strong", "definitive"}
        return PrimaryHardEvidenceResult(
            eligible,
            "HUMAN_GENETIC",
            "QUALIFY_STRONG_OR_DEFINITIVE" if eligible else "FAIL_CONFIDENCE",
        )

    if datasource_id == "gene2phenotype":
        eligible = confidence in {
            "strong",
            "definitive",
            "both rd and if",
            "both_rd_and_if",
        }
        return PrimaryHardEvidenceResult(
            eligible,
            "HUMAN_GENETIC",
            "QUALIFY_STRONG_CAUSAL_G2P" if eligible else "FAIL_CONFIDENCE",
        )

    if datasource_id == "genomics_england":
        eligible = confidence == "green"
        return PrimaryHardEvidenceResult(
            eligible,
            "HUMAN_GENETIC",
            (
                "QUALIFY_DIAGNOSTIC_GRADE_GREEN"
                if eligible
                else "FAIL_CONFIDENCE"
            ),
        )

    if datasource_id == "eva":
        pathogenic = contains_token(
            significance, {"pathogenic", "likely pathogenic"}
        )
        reviewed = confidence in {
            "criteria provided, single submitter",
            "criteria provided, multiple submitters, no conflicts",
        }
        germline = contains_token(
            origin, {"germline", "de novo", "maternal", "paternal", "inherited"}
        )
        eligible = pathogenic and reviewed and germline
        return PrimaryHardEvidenceResult(
            eligible,
            "HUMAN_GENETIC",
            (
                "QUALIFY_REVIEWED_PATHOGENIC_GERMLINE"
                if eligible
                else "FAIL_SIGNIFICANCE_REVIEW_OR_ORIGIN"
            ),
        )

    if datasource_id == "gene_burden":
        effect_resolved = math.isfinite(beta) or math.isfinite(odds_ratio)
        eligible = math.isfinite(p_value) and p_value <= 5e-8 and effect_resolved
        return PrimaryHardEvidenceResult(
            eligible,
            "HUMAN_GENETIC",
            (
                "QUALIFY_GENOME_WIDE_SIGNIFICANT_BURDEN_WITH_EFFECT"
                if eligible
                else "FAIL_PVALUE_OR_EFFECT"
            ),
        )

    if datasource_id == "gwas_credible_sets":
        eligible = math.isfinite(resource_score) and resource_score >= 0.5
        return PrimaryHardEvidenceResult(
            eligible,
            "HUMAN_GENETIC",
            (
                "QUALIFY_L2G_AT_LEAST_0_5"
                if eligible
                else "FAIL_L2G_STRONG_THRESHOLD"
            ),
        )

    if datasource_id == "orphanet":
        eligible = confidence == "assessed"
        return PrimaryHardEvidenceResult(
            eligible,
            "HUMAN_GENETIC",
            "QUALIFY_ORPHANET_ASSESSED_RELATION" if eligible else "FAIL_CONFIDENCE",
        )

    if datasource_id == "uniprot_variants":
        eligible = confidence == "high"
        return PrimaryHardEvidenceResult(
            eligible,
            "HUMAN_GENETIC",
            (
                "QUALIFY_HIGH_CONFIDENCE_CURATED_VARIANT"
                if eligible
                else "FAIL_CONFIDENCE"
            ),
        )

    if datasource_id == "cancer_gene_census":
        eligible = math.isfinite(resource_score) and resource_score >= 0.5
        return PrimaryHardEvidenceResult(
            eligible,
            "SOMATIC_CANCER_GENETIC",
            (
                "QUALIFY_CGC_CAUSAL_SCORE_AT_LEAST_0_5"
                if eligible
                else "FAIL_CGC_CAUSAL_THRESHOLD"
            ),
        )

    if datasource_id == "eva_somatic":
        pathogenic = contains_token(
            significance, {"pathogenic", "likely pathogenic"}
        )
        reviewed = confidence in {
            "criteria provided, single submitter",
            "criteria provided, multiple submitters, no conflicts",
        }
        somatic = contains_token(origin, {"somatic"})
        eligible = pathogenic and reviewed and somatic
        return PrimaryHardEvidenceResult(
            eligible,
            "SOMATIC_CANCER_GENETIC",
            (
                "QUALIFY_REVIEWED_PATHOGENIC_SOMATIC"
                if eligible
                else "FAIL_SIGNIFICANCE_REVIEW_OR_ORIGIN"
            ),
        )

    if datasource_id == "intogen":
        eligible = (
            math.isfinite(resource_score)
            and resource_score <= 0.01
            and bool(driver_methods)
        )
        return PrimaryHardEvidenceResult(
            eligible,
            "SOMATIC_CANCER_GENETIC",
            (
                "QUALIFY_SIGNIFICANT_DRIVER_Q_LE_0_01"
                if eligible
                else "FAIL_DRIVER_METHOD_OR_QVALUE"
            ),
        )

    return PrimaryHardEvidenceResult(
        False, "NOT_PRIMARY", "DATASOURCE_NOT_IN_PRIMARY_WHITELIST"
    )


def primary_evidence_eligibility(
    record: Mapping[str, Any], datasource_id: str
) -> PrimaryHardEvidenceResult:
    """Historical compatibility alias for :func:`primary_hard_evidence_exclusion`.

    The returned ``eligible`` property is retained solely for reproducing the
    legacy internal implementation and means ``matches_exclusion``.
    """

    return primary_hard_evidence_exclusion(record, datasource_id)


def resolve_canonical_key(
    record: Mapping[str, Any], datasource_id: str, priority_spec: str
) -> CanonicalKeyResult:
    """Resolve the first complete datasource-specific key tier."""

    for tier in priority_spec.split(";"):
        fields = tier.split("+")
        parts = [
            normalize_text(record.get(field_name), lowercase=False)
            for field_name in fields
        ]
        if not all(parts):
            continue
        tokens = [
            f"{field_name}={part}"
            for field_name, part in zip(fields, parts, strict=True)
        ]
        return CanonicalKeyResult(
            canonical_key=(
                f"{datasource_id}::{tier}::" + "&&".join(tokens)
            ),
            key_tier=tier,
            released_id_fallback=tier == "id",
        )
    return CanonicalKeyResult("", "", False)


def resolve_provenance(
    datasource_id: str,
    canonical_key: str,
    mapping: Mapping[tuple[str, str], Mapping[str, Any]],
) -> ProvenanceResult:
    """Resolve a canonical key against the distributed source-unit mapping."""

    entry = mapping.get((datasource_id, canonical_key))
    if entry is None:
        return ProvenanceResult("", "MISSING_R05_MAPPING", "MISSING_R05_MAPPING")
    return ProvenanceResult(
        str(entry.get("ancestry_group_id") or ""),
        str(entry.get("resolution_status") or ""),
        str(entry.get("forced_abstention_reason") or ""),
    )


def operator_status_with_precedence(
    *,
    primary_hard_positive: bool,
    positive_raw_rows: int,
    invalid_score: bool,
    unresolved_key: bool,
    unresolved_provenance: bool,
    use_independent_key: bool,
    use_provenance_grouping: bool,
) -> str:
    """Apply the executed status-assignment precedence.

    Later conditions overwrite earlier ones. Consequently unresolved
    provenance under O2 has precedence over the primary-hard exclusion state.
    """

    status = "SCORED"
    if primary_hard_positive:
        status = "INELIGIBLE_T0_PRIMARY_HARD_EVIDENCE"
    if positive_raw_rows == 0:
        status = "ABSTAIN_NO_POSITIVE_RAW_EVIDENCE"
    if invalid_score:
        status = "ABSTAIN_INVALID_SCORE"
    if use_independent_key and unresolved_key:
        status = "ABSTAIN_UNRESOLVED_INDEPENDENT_KEY"
    if use_provenance_grouping and unresolved_provenance:
        status = "ABSTAIN_UNRESOLVED_ANCESTRY"
    return status
