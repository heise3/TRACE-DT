suppressPackageStartupMessages(library(arrow))
suppressPackageStartupMessages(library(data.table))

# Read-only sensitivity audit. This script does not recompute any of the 32
# scientific specifications. It reorders the frozen B01 association scores
# within exact ties and compares the resulting B01 lists with frozen top-50
# specification memberships.

args <- commandArgs(trailingOnly = TRUE)
script_arg <- commandArgs(trailingOnly = FALSE)
script_arg <- script_arg[grepl("^--file=", script_arg)]
if (length(script_arg) != 1L) stop("R16_B01_TIE_AUDIT_SCRIPT_PATH_NOT_RESOLVED")
script_path <- normalizePath(
  sub("^--file=", "", script_arg[[1]]),
  winslash = "/",
  mustWork = TRUE
)
artifact_root <- normalizePath(
  file.path(dirname(script_path), "..", ".."),
  winslash = "/",
  mustWork = TRUE
)
output_root <- if (length(args) >= 1L) {
  normalizePath(args[[1]], winslash = "/", mustWork = FALSE)
} else {
  file.path(artifact_root, "work", "b01_tie_sensitivity")
}
dir.create(output_root, recursive = TRUE, showWarnings = FALSE)

baseline_metric_path <- file.path(
  artifact_root,
  "data",
  "derived",
  "ot26_06",
  "t0_legal_unit_baseline_metrics.parquet"
)
frozen_baseline_list_path <- file.path(
  artifact_root,
  "data",
  "derived",
  "ot26_06",
  "baseline_b50_nominations.tsv"
)
operator_matrix_path <- file.path(
  artifact_root,
  "data",
  "derived",
  "ot26_06",
  "legal_unit_operator_status_matrix.parquet"
)

required_paths <- c(
  baseline_metric_path,
  frozen_baseline_list_path,
  operator_matrix_path
)
if (!all(file.exists(required_paths))) {
  stop(
    "R16_B01_TIE_AUDIT_MISSING_INPUT: ",
    paste(required_paths[!file.exists(required_paths)], collapse = " | ")
  )
}

baseline_metrics <- as.data.table(read_parquet(baseline_metric_path))
required_baseline_columns <- c(
  "candidate_id",
  "context_name",
  "diseaseId",
  "targetId",
  "associationScore",
  "t0_hard_negative",
  "common_baseline_abstention"
)
if (!all(required_baseline_columns %in% names(baseline_metrics))) {
  stop("R16_B01_TIE_AUDIT_BASELINE_SCHEMA_MISMATCH")
}

eligible <- baseline_metrics[
  t0_hard_negative == TRUE &
    common_baseline_abstention == FALSE &
    is.finite(associationScore)
]
if (uniqueN(eligible$candidate_id) != 23L) {
  stop("R16_B01_TIE_AUDIT_CONTEXT_COUNT_NOT_23")
}
if (eligible[, min(.N), by = candidate_id][, min(V1)] < 51L) {
  stop("R16_B01_TIE_AUDIT_CONTEXT_BELOW_51_ELIGIBLE_TARGETS")
}

ascending <- copy(eligible)
setorder(ascending, candidate_id, -associationScore, targetId)
ascending[, ascending_rank := seq_len(.N), by = candidate_id]

descending <- copy(eligible)
setorder(descending, candidate_id, -associationScore, -targetId)
descending[, reverse_id_rank := seq_len(.N), by = candidate_id]

ascending_top50 <- ascending[
  ascending_rank <= 50L,
  .(
    candidate_id,
    context_name,
    diseaseId,
    targetId,
    associationScore,
    ascending_rank
  )
]
descending_top50 <- descending[
  reverse_id_rank <= 50L,
  .(
    candidate_id,
    targetId,
    reverse_id_rank
  )
]

frozen_b01 <- fread(frozen_baseline_list_path)[
  baseline_id == "B01" &
    slot_status == "BASELINE_NOMINATION",
  .(
    candidate_id,
    targetId,
    frozen_slot = as.integer(slot),
    frozen_metric_value = as.numeric(metric_value)
  )
]

frozen_reconciliation <- merge(
  frozen_b01,
  ascending_top50[
    ,
    .(
      candidate_id,
      targetId,
      ascending_rank,
      associationScore
    )
  ],
  by = c("candidate_id", "targetId"),
  all = TRUE,
  sort = TRUE
)

frozen_set_exact <- (
  nrow(frozen_reconciliation) == 1150L &&
    all(!is.na(frozen_reconciliation$frozen_slot)) &&
    all(!is.na(frozen_reconciliation$ascending_rank))
)
frozen_slot_exact <- (
  frozen_set_exact &&
    all(frozen_reconciliation$frozen_slot ==
          frozen_reconciliation$ascending_rank)
)
frozen_score_max_abs_error <- max(
  abs(
    frozen_reconciliation$frozen_metric_value -
      frozen_reconciliation$associationScore
  ),
  na.rm = TRUE
)
if (
  !frozen_set_exact ||
    !frozen_slot_exact ||
    !is.finite(frozen_score_max_abs_error) ||
    frozen_score_max_abs_error > 1e-12
) {
  stop("R16_B01_TIE_AUDIT_FROZEN_B01_RECONCILIATION_FAILED")
}

