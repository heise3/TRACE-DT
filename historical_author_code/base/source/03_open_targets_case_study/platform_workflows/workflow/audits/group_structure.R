suppressPackageStartupMessages({
  library(arrow)
  library(data.table)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 1L) {
  stop("Usage: Rscript group_structure.R [output_directory]")
}
script_arg <- commandArgs(trailingOnly = FALSE)
script_arg <- script_arg[grepl("^--file=", script_arg)]
if (length(script_arg) != 1L) stop("R16_GROUP_AUDIT_SCRIPT_PATH_NOT_RESOLVED")
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
derived_root <- file.path(artifact_root, "data", "derived", "ot26_06")
operator_input_path <- file.path(derived_root, "formal_operator_input.parquet")
legal_metrics_path <- file.path(
  derived_root,
  "t0_legal_unit_baseline_metrics.parquet"
)
survival_path <- file.path(derived_root, "target_context_survival_table.parquet")
output_directory <- if (length(args) == 1L) {
  normalizePath(args[[1]], winslash = "/", mustWork = FALSE)
} else {
  file.path(artifact_root, "work", "group_structure")
}
if (!all(file.exists(c(
  operator_input_path,
  legal_metrics_path,
  survival_path
)))) {
  stop("R16_GROUP_AUDIT_REQUIRED_ARTIFACT_INPUT_MISSING")
}
dir.create(output_directory, recursive = TRUE, showWarnings = FALSE)

records <- as.data.table(read_parquet(operator_input_path))
legal <- as.data.table(read_parquet(legal_metrics_path))
survival <- as.data.table(read_parquet(survival_path))

required_record_fields <- c(
  "pair_key", "diseaseId", "targetId", "datasourceId",
  "canonical_key", "ancestry_group_id"
)
required_legal_fields <- c(
  "candidate_id", "context_name", "pair_key", "t0_hard_negative",
  "t0_primary_hard_positive"
)
required_survival_fields <- c(
  "candidate_id", "diseaseId", "targetId", "selection_count"
)
stopifnot(
  all(required_record_fields %in% names(records)),
  all(required_legal_fields %in% names(legal)),
  all(required_survival_fields %in% names(survival))
)

records[, `:=`(
  datasourceId = as.character(datasourceId),
  canonical_key = fifelse(
    is.na(canonical_key), "", as.character(canonical_key)
  ),
  ancestry_group_id = fifelse(
    is.na(ancestry_group_id), "", as.character(ancestry_group_id)
  )
)]

pair_flags <- legal[, .(
  candidate_id,
  context_name,
  pair_key,
  hard_negative = as.logical(t0_hard_negative),
  primary_hard_evidence_excluded = as.logical(t0_primary_hard_positive)
)]
survival_flags <- survival[, .(
  candidate_id,
  pair_key = paste(diseaseId, targetId, sep = "::"),
  selection_count = as.integer(selection_count),
  ever_selected = as.integer(selection_count) > 0L,
  selected_ge26 = as.integer(selection_count) >= 26L
)]
pair_flags <- merge(
  pair_flags,
  survival_flags[, .(
    pair_key, selection_count, ever_selected, selected_ge26
  )],
  by = "pair_key",
  all.x = TRUE,
  sort = FALSE
)
pair_flags[is.na(selection_count), `:=`(
  selection_count = 0L,
  ever_selected = FALSE,
  selected_ge26 = FALSE
)]

make_group_units <- function(grouping, collapse_canonical) {
  current <- copy(records)
  if (grouping == "datasource") {
    current[, group_id := paste0("DATASOURCE::", datasourceId)]
    current[, unresolved_group := FALSE]
  } else {
    current[, group_id := paste0("PROVENANCE::", ancestry_group_id)]
    current[, unresolved_group := !nzchar(ancestry_group_id)]
  }

  current <- current[unresolved_group == FALSE]
  if (collapse_canonical) {
    current <- current[nzchar(canonical_key)]
    group_units <- current[, .(
      unit_count = uniqueN(canonical_key)
    ), by = .(pair_key, group_id)]
  } else {
    group_units <- current[, .(
      unit_count = .N
    ), by = .(pair_key, group_id)]
  }

  group_units[, `:=`(
    grouping = grouping,
    row_collapse = ifelse(collapse_canonical, "canonical-unit", "raw-row"),
    singleton_group = unit_count == 1L
  )]
  group_units[]
}

group_units <- rbindlist(
  list(
    make_group_units("datasource", FALSE),
    make_group_units("datasource", TRUE),
    make_group_units("provenance", FALSE),
    make_group_units("provenance", TRUE)
  ),
  use.names = TRUE
)
group_units <- merge(
  group_units,
  pair_flags,
  by = "pair_key",
  all.x = TRUE,
  sort = FALSE
)

pair_structure <- group_units[, .(
  group_count = .N,
  mean_units_per_group = as.numeric(mean(unit_count)),
  median_units_per_group = as.numeric(median(unit_count)),
  maximum_units_per_group = as.numeric(max(unit_count)),
  singleton_group_fraction = mean(singleton_group),
  all_groups_singleton = all(singleton_group)
), by = .(
  pair_key, candidate_id, context_name, hard_negative,
  primary_hard_evidence_excluded, selection_count, ever_selected,
  selected_ge26, grouping, row_collapse
)]

add_stratum <- function(value, label) {
  copy(value)[, stratum := label]
}
stratified <- rbindlist(
  list(
    add_stratum(pair_structure[hard_negative == TRUE], "all_hard_negative"),
    add_stratum(
      pair_structure[hard_negative == TRUE & ever_selected == TRUE],
      "ever_selected_1plus_of_32"
    ),
    add_stratum(
      pair_structure[hard_negative == TRUE & selected_ge26 == TRUE],
      "selected_26plus_of_32"
    )
  ),
  use.names = TRUE
)

summarise_structure <- function(value, by_context = FALSE) {
  grouping_fields <- c("stratum", "grouping", "row_collapse")
  if (by_context) {
    grouping_fields <- c("candidate_id", "context_name", grouping_fields)
  }
  value[, .(
    target_context_pairs = .N,
    median_group_count = as.numeric(median(group_count)),
    q25_group_count = as.numeric(quantile(
      group_count, 0.25, names = FALSE
    )),
    q75_group_count = as.numeric(quantile(
      group_count, 0.75, names = FALSE
    )),
    median_mean_units_per_group = as.numeric(median(mean_units_per_group)),
    q25_mean_units_per_group = as.numeric(quantile(
      mean_units_per_group, 0.25, names = FALSE
    )),
    q75_mean_units_per_group = as.numeric(quantile(
      mean_units_per_group, 0.75, names = FALSE
    )),
    pairs_with_all_groups_singleton = sum(all_groups_singleton),
    fraction_pairs_with_all_groups_singleton = mean(all_groups_singleton),
    median_singleton_group_fraction = as.numeric(
      median(singleton_group_fraction)
    ),
    maximum_units_per_group = as.numeric(max(maximum_units_per_group))
  ), by = grouping_fields]
}

global_summary <- summarise_structure(stratified, FALSE)
context_summary <- summarise_structure(stratified, TRUE)

setorder(
  global_summary,
  stratum,
  grouping,
  row_collapse
)
setorder(
  context_summary,
  candidate_id,
  stratum,
  grouping,
  row_collapse
)
setorder(
  pair_structure,
  candidate_id,
  grouping,
  row_collapse,
  pair_key
)

fwrite(
  global_summary,
  file.path(output_directory, "R16_GROUP_STRUCTURE_GLOBAL_SUMMARY.tsv"),
  sep = "\t",
  quote = FALSE,
  na = "NA"
)
fwrite(
  context_summary,
  file.path(output_directory, "R16_GROUP_STRUCTURE_BY_CONTEXT.tsv"),
  sep = "\t",
  quote = FALSE,
  na = "NA"
)
write_parquet(
  as.data.frame(pair_structure),
  file.path(output_directory, "R16_GROUP_STRUCTURE_PAIR_LEVEL.parquet"),
  compression = "zstd"
)

cat(
  "R16_GROUP_STRUCTURE_AUDIT_COMPLETE\n",
  "record_rows=", nrow(records), "\n",
  "pair_structure_rows=", nrow(pair_structure), "\n",
  "global_summary_rows=", nrow(global_summary), "\n",
  "context_summary_rows=", nrow(context_summary), "\n",
  sep = ""
)
