#!/usr/bin/env python
"""One-component-at-a-time ablations around the released-score B01 anchor."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.dataset as ds

from run_r17_tie_aware_primary import build_cell, pair_record


BUDGET = 50
H1000 = float(np.sum(1.0 / (np.arange(1, 1001, dtype=float) ** 2)))


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


def harmonic_group_score(
    frame: pd.DataFrame,
    *,
    value_col: str,
    fixed_normalizer: bool,
) -> pd.Series:
    ordered = frame.sort_values(
        ["pair_key", value_col],
        ascending=[True, False],
        kind="mergesort",
    ).copy()
    ordered["_rank"] = (
        ordered.groupby("pair_key", sort=False, observed=True).cumcount() + 1
    )
    ordered["_term"] = ordered[value_col] / (ordered["_rank"].astype(float) ** 2)
    numerator = ordered.groupby(
        "pair_key", sort=False, observed=True
    )["_term"].sum()
    if fixed_normalizer:
        return numerator / H1000
    counts = ordered.groupby("pair_key", sort=False, observed=True).size()
    denominator = counts.map(
        lambda n: float(
            np.sum(1.0 / (np.arange(1, int(n) + 1, dtype=float) ** 2))
        )
    )
    return numerator / denominator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--open-targets-root", required=True, type=Path)
    parser.add_argument("--formal-input", required=True, type=Path)
    parser.add_argument("--baseline-metrics", required=True, type=Path)
    parser.add_argument("--datasource-registry", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    baseline = pd.read_parquet(args.baseline_metrics)
    baseline["candidate_id"] = baseline["candidate_id"].astype(str)
    baseline["diseaseId"] = baseline["diseaseId"].astype(str)
    baseline["targetId"] = baseline["targetId"].astype(str)
    baseline["pair_key"] = baseline["diseaseId"] + "::" + baseline["targetId"]
    contexts = baseline[["candidate_id", "context_name", "diseaseId"]].drop_duplicates()
    disease_ids = sorted(contexts["diseaseId"].unique())
    weights = pd.read_csv(args.datasource_registry, sep="\t")[
        ["datasourceId", "weight"]
    ]
    weights["datasourceId"] = weights["datasourceId"].astype(str)
    weights["weight"] = weights["weight"].astype(float)

    dataset = ds.dataset(
        str(args.open_targets_root / "association_by_datasource_direct"),
        format="parquet",
    )
    official = dataset.to_table(
        columns=[
            "diseaseId",
            "targetId",
            "aggregationType",
            "aggregationValue",
            "associationScore",
        ],
        filter=pc.field("diseaseId").isin(disease_ids),
    ).to_pandas()
    official = official.rename(
        columns={
            "aggregationValue": "datasourceId",
            "associationScore": "official_datasource_score",
        }
    )
    if not official["aggregationType"].astype(str).eq("datasourceId").all():
        raise ValueError("Unexpected association_by_datasource aggregation type")
    official["diseaseId"] = official["diseaseId"].astype(str)
    official["targetId"] = official["targetId"].astype(str)
    official["datasourceId"] = official["datasourceId"].astype(str)
    official["pair_key"] = official["diseaseId"] + "::" + official["targetId"]
    official = official.merge(
        weights,
        on="datasourceId",
        how="inner",
        validate="many_to_one",
    )

    formal = pd.read_parquet(
        args.formal_input,
        columns=["diseaseId", "targetId", "datasourceId", "score"],
    )
    formal["diseaseId"] = formal["diseaseId"].astype(str)
    formal["targetId"] = formal["targetId"].astype(str)
    formal["datasourceId"] = formal["datasourceId"].astype(str)
    formal["pair_key"] = formal["diseaseId"] + "::" + formal["targetId"]
    formal["score"] = formal["score"].astype(float)
    formal = formal.sort_values(
        ["pair_key", "datasourceId", "score"],
        ascending=[True, True, False],
        kind="mergesort",
    )
    formal["_within_source_rank"] = (
        formal.groupby(
            ["pair_key", "datasourceId"],
            sort=False,
            observed=True,
        ).cumcount()
        + 1
    )
    top50 = formal.loc[formal["_within_source_rank"] <= 50].copy()
    top50["_fixed_term"] = top50["score"] / (
        top50["_within_source_rank"].astype(float) ** 2
    )
    raw_ds = (
        top50.groupby(
            ["pair_key", "diseaseId", "targetId", "datasourceId"],
            as_index=False,
            sort=False,
            observed=True,
        )
        .agg(
            replay_fixed_datasource_score=("_fixed_term", lambda x: x.sum() / H1000),
            raw_max_datasource_score=("score", "max"),
            retained_evidence_rows=("_within_source_rank", "size"),
        )
    )
    h_by_count = {
        int(n): float(np.sum(1.0 / (np.arange(1, int(n) + 1) ** 2)))
        for n in raw_ds["retained_evidence_rows"].unique()
    }
    numerator = (
        top50.groupby(
            ["pair_key", "datasourceId"],
            sort=False,
            observed=True,
        )["_fixed_term"]
        .sum()
        .rename("_numerator")
        .reset_index()
    )
    raw_ds = raw_ds.merge(
        numerator,
        on=["pair_key", "datasourceId"],
        how="left",
        validate="one_to_one",
    )
    raw_ds["observed_harmonic_datasource_score"] = (
        raw_ds["_numerator"]
        / raw_ds["retained_evidence_rows"].map(h_by_count)
    )
    raw_ds = raw_ds.drop(columns="_numerator")

    source = official.merge(
        raw_ds,
        on=["pair_key", "diseaseId", "targetId", "datasourceId"],
        how="inner",
        validate="one_to_one",
    )
    if len(source) != len(official):
        raise RuntimeError(
            f"Official/raw datasource triplet mismatch: {len(official)} vs {len(source)}"
        )
    source["official_weighted"] = (
        source["official_datasource_score"] * source["weight"]
    )
    source["equal_weight"] = source["official_datasource_score"]
    source["raw_max_weighted"] = (
        source["raw_max_datasource_score"] * source["weight"]
    )
    source["observed_within_weighted"] = (
        source["observed_harmonic_datasource_score"] * source["weight"]
    )

    score_variants = pd.DataFrame(index=sorted(source["pair_key"].unique()))
    score_variants.index.name = "pair_key"
    score_variants["B01_EXACT_REPLAY"] = harmonic_group_score(
        source,
        value_col="official_weighted",
        fixed_normalizer=True,
    )
    score_variants["ABL_WEIGHT_EQUAL_ONLY"] = harmonic_group_score(
        source,
        value_col="equal_weight",
        fixed_normalizer=True,
    )
    score_variants["ABL_UPPER_NORMALIZER_OBSERVED_ONLY"] = harmonic_group_score(
        source,
        value_col="official_weighted",
        fixed_normalizer=False,
    )
    score_variants["ABL_UPPER_ARITHMETIC_WEIGHTED_ONLY"] = source.groupby(
        "pair_key", sort=False, observed=True
    )["official_weighted"].mean()
    score_variants["ABL_WITHIN_MAX_ONLY"] = harmonic_group_score(
        source,
        value_col="raw_max_weighted",
        fixed_normalizer=True,
    )
    score_variants["ABL_WITHIN_OBSERVED_HARMONIC_ONLY"] = harmonic_group_score(
        source,
        value_col="observed_within_weighted",
        fixed_normalizer=True,
    )
    score_variants = score_variants.reset_index()
    score_variants = baseline[
        [
            "candidate_id",
            "context_name",
            "diseaseId",
            "targetId",
            "pair_key",
            "associationScore",
            "t0_hard_negative",
            "common_baseline_abstention",
        ]
    ].merge(
        score_variants,
        on="pair_key",
        how="left",
        validate="one_to_one",
    )
    exact_error = (
        score_variants["B01_EXACT_REPLAY"] - score_variants["associationScore"]
    ).abs()
    max_exact_error = float(exact_error.max())
    if max_exact_error > 1e-12:
        raise RuntimeError(f"B01 exact replay mismatch: {max_exact_error}")

    score_columns = [
        "B01_EXACT_REPLAY",
        "ABL_WEIGHT_EQUAL_ONLY",
        "ABL_UPPER_NORMALIZER_OBSERVED_ONLY",
        "ABL_UPPER_ARITHMETIC_WEIGHTED_ONLY",
        "ABL_WITHIN_MAX_ONLY",
        "ABL_WITHIN_OBSERVED_HARMONIC_ONLY",
    ]
    score_variants["t0_hard_negative"] = as_bool(
        score_variants["t0_hard_negative"]
    )
    score_variants["common_baseline_abstention"] = as_bool(
        score_variants["common_baseline_abstention"]
    )
    cells = {}
    top_rows = []
    for context_id, context_frame in score_variants.groupby(
        "candidate_id", sort=True, observed=True
    ):
        eligible = context_frame.loc[
            context_frame["t0_hard_negative"]
            & ~context_frame["common_baseline_abstention"]
        ].copy()
        for score_column in score_columns:
            cell = build_cell(
                eligible,
                context_id=str(context_id),
                context_name=str(context_frame["context_name"].iloc[0]),
                disease_id=str(context_frame["diseaseId"].iloc[0]),
                realization_id=score_column,
                operator_code="B01",
                score_col=score_column,
                selected_col=None,
            )
            cells[(str(context_id), score_column)] = cell
            ordered = eligible.sort_values(
                [score_column, "targetId"],
                ascending=[False, True],
                kind="mergesort",
            ).head(BUDGET)
            for rank, (_, row) in enumerate(ordered.iterrows(), start=1):
                top_rows.append(
                    {
                        "candidate_id": context_id,
                        "context_name": row["context_name"],
                        "diseaseId": row["diseaseId"],
                        "ablation_id": score_column,
                        "rank": rank,
                        "targetId": row["targetId"],
                        "score": row[score_column],
                    }
                )

    comparison_rows = []
    for context_id in sorted(score_variants["candidate_id"].unique()):
        anchor = cells[(str(context_id), "B01_EXACT_REPLAY")]
        n_pool = int(
            score_variants.loc[
                score_variants["candidate_id"].eq(context_id)
                & score_variants["t0_hard_negative"]
                & ~score_variants["common_baseline_abstention"]
            ].shape[0]
        )
        chance_intersection = BUDGET * BUDGET / n_pool
        for score_column in score_columns[1:]:
            record = pair_record(
                cells[(str(context_id), score_column)],
                anchor,
                "B01_component_ablation",
            )
            record["ablation_id"] = score_column
            record["eligible_pool_size"] = n_pool
            record["chance_expected_intersection"] = chance_intersection
            record["chance_adjusted_stability_deterministic"] = (
                record["intersection_deterministic"] - chance_intersection
            ) / (BUDGET - chance_intersection)
            record["chance_adjusted_stability_expected_uniform_tie"] = (
                record["intersection_expected_uniform_tie"] - chance_intersection
            ) / (BUDGET - chance_intersection)
            comparison_rows.append(record)
    comparisons = pd.DataFrame(comparison_rows)
    summary = (
        comparisons.groupby("ablation_id", as_index=False, observed=True)
        .agg(
            contexts=("candidate_id", "size"),
            mean_substitution_deterministic=(
                "substitution_deterministic",
                "mean",
            ),
            mean_substitution_expected_uniform_tie=(
                "substitution_expected_uniform_tie",
                "mean",
            ),
            mean_substitution_lower_bound=("substitution_lower_bound", "mean"),
            mean_substitution_upper_bound=("substitution_upper_bound", "mean"),
            mean_chance_adjusted_stability_deterministic=(
                "chance_adjusted_stability_deterministic",
                "mean",
            ),
            mean_chance_adjusted_stability_expected_uniform_tie=(
                "chance_adjusted_stability_expected_uniform_tie",
                "mean",
            ),
        )
        .sort_values("mean_substitution_deterministic", ascending=False)
    )

    score_path = args.output_dir / "R17_B01_COMPONENT_ABLATION_SCORES.parquet"
    top_path = args.output_dir / "R17_B01_COMPONENT_ABLATION_TOP50.tsv"
    comparison_path = args.output_dir / "R17_B01_COMPONENT_ABLATION_BY_CONTEXT.tsv"
    summary_path = args.output_dir / "R17_B01_COMPONENT_ABLATION_SUMMARY.tsv"
    validation_path = args.output_dir / "R17_B01_EXACT_REPLAY_VALIDATION.tsv"
    score_variants.to_parquet(score_path, index=False, compression="zstd")
    pd.DataFrame(top_rows).to_csv(
        top_path, sep="\t", index=False, float_format="%.17g"
    )
    comparisons.to_csv(
        comparison_path, sep="\t", index=False, float_format="%.12g"
    )
    summary.to_csv(summary_path, sep="\t", index=False, float_format="%.12g")
    pd.DataFrame(
        [
            {
                "pair_count": len(score_variants),
                "maximum_absolute_score_error": max_exact_error,
                "tolerance": 1e-12,
                "status": "PASS" if max_exact_error <= 1e-12 else "FAIL",
            }
        ]
    ).to_csv(validation_path, sep="\t", index=False, float_format="%.17g")
    outputs = [score_path, top_path, comparison_path, summary_path, validation_path]
    receipt = {
        "analysis": "R17 B01 one-component-at-a-time ablation",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "contexts": 23,
        "target_context_pairs": len(score_variants),
        "datasource_triplets": len(source),
        "B01_exact_replay_max_abs_error": max_exact_error,
        "ablation_count": 5,
        "output_sha256": {path.name: sha256_file(path) for path in outputs},
    }
    receipt_path = args.output_dir / "R17_B01_COMPONENT_ABLATION_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