context_audit <- ascending[
  ,
  {
    score_50 <- associationScore[[50L]]
    score_51 <- associationScore[[51L]]
    ascending_ids <- targetId[seq_len(50L)]
    reverse_ids <- descending_top50[
      candidate_id == .BY$candidate_id,
      targetId
    ]
    tie_mask <- associationScore == score_50
    intersection_count <- length(intersect(ascending_ids, reverse_ids))
    list(
      context_name = context_name[[1L]],
      diseaseId = diseaseId[[1L]],
      scored_hard_negative_targets = .N,
      rank50_score = score_50,
      rank51_score = score_51,
      rank50_51_margin = score_50 - score_51,
      exact_cutoff_tie = score_50 == score_51,
      cutoff_tie_block_size = sum(tie_mask),
      cutoff_tie_inside_top50 = sum(tie_mask & ascending_rank <= 50L),
      cutoff_tie_outside_top50 = sum(tie_mask & ascending_rank > 50L),
      ascending_vs_reverse_intersection = intersection_count,
      reverse_id_substitution = 1 - intersection_count / 50
    )
  },
  by = candidate_id
]
setorder(context_audit, candidate_id)
context_audit[
  ,
  `:=`(
    frozen_b01_set_reproduced = frozen_set_exact,
    frozen_b01_slot_order_reproduced = frozen_slot_exact,
    frozen_metric_max_abs_error = frozen_score_max_abs_error
  )
]

operator_memberships <- as.data.table(read_parquet(operator_matrix_path))[
  selected_top50 == TRUE,
  .(
    candidate_id,
    context_name,
    diseaseId,
    realization_id,
    operator_code,
    targetId
  )
]
if (
  nrow(operator_memberships) != 36800L ||
    uniqueN(
      operator_memberships,
      by = c("candidate_id", "realization_id", "targetId")
    ) != 36800L
) {
  stop("R16_B01_TIE_AUDIT_OPERATOR_MEMBERSHIP_DIMENSION_FAILED")
}

ascending_flags <- ascending_top50[
  ,
  .(
    candidate_id,
    targetId,
    in_b01_ascending = TRUE
  )
]
descending_flags <- descending_top50[
  ,
  .(
    candidate_id,
    targetId,
    in_b01_reverse = TRUE
  )
]

comparison_rows <- merge(
  operator_memberships,
  ascending_flags,
  by = c("candidate_id", "targetId"),
  all.x = TRUE,
  sort = FALSE
)
comparison_rows <- merge(
  comparison_rows,
  descending_flags,
  by = c("candidate_id", "targetId"),
  all.x = TRUE,
  sort = FALSE
)
comparison_rows[is.na(in_b01_ascending), in_b01_ascending := FALSE]
comparison_rows[is.na(in_b01_reverse), in_b01_reverse := FALSE]

comparison_cells <- comparison_rows[
  ,
  .(
    b01_ascending_overlap = sum(in_b01_ascending),
    b01_reverse_overlap = sum(in_b01_reverse)
  ),
  by = .(
    candidate_id,
    context_name,
    diseaseId,
    realization_id,
    operator_code
  )
]
comparison_cells[
  ,
  `:=`(
    b01_ascending_substitution =
      1 - b01_ascending_overlap / 50,
    b01_reverse_substitution =
      1 - b01_reverse_overlap / 50,
    b01_distance_shift =
      (b01_ascending_overlap - b01_reverse_overlap) / 50
  )
]
comparison_cells <- merge(
  comparison_cells,
  context_audit[
    ,
    .(
      candidate_id,
      b01_list_reverse_substitution = reverse_id_substitution,
      exact_b01_cutoff_tie = exact_cutoff_tie,
      b01_cutoff_tie_block_size = cutoff_tie_block_size
    )
  ],
  by = "candidate_id",
  all.x = TRUE,
  sort = FALSE
)
setorder(comparison_cells, candidate_id, realization_id)

if (
  nrow(comparison_cells) != 736L ||
    uniqueN(
      comparison_cells,
      by = c("candidate_id", "realization_id")
    ) != 736L
) {
  stop("R16_B01_TIE_AUDIT_COMPARISON_CELL_COUNT_NOT_736")
}

