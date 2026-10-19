suppressPackageStartupMessages({
  library(arrow)
  library(data.table)
  library(digest)
})
arrow::set_cpu_count(1L)
arrow::set_io_thread_count(1L)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 8L) {
  stop(
    "Usage: Rscript verify_cleanroom_parity.R ",
    "--rebuilt MATRIX --reference MATRIX --context-id ID --output TSV"
  )
}
lookup <- setNames(args[c(2L, 4L, 6L, 8L)], sub("^--", "", args[c(1L, 3L, 5L, 7L)]))
required <- c("rebuilt", "reference", "context-id", "output")
if (!all(required %in% names(lookup))) stop("PARITY_FAIL_REQUIRED_ARGUMENTS")

rebuilt_path <- normalizePath(lookup[["rebuilt"]], winslash = "/", mustWork = TRUE)
reference_path <- normalizePath(lookup[["reference"]], winslash = "/", mustWork = TRUE)
output_path <- normalizePath(lookup[["output"]], winslash = "/", mustWork = FALSE)
context_id <- lookup[["context-id"]]

columns <- c(
  "candidate_id", "context_name", "diseaseId", "targetId",
  "realization_id", "operator_code", "operator_status", "operator_score",
  "operator_rank", "selected_top50", "survival_normalized_rank",
  "t0_primary_hard_positive", "t0_hard_negative", "positive_raw_rows"
)
rebuilt <- as.data.table(read_parquet(rebuilt_path, col_select = columns))
reference <- as.data.table(read_parquet(reference_path, col_select = columns))
reference <- reference[candidate_id == context_id]
if (nrow(rebuilt) == 0L || nrow(reference) == 0L) {
  stop("PARITY_FAIL_EMPTY_CONTEXT")
}
keys <- c("candidate_id", "realization_id", "targetId")
setkeyv(rebuilt, keys)
setkeyv(reference, keys)
if (nrow(rebuilt) != nrow(reference) || anyDuplicated(rebuilt, by = keys) ||
    anyDuplicated(reference, by = keys)) {
  stop("PARITY_FAIL_DIMENSION_OR_KEY")
}
joined <- merge(
  rebuilt,
  reference,
  by = keys,
  suffixes = c("_rebuilt", "_reference"),
  all = TRUE,
  sort = TRUE
)

same_text <- function(field) {
  left <- joined[[paste0(field, "_rebuilt")]]
  right <- joined[[paste0(field, "_reference")]]
  all(ifelse(is.na(left), "", as.character(left)) ==
      ifelse(is.na(right), "", as.character(right)))
}
same_number <- function(field, tolerance = 0) {
  left <- as.numeric(joined[[paste0(field, "_rebuilt")]])
  right <- as.numeric(joined[[paste0(field, "_reference")]])
  same_na <- is.na(left) & is.na(right)
  finite <- is.finite(left) & is.finite(right)
  all(same_na | (finite & abs(left - right) <= tolerance))
}

cell_rows <- joined[, .(
  rows = .N,
  operator_status_exact = all(operator_status_rebuilt == operator_status_reference),
  operator_score_max_abs_difference = {
    difference <- abs(operator_score_rebuilt - operator_score_reference)
    if (any(is.finite(difference))) max(difference, na.rm = TRUE) else 0
  },
  operator_rank_exact = all(
    fifelse(is.na(operator_rank_rebuilt), -1L, operator_rank_rebuilt) ==
      fifelse(is.na(operator_rank_reference), -1L, operator_rank_reference)
  ),
  selected_top50_exact = all(selected_top50_rebuilt == selected_top50_reference),
  survival_normalized_rank_max_abs_difference =
    max(abs(survival_normalized_rank_rebuilt -
      survival_normalized_rank_reference), na.rm = TRUE),
  exclusion_flag_exact = all(
    t0_primary_hard_positive_rebuilt == t0_primary_hard_positive_reference
  ),
  hard_negative_flag_exact = all(
    t0_hard_negative_rebuilt == t0_hard_negative_reference
  ),
  positive_raw_rows_exact = all(
    positive_raw_rows_rebuilt == positive_raw_rows_reference
  )
), by = .(
  candidate_id,
  realization_id,
  operator_code = operator_code_rebuilt
)]
cell_rows[, parity_pass := (
  operator_status_exact &
  operator_score_max_abs_difference <= 1e-14 &
  operator_rank_exact &
  selected_top50_exact &
  survival_normalized_rank_max_abs_difference <= 1e-14 &
  exclusion_flag_exact &
  hard_negative_flag_exact &
  positive_raw_rows_exact
)]
setorder(cell_rows, realization_id)

global_checks <- c(
  same_text("context_name"),
  same_text("diseaseId"),
  same_text("operator_code"),
  same_text("operator_status"),
  same_number("operator_score", 1e-14),
  same_number("operator_rank", 0),
  same_text("selected_top50"),
  same_number("survival_normalized_rank", 1e-14),
  same_text("t0_primary_hard_positive"),
  same_text("t0_hard_negative"),
  same_number("positive_raw_rows", 0)
)
if (nrow(cell_rows) != 32L || !all(cell_rows$parity_pass) || !all(global_checks)) {
  stop("PARITY_FAIL_CLEANROOM_MATRIX_MISMATCH")
}

dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
write.table(
  cell_rows,
  output_path,
  sep = "\t",
  row.names = FALSE,
  col.names = TRUE,
  quote = FALSE,
  na = "",
  fileEncoding = "UTF-8"
)
receipt_path <- sub("\\.tsv$", ".md", output_path, ignore.case = TRUE)
writeLines(
  c(
    "# TRACE-DT clean-room one-context all-32 parity",
    "",
    paste0("- Context: `", context_id, "`."),
    paste0("- Rebuilt rows: `", nrow(rebuilt), "`."),
    paste0("- Specification cells: `", nrow(cell_rows), "/32` PASS."),
    "- Key: `candidate_id + realization_id + targetId`.",
    "- State, exclusion flags, ranks and top-50 membership: exact.",
    paste0(
      "- Maximum operator-score absolute difference: `",
      format(max(cell_rows$operator_score_max_abs_difference), scientific = TRUE),
      "`."
    ),
    paste0(
      "- Maximum normalized-rank absolute difference: `",
      format(
        max(cell_rows$survival_normalized_rank_max_abs_difference),
        scientific = TRUE
      ),
      "`."
    ),
    "- Decision: `PASS_CLEANROOM_ONE_CONTEXT_ALL32_PARITY`.",
    "- T1: `NOT_ACCESSED_NOT_REQUIRED`.",
    "",
    "The official input release root is not redistributed. The rebuilt temporary",
    "matrix is intentionally excluded from the reviewer artifact; this compact",
    "cell receipt is distributed with the executable command needed to repeat it."
  ),
  receipt_path,
  useBytes = TRUE
)
cat("PASS_CLEANROOM_ONE_CONTEXT_ALL32_PARITY\n")
cat("receipt=", output_path, "\n", sep = "")
cat("receipt_sha256=", digest(output_path, algo = "sha256", file = TRUE), "\n", sep = "")