summary_metrics <- data.table(
  metric = c(
    "frozen_b01_target_sets_reproduced",
    "frozen_b01_slot_orders_reproduced",
    "frozen_b01_metric_max_abs_error",
    "contexts",
    "contexts_with_exact_rank50_51_tie",
    "contexts_with_reverse_id_membership_change",
    "mean_b01_list_reverse_id_substitution",
    "median_b01_list_reverse_id_substitution",
    "maximum_b01_list_reverse_id_substitution",
    "comparison_cells",
    "mean_specification_to_b01_distance_ascending_id",
    "median_specification_to_b01_distance_ascending_id",
    "minimum_specification_to_b01_distance_ascending_id",
    "maximum_specification_to_b01_distance_ascending_id",
    "mean_specification_to_b01_distance_reverse_id",
    "median_specification_to_b01_distance_reverse_id",
    "minimum_specification_to_b01_distance_reverse_id",
    "maximum_specification_to_b01_distance_reverse_id",
    "mean_distance_shift_reverse_minus_ascending",
    "median_distance_shift_reverse_minus_ascending",
    "minimum_distance_shift_reverse_minus_ascending",
    "maximum_distance_shift_reverse_minus_ascending",
    "comparison_cells_with_distance_change",
    "comparison_cells_with_distance_increase",
    "comparison_cells_with_distance_decrease"
  ),
  value = as.character(c(
    frozen_set_exact,
    frozen_slot_exact,
    format(frozen_score_max_abs_error, scientific = TRUE, digits = 17),
    nrow(context_audit),
    sum(context_audit$exact_cutoff_tie),
    sum(context_audit$reverse_id_substitution > 0),
    format(mean(context_audit$reverse_id_substitution), digits = 17),
    format(median(context_audit$reverse_id_substitution), digits = 17),
    format(max(context_audit$reverse_id_substitution), digits = 17),
    nrow(comparison_cells),
    format(mean(comparison_cells$b01_ascending_substitution), digits = 17),
    format(median(comparison_cells$b01_ascending_substitution), digits = 17),
    format(min(comparison_cells$b01_ascending_substitution), digits = 17),
    format(max(comparison_cells$b01_ascending_substitution), digits = 17),
    format(mean(comparison_cells$b01_reverse_substitution), digits = 17),
    format(median(comparison_cells$b01_reverse_substitution), digits = 17),
    format(min(comparison_cells$b01_reverse_substitution), digits = 17),
    format(max(comparison_cells$b01_reverse_substitution), digits = 17),
    format(mean(comparison_cells$b01_distance_shift), digits = 17),
    format(median(comparison_cells$b01_distance_shift), digits = 17),
    format(min(comparison_cells$b01_distance_shift), digits = 17),
    format(max(comparison_cells$b01_distance_shift), digits = 17),
    sum(comparison_cells$b01_distance_shift != 0),
    sum(comparison_cells$b01_distance_shift > 0),
    sum(comparison_cells$b01_distance_shift < 0)
  )),
  denominator_or_scope = c(
    "1150 frozen B01 nominations",
    "1150 frozen B01 nomination slots",
    "1150 frozen B01 metric values",
    "frozen cancer-context universe",
    "23 contexts",
    "23 contexts",
    "23 contexts",
    "23 contexts",
    "23 contexts",
    "23 contexts x 32 specifications",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells",
    "736 cells"
  )
)
summary_metrics[
  ,
  audit_definition := paste(
    "B01: associationScore descending;",
    "primary tie rule: targetId ascending;",
    "sensitivity: targetId descending within exact score ties;",
    "specification memberships read from the frozen R16 matrix"
  )
]

dir.create(output_root, recursive = TRUE, showWarnings = FALSE)
fwrite(
  context_audit,
  file.path(output_root, "R16_B01_TIE_SENSITIVITY_BY_CONTEXT.tsv"),
  sep = "\t",
  quote = FALSE,
  na = ""
)
fwrite(
  summary_metrics,
  file.path(output_root, "R16_B01_TIE_SENSITIVITY_SUMMARY.tsv"),
  sep = "\t",
  quote = FALSE,
  na = ""
)
fwrite(
  comparison_cells,
  file.path(output_root, "R16_B01_TIE_SENSITIVITY_COMPARISON_CELLS.tsv"),
  sep = "\t",
  quote = FALSE,
  na = ""
)

cat("R16_B01_TIE_SENSITIVITY_AUDIT=PASS\n")
cat("CONTEXT_ROWS=", nrow(context_audit), "\n", sep = "")
cat("EXACT_CUTOFF_TIE_CONTEXTS=", sum(context_audit$exact_cutoff_tie), "\n", sep = "")
cat("COMPARISON_ROWS=", nrow(comparison_cells), "\n", sep = "")
cat(
  "MEAN_B01_LIST_REVERSE_SUBSTITUTION=",
  format(mean(context_audit$reverse_id_substitution), digits = 17),
  "\n",
  sep = ""
)
cat(
  "MEAN_B01_DISTANCE_ASCENDING=",
  format(mean(comparison_cells$b01_ascending_substitution), digits = 17),
  "\n",
  sep = ""
)
cat(
  "MEAN_B01_DISTANCE_REVERSE=",
  format(mean(comparison_cells$b01_reverse_substitution), digits = 17),
  "\n",
  sep = ""
)
cat(
  "MEAN_DISTANCE_SHIFT=",
  format(mean(comparison_cells$b01_distance_shift), digits = 17),
  "\n",
  sep = ""
)
