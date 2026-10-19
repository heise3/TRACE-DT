parse_cli <- function(args) {
  values <- list()
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (!startsWith(key, "--")) stop("CLI_FAIL_EXPECTED_OPTION_", key)
    key <- sub("^--", "", key)
    if (i == length(args) || startsWith(args[[i + 1L]], "--")) {
      values[[key]] <- TRUE
      i <- i + 1L
    } else {
      values[[key]] <- args[[i + 1L]]
      i <- i + 2L
    }
  }
  values
}

script_arg <- commandArgs(trailingOnly = FALSE)
script_arg <- script_arg[grepl("^--file=", script_arg)]
if (length(script_arg) != 1L) stop("CLI_FAIL_SCRIPT_PATH_NOT_RESOLVED")
script_path <- normalizePath(
  sub("^--file=", "", script_arg[[1]]),
  winslash = "/",
  mustWork = TRUE
)
artifact_root <- normalizePath(
  file.path(dirname(script_path), ".."),
  winslash = "/",
  mustWork = TRUE
)
cli <- parse_cli(commandArgs(trailingOnly = TRUE))

contracts_root <- file.path(artifact_root, "contracts")
operator_contract_path <- file.path(
  contracts_root,
  "specification_realizations_32.tsv"
)
baseline_contract_path <- file.path(contracts_root, "baseline_registry_6.tsv")
key_registry_path <- file.path(
  contracts_root,
  "R16_CANONICAL_KEY_PROVENANCE_CONTRACT.tsv"
)
source_config_path <- file.path(contracts_root, "datasource_registry_20.tsv")
universe_path <- file.path(contracts_root, "context_identifier_contract_23.tsv")
mapping_metadata_path <- file.path(
  contracts_root,
  "provenance_mapping_metadata.tsv"
)
hard_rules_path <- file.path(
  artifact_root,
  "src",
  "trace_dt",
  "hard_evidence_rules_v1.R"
)
mapping_path <- if (!is.null(cli[["provenance-mapping"]])) {
  normalizePath(
    as.character(cli[["provenance-mapping"]]),
    winslash = "/",
    mustWork = TRUE
  )
} else {
  file.path(
    artifact_root,
    "data",
    "derived",
    "ot26_06",
    "source_unit_provenance_mapping.parquet"
  )
}

preflight_read_tsv <- function(path, ...) {
  read.delim(
    path,
    sep = "\t",
    quote = "",
    stringsAsFactors = FALSE,
    check.names = FALSE,
    fileEncoding = "UTF-8",
    ...
  )
}

preflight_require_fields <- function(value, required, label) {
  missing_fields <- setdiff(required, names(value))
  if (length(missing_fields) > 0L) {
    stop(
      "CONTRACT_PREFLIGHT_FAIL_", label, "_FIELDS_",
      paste(missing_fields, collapse = ",")
    )
  }
}

preflight_package_versions <- c(
  arrow = "24.0.0",
  data.table = "1.18.4",
  digest = "0.6.39",
  dplyr = "1.2.1",
  jsonlite = "2.0.0"
)

run_contract_preflight <- function() {
  cat("TRACE_DT_V11_CONTRACT_PREFLIGHT\n")
  cat("MODE=CONTRACTS_ONLY_NO_RAW_INPUTS\n")
  cat("ARTIFACT_ROOT=", artifact_root, "\n", sep = "")

  dependency_paths <- c(
    operator_contract = operator_contract_path,
    baseline_contract = baseline_contract_path,
    canonical_key_contract = key_registry_path,
    datasource_contract = source_config_path,
    context_contract = universe_path,
    provenance_mapping_metadata = mapping_metadata_path,
    hard_evidence_rules = hard_rules_path,
    provenance_mapping = mapping_path
  )
  missing_paths <- names(dependency_paths)[
    !file.exists(unname(dependency_paths))
  ]
  if (length(missing_paths) > 0L) {
    stop(
      "CONTRACT_PREFLIGHT_FAIL_MISSING_FILES_",
      paste(missing_paths, collapse = ",")
    )
  }
  zero_byte_paths <- names(dependency_paths)[
    file.info(unname(dependency_paths))$size <= 0
  ]
  if (length(zero_byte_paths) > 0L) {
    stop(
      "CONTRACT_PREFLIGHT_FAIL_ZERO_BYTE_FILES_",
      paste(zero_byte_paths, collapse = ",")
    )
  }

  installed_versions <- vapply(
    names(preflight_package_versions),
    function(package_name) {
      description <- tryCatch(
        utils::packageDescription(package_name),
        error = function(e) NULL,
        warning = function(w) NULL
      )
      if (is.null(description) || is.null(description$Version)) return(NA_character_)
      as.character(description$Version)
    },
    character(1)
  )
  missing_packages <- names(installed_versions)[is.na(installed_versions)]
  if (length(missing_packages) > 0L) {
    stop(
      "CONTRACT_PREFLIGHT_FAIL_MISSING_R_PACKAGES_",
      paste(missing_packages, collapse = ",")
    )
  }
  wrong_versions <- names(installed_versions)[
    installed_versions != preflight_package_versions[names(installed_versions)]
  ]
  if (length(wrong_versions) > 0L) {
    detail <- paste0(
      wrong_versions,
      "=",
      installed_versions[wrong_versions],
      "_EXPECTED_",
      preflight_package_versions[wrong_versions]
    )
    stop(
      "CONTRACT_PREFLIGHT_FAIL_R_PACKAGE_VERSIONS_",
      paste(detail, collapse = ",")
    )
  }

  operator_contract <- preflight_read_tsv(
    operator_contract_path,
    colClasses = c(operator_code = "character")
  )
  preflight_require_fields(
    operator_contract,
    c("realization_id", "operator_code", "O1", "O2", "O3", "O4", "O5"),
    "OPERATOR_CONTRACT"
  )
  expected_operator_codes <- vapply(
    0:31,
    function(value) paste0(as.integer(intToBits(value))[5:1], collapse = ""),
    character(1)
  )
  if (
    nrow(operator_contract) != 32L ||
    !identical(operator_contract$operator_code, expected_operator_codes) ||
    anyDuplicated(operator_contract$realization_id) > 0L
  ) {
    stop("CONTRACT_PREFLIGHT_FAIL_OPERATOR_CONTRACT_NOT_EXACT_32")
  }

  baseline_contract <- preflight_read_tsv(baseline_contract_path)
  preflight_require_fields(
    baseline_contract,
    c("baseline_id", "baseline_name", "legal_unit", "metric", "budget"),
    "BASELINE_CONTRACT"
  )
  if (
    nrow(baseline_contract) != 6L ||
    anyDuplicated(baseline_contract$baseline_id) > 0L
  ) {
    stop("CONTRACT_PREFLIGHT_FAIL_BASELINE_CONTRACT_NOT_EXACT_6")
  }

  key_contract <- preflight_read_tsv(key_registry_path)
  preflight_require_fields(
    key_contract,
    c(
      "datasource_id",
      "local_dataset",
      "key_tier_priority_first_complete_wins",
      "mapping_join_key"
    ),
    "CANONICAL_KEY_CONTRACT"
  )
  if (
    nrow(key_contract) != 20L ||
    anyDuplicated(key_contract$datasource_id) > 0L
  ) {
    stop("CONTRACT_PREFLIGHT_FAIL_CANONICAL_KEY_CONTRACT_NOT_EXACT_20")
  }

  source_contract <- preflight_read_tsv(source_config_path)
  preflight_require_fields(
    source_contract,
    c("datasourceId", "datatypeId", "weight", "toPropagate"),
    "DATASOURCE_CONTRACT"
  )
  if (
    nrow(source_contract) != 20L ||
    anyDuplicated(source_contract$datasourceId) > 0L ||
    !setequal(source_contract$datasourceId, key_contract$datasource_id)
  ) {
    stop("CONTRACT_PREFLIGHT_FAIL_DATASOURCE_CONTRACT_NOT_EXACT_20")
  }

  context_contract <- preflight_read_tsv(universe_path)
  preflight_require_fields(
    context_contract,
    c("candidate_id", "context_name", "open_targets_disease_id"),
    "CONTEXT_CONTRACT"
  )
  if (
    nrow(context_contract) != 23L ||
    anyDuplicated(context_contract$candidate_id) > 0L ||
    anyDuplicated(context_contract$open_targets_disease_id) > 0L
  ) {
    stop("CONTRACT_PREFLIGHT_FAIL_CONTEXT_CONTRACT_NOT_EXACT_23")
  }

  mapping_metadata <- preflight_read_tsv(mapping_metadata_path)
  preflight_require_fields(
    mapping_metadata,
    c("row_count", "row_group_count", "byte_size", "sha256", "columns_pipe"),
    "PROVENANCE_MAPPING_METADATA"
  )
  if (nrow(mapping_metadata) != 1L) {
    stop("CONTRACT_PREFLIGHT_FAIL_PROVENANCE_MAPPING_METADATA_NOT_ONE_ROW")
  }
  expected_mapping_fields <- c(
    "datasourceId",
    "local_dataset",
    "r04_canonical_key",
    "r04_key_tier",
    "source_unit_node_id",
    "ancestry_group_id",
    "raw_row_count",
    "pair_unit_count",
    "linked_artifact_count",
    "primary_artifact_count",
    "linked_publication_count",
    "linked_artifact_types",
    "cross_source_ancestry_group",
    "resolution_status",
    "forced_abstention_reason",
    "import_parent_node_id",
    "checked_date"
  )
  if (
    as.integer(mapping_metadata$row_count[[1]]) != 528893L ||
    as.integer(mapping_metadata$row_group_count[[1]]) != 19L ||
    as.numeric(mapping_metadata$byte_size[[1]]) != file.info(mapping_path)$size ||
    !identical(
      strsplit(mapping_metadata$columns_pipe[[1]], "|", fixed = TRUE)[[1]],
      expected_mapping_fields
    )
  ) {
    stop("CONTRACT_PREFLIGHT_FAIL_PROVENANCE_MAPPING_METADATA")
  }
  actual_mapping_sha256 <- digest::digest(
    mapping_path,
    algo = "sha256",
    file = TRUE,
    serialize = FALSE
  )
  if (!identical(actual_mapping_sha256, mapping_metadata$sha256[[1]])) {
    stop("CONTRACT_PREFLIGHT_FAIL_PROVENANCE_MAPPING_SHA256")
  }
  mapping_connection <- file(mapping_path, open = "rb")
  on.exit(close(mapping_connection), add = TRUE)
  parquet_magic <- rawToChar(readBin(mapping_connection, what = "raw", n = 4L))
  if (!identical(parquet_magic, "PAR1")) {
    stop("CONTRACT_PREFLIGHT_FAIL_PROVENANCE_MAPPING_NOT_PARQUET")
  }

  hard_rule_environment <- new.env(parent = baseenv())
  sys.source(hard_rules_path, envir = hard_rule_environment)
  if (length(ls(hard_rule_environment, all.names = TRUE)) == 0L) {
    stop("CONTRACT_PREFLIGHT_FAIL_HARD_RULES_EMPTY")
  }

  for (package_name in names(installed_versions)) {
    cat(
      "R_PACKAGE_", toupper(gsub("[.]", "_", package_name)), "=",
      installed_versions[[package_name]], "\n",
      sep = ""
    )
  }
  cat("OPERATOR_ROWS=32\n")
  cat("BASELINE_ROWS=6\n")
  cat("CANONICAL_KEY_ROWS=20\n")
  cat("DATASOURCE_ROWS=20\n")
  cat("CONTEXT_ROWS=23\n")
  cat("PROVENANCE_MAPPING_ROWS=528893\n")
  cat("PROVENANCE_MAPPING_ROW_GROUPS=19\n")
  cat("PROVENANCE_MAPPING_SCHEMA_FIELDS=17\n")
  cat("PROVENANCE_MAPPING_SHA256=", actual_mapping_sha256, "\n", sep = "")
  cat("RAW_INPUTS_ACCESSED=FALSE\n")
  cat("DOWNLOADS_PERFORMED=FALSE\n")
  cat("FORMAL_MATRIX_RUN=FALSE\n")
  cat("CONTRACT_PREFLIGHT_PASS\n")
  invisible(TRUE)
}

if (isTRUE(cli[["contracts-only"]])) {
  run_contract_preflight()
  quit(save = "no", status = 0L, runLast = FALSE)
}

suppressPackageStartupMessages({
  library(arrow)
  library(data.table)
  library(digest)
  library(dplyr)
  library(jsonlite)
})
arrow::set_cpu_count(1L)
arrow::set_io_thread_count(2L)

required_cli <- c("release-root", "output-root", "release-id", "release-date")
missing_cli <- required_cli[!vapply(
  required_cli,
  function(key) !is.null(cli[[key]]) && nzchar(as.character(cli[[key]])),
  logical(1)
)]
if (length(missing_cli) > 0L) {
  stop("CLI_FAIL_MISSING_REQUIRED_OPTIONS_", paste(missing_cli, collapse = ","))
}

checked_date <- format(Sys.Date(), "%Y-%m-%d")
release_id <- as.character(cli[["release-id"]])
release_date <- as.character(cli[["release-date"]])
ot_root <- normalizePath(
  as.character(cli[["release-root"]]),
  winslash = "/",
  mustWork = TRUE
)
out_root <- normalizePath(
  as.character(cli[["output-root"]]),
  winslash = "/",
  mustWork = FALSE
)
dir.create(out_root, recursive = TRUE, showWarnings = FALSE)
out_root <- normalizePath(out_root, winslash = "/", mustWork = TRUE)

context_filter <- if (!is.null(cli[["context-id"]])) {
  trimws(strsplit(as.character(cli[["context-id"]]), ",", fixed = TRUE)[[1]])
} else {
  character()
}

run_log <- file.path(out_root, "R08B_FORMAL_RUN.log")
sink(run_log, append = FALSE, split = TRUE)
on.exit({
  while (sink.number() > 0L) sink()
}, add = TRUE)

cat("TRACE_DT_R12_RELEASE_MATRIX\n")
cat("CHECKED_DATE=", checked_date, "\n", sep = "")
cat("RELEASE=Open Targets Platform ", release_id, " release ", release_date, "\n", sep = "")
cat("T1_ACCESS=NOT_ACCESSED_NOT_REQUIRED\n")
cat("ARTIFACT_RELATIVE_CONTRACTS=TRUE\n")
cat("T1_INPUT_OPTION=NONE\n")

read_tsv <- function(path, ...) {
  read.delim(
    path,
    sep = "\t",
    quote = "",
    stringsAsFactors = FALSE,
    check.names = FALSE,
    fileEncoding = "UTF-8",
    ...
  )
}

write_tsv <- function(value, path, na = "UNKNOWN") {
  write.table(
    value,
    path,
    sep = "\t",
    row.names = FALSE,
    col.names = TRUE,
    quote = FALSE,
    na = na,
    fileEncoding = "UTF-8"
  )
}

hash_text <- function(value) {
  digest(value, algo = "sha256", serialize = FALSE)
}

hash_file <- function(path) {
  digest(path, algo = "sha256", file = TRUE, serialize = FALSE)
}

to_text <- function(x) {
  if (is.data.frame(x)) {
    return(vapply(
      seq_len(nrow(x)),
      function(i) {
        value <- unlist(x[i, , drop = FALSE], recursive = TRUE, use.names = FALSE)
        value <- trimws(as.character(value))
        value <- value[!is.na(value) & nzchar(value)]
        paste(sort(unique(value), method = "radix"), collapse = "|")
      },
      character(1)
    ))
  }
  if (is.list(x)) {
    return(vapply(
      x,
      function(value) {
        value <- unlist(value, recursive = TRUE, use.names = FALSE)
        value <- trimws(as.character(value))
        value <- value[!is.na(value) & nzchar(value)]
        paste(sort(unique(value), method = "radix"), collapse = "|")
      },
      character(1)
    ))
  }
  value <- trimws(as.character(x))
  value[is.na(value)] <- ""
  value
}

field_text <- function(df, field_name) {
  if (!field_name %in% names(df)) return(rep("", nrow(df)))
  to_text(df[[field_name]])
}

resolve_keys <- function(df, datasource_id, spec_text) {
  specs <- strsplit(spec_text, ";", fixed = TRUE)[[1]]
  n <- nrow(df)
  resolved_key <- rep("", n)
  resolved_tier <- rep("", n)
  for (spec in specs) {
    fields <- strsplit(spec, "+", fixed = TRUE)[[1]]
    parts <- lapply(fields, function(field_name) field_text(df, field_name))
    valid <- !nzchar(resolved_key)
    for (part in parts) valid <- valid & nzchar(part)
    if (!any(valid)) next
    value <- rep("", n)
    for (j in seq_along(fields)) {
      token <- paste0(fields[[j]], "=", parts[[j]])
      value <- if (j == 1L) token else paste(value, token, sep = "&&")
    }
    resolved_key[valid] <- paste(
      datasource_id,
      spec,
      value[valid],
      sep = "::"
    )
    resolved_tier[valid] <- spec
  }
  data.frame(
    canonical_key = resolved_key,
    key_tier = resolved_tier,
    released_id_fallback = resolved_tier == "id",
    stringsAsFactors = FALSE
  )
}

harmonic_normalised <- function(values) {
  values <- sort(as.numeric(values), decreasing = TRUE)
  weights <- 1 / (seq_along(values)^2)
  sum(values * weights) / sum(weights)
}

deterministic_mean <- function(values) {
  values <- sort(as.numeric(values), decreasing = TRUE, method = "radix")
  mean(values)
}

canonical_cell_hash <- function(ledger) {
  ledger <- copy(ledger)
  setorder(ledger, targetId)
  score_text <- ifelse(
    is.finite(ledger$operator_score),
    sprintf("%.17g", ledger$operator_score),
    "NA"
  )
  rank_text <- ifelse(
    is.finite(ledger$operator_rank),
    as.character(as.integer(ledger$operator_rank)),
    "NA"
  )
  norm_text <- sprintf("%.17g", ledger$survival_normalized_rank)
  hash_text(paste(
    ledger$targetId,
    ledger$operator_status,
    score_text,
    rank_text,
    as.integer(ledger$selected_top50),
    norm_text,
    sep = "|",
    collapse = "\n"
  ))
}

top50_hash <- function(ledger) {
  selected <- ledger[selected_top50 == TRUE]
  setorder(selected, operator_rank, targetId)
  hash_text(paste(
    selected$targetId,
    sprintf("%.17g", selected$operator_score),
    sep = "|",
    collapse = "\n"
  ))
}

source(hard_rules_path)

universe <- as.data.table(read_tsv(universe_path))
required_universe_fields <- c(
  "candidate_id", "context_name", "open_targets_disease_id"
)
if (!all(required_universe_fields %in% names(universe))) {
  stop("CLI_FAIL_CONTEXT_CONTRACT_FIELDS")
}
if (length(context_filter) > 0L) {
  unknown_contexts <- setdiff(context_filter, universe$candidate_id)
  if (length(unknown_contexts) > 0L) {
    stop(
      "CLI_FAIL_UNKNOWN_CONTEXT_IDS_",
      paste(unknown_contexts, collapse = ",")
    )
  }
  universe <- universe[candidate_id %chin% context_filter]
}
if (nrow(universe) == 0L) stop("CLI_FAIL_NO_CONTEXTS_SELECTED")
setorder(universe, candidate_id)
disease_ids <- universe$open_targets_disease_id

operator_contract <- read_tsv(
  operator_contract_path,
  colClasses = c(operator_code = "character")
)
expected_operator_codes <- vapply(
  0:31,
  function(value) {
    paste0(as.integer(intToBits(value))[5:1], collapse = "")
  },
  character(1)
)
if (
  nrow(operator_contract) != 32L ||
  !identical(operator_contract$operator_code, expected_operator_codes)
) {
  stop("R08B_FAIL_OPERATOR_CONTRACT_NOT_EXACT_32")
}

baseline_contract <- read_tsv(baseline_contract_path)
if (nrow(baseline_contract) != 6L) stop("R08B_FAIL_BASELINE_COUNT_NOT_6")

r04_registry <- read_tsv(key_registry_path)
r04_registry <- r04_registry[, c(
  "datasource_id",
  "local_dataset",
  "key_tier_priority_first_complete_wins"
)]
names(r04_registry) <- c(
  "datasourceId",
  "local_dataset",
  "key_spec_priority_order"
)
if (nrow(r04_registry) != 20L) stop("R08B_FAIL_R04_REGISTRY_NOT_20")

mapping <- if (grepl("\\.parquet$", mapping_path, ignore.case = TRUE)) {
  as.data.table(read_parquet(mapping_path))
} else {
  fread(
    mapping_path,
    sep = "\t",
    encoding = "UTF-8",
    showProgress = FALSE
  )
}
mapping <- mapping[, .(
  datasourceId = as.character(datasourceId),
  canonical_key = as.character(r04_canonical_key),
  ancestry_group_id = fifelse(
    is.na(ancestry_group_id),
    "",
    as.character(ancestry_group_id)
  ),
  resolution_status = fifelse(
    is.na(resolution_status),
    "",
    as.character(resolution_status)
  ),
  forced_abstention_reason = fifelse(
    is.na(forced_abstention_reason),
    "",
    as.character(forced_abstention_reason)
  )
)]
if (mapping[, anyDuplicated(paste(datasourceId, canonical_key, sep = "\r"))] > 0L) {
  stop("R08B_FAIL_R05_MAPPING_KEY_NOT_UNIQUE")
}
setkey(mapping, datasourceId, canonical_key)

source_config <- as.data.table(read_tsv(source_config_path))
source_config <- source_config[, .(
  datasourceId = as.character(datasourceId),
  datatypeId = as.character(datatypeId)
)]
if (nrow(source_config) != 20L) stop("R08B_FAIL_SOURCE_CONFIG_NOT_20")
setkey(source_config, datasourceId)

structural_zero_sources <- character()

overall_ds <- open_dataset(file.path(ot_root, "association_overall_direct"))
legal_units <- overall_ds |>
  filter(diseaseId %in% disease_ids) |>
  select(
    diseaseId,
    targetId,
    associationScore,
    evidenceCount,
    currentNovelty
  ) |>
  collect()
rm(overall_ds)
invisible(gc(full = TRUE))
legal_units <- as.data.table(legal_units)
legal_units[, `:=`(
  diseaseId = as.character(diseaseId),
  targetId = as.character(targetId),
  associationScore = as.numeric(associationScore),
  evidenceCount = as.numeric(evidenceCount),
  currentNovelty = as.numeric(currentNovelty)
)]
legal_units <- merge(
  legal_units,
  universe[, .(
    candidate_id,
    context_name,
    diseaseId = open_targets_disease_id
  )],
  by = "diseaseId",
  all.x = TRUE,
  sort = FALSE
)
setorder(legal_units, candidate_id, targetId)
if (
  nrow(legal_units) == 0L ||
  uniqueN(legal_units, by = c("diseaseId", "targetId")) != nrow(legal_units)
) {
  stop("R12_FAIL_LEGAL_UNIT_KEY_NOT_UNIQUE_OR_EMPTY")
}
context_counts <- legal_units[, .(legal_unit_count = .N), by = diseaseId]
context_evaluability <- merge(
  universe[, .(
    candidate_id,
    context_name,
    diseaseId = open_targets_disease_id
  )],
  context_counts,
  by = "diseaseId",
  all.x = TRUE,
  sort = FALSE
)
context_evaluability[
  is.na(legal_unit_count),
  legal_unit_count := 0L
]
context_evaluability[, `:=`(
  evaluability_status = ifelse(
    legal_unit_count > 0L,
    "EVALUABLE_EXACT_DISEASE_ID",
    "NOT_EVALUABLE_CONTEXT_ABSENT"
  ),
  non_evaluable_reason = ifelse(
    legal_unit_count > 0L,
    "",
    paste0(
      "EXACT_DISEASE_ID_ABSENT_FROM_ASSOCIATION_OVERALL_DIRECT_",
      gsub("\\.", "_", release_id)
    )
  ),
  ontology_substitution = "PROHIBITED_NOT_PERFORMED",
  open_targets_release = release_id,
  checked_date = checked_date
)]
setorder(context_evaluability, candidate_id)
write_tsv(
  context_evaluability,
  file.path(out_root, "CONTEXT_EVALUABILITY_MANIFEST.tsv"),
  na = ""
)

frozen_universe <- copy(universe)
universe <- universe[
  open_targets_disease_id %chin%
    context_evaluability[
      evaluability_status == "EVALUABLE_EXACT_DISEASE_ID",
      diseaseId
    ]
]
if (nrow(universe) == 0L) {
  stop("R12_FAIL_NO_EXACT_CONTEXT_EVALUABLE_IN_HISTORICAL_RELEASE")
}
if (uniqueN(legal_units$diseaseId) != nrow(universe)) {
  stop("R12_FAIL_EVALUABLE_CONTEXT_COUNT_MISMATCH")
}
legal_units[, pair_key := paste(diseaseId, targetId, sep = "::")]

hard_rule_fields <- c(
  "clinicalStage", "trialStopReasonCategories", "confidence",
  "clinicalSignificances", "alleleOrigins", "resourceScore",
  "pValueMantissa", "pValueExponent", "beta", "oddsRatio",
  "significantDriverMethods", "evidenceDate"
)

record_chunks <- vector("list", nrow(r04_registry))
empty_record_chunk <- data.table(
  pair_key = character(),
  diseaseId = character(),
  targetId = character(),
  datasourceId = character(),
  datatypeId = character(),
  canonical_key = character(),
  key_tier = character(),
  ancestry_group_id = character(),
  resolution_status = character(),
  forced_abstention_reason = character(),
  score = double(),
  evidence_date_text = character(),
  primary_hard_eligible = logical(),
  hard_class = character(),
  source_rule_reason = character()
)
for (i in seq_len(nrow(r04_registry))) {
  reg <- r04_registry[i, , drop = FALSE]
  datasource_id <- as.character(reg$datasourceId)
  dataset_path <- file.path(ot_root, reg$local_dataset)
  ds <- open_dataset(dataset_path)
  available <- names(ds)
  key_fields <- unique(unlist(strsplit(
    unlist(strsplit(reg$key_spec_priority_order, ";", fixed = TRUE)),
    "+",
    fixed = TRUE
  )))
  keep <- intersect(
    unique(c(
      "diseaseId", "targetId", "datasourceId", "score",
      key_fields, hard_rule_fields
    )),
    available
  )
  current <- ds |>
    filter(diseaseId %in% disease_ids, score > 0) |>
    select(all_of(keep)) |>
    collect()
  rm(ds)
  invisible(gc(full = TRUE))
  if (nrow(current) == 0L) {
    structural_zero_sources <- sort(
      unique(c(structural_zero_sources, datasource_id)),
      method = "radix"
    )
    record_chunks[[i]] <- copy(empty_record_chunk)
    cat(
      "STRUCTURAL_ZERO_DATASOURCE=",
      datasource_id,
      ";STATUS=RELEASE_SPECIFIC_STRUCTURAL_ZERO\n",
      sep = ""
    )
    next
  }
  resolved <- resolve_keys(
    current,
    datasource_id,
    reg$key_spec_priority_order
  )
  current$canonical_key <- resolved$canonical_key
  current$key_tier <- resolved$key_tier
  current$released_id_fallback <- resolved$released_id_fallback
  current$datasourceId <- datasource_id
  current$score <- as.numeric(current$score)
  current$evidence_date_text <- field_text(current, "evidenceDate")
  hard_status <- hard_evidence_eligibility_v1(current, datasource_id)
  current$primary_hard_eligible <- hard_status$primary_hard_eligible
  current$hard_class <- hard_status$hard_class
  current$source_rule_reason <- hard_status$source_rule_reason

  current <- as.data.table(current)
  current <- merge(
    current,
    mapping[J(datasource_id), nomatch = 0L],
    by = c("datasourceId", "canonical_key"),
    all.x = TRUE,
    sort = FALSE
  )
  current <- merge(
    current,
    source_config,
    by = "datasourceId",
    all.x = TRUE,
    sort = FALSE
  )
  current[is.na(ancestry_group_id), ancestry_group_id := ""]
  current[is.na(resolution_status), resolution_status := "MISSING_R05_MAPPING"]
  current[
    is.na(forced_abstention_reason),
    forced_abstention_reason := "MISSING_R05_MAPPING"
  ]
  current[, pair_key := paste(diseaseId, targetId, sep = "::")]
  current <- current[pair_key %chin% legal_units$pair_key]
  record_chunks[[i]] <- current[, .(
    pair_key,
    diseaseId = as.character(diseaseId),
    targetId = as.character(targetId),
    datasourceId = as.character(datasourceId),
    datatypeId = as.character(datatypeId),
    canonical_key = as.character(canonical_key),
    key_tier = as.character(key_tier),
    ancestry_group_id = as.character(ancestry_group_id),
    resolution_status = as.character(resolution_status),
    forced_abstention_reason = as.character(forced_abstention_reason),
    score = as.numeric(score),
    evidence_date_text = as.character(evidence_date_text),
    primary_hard_eligible = as.logical(primary_hard_eligible),
    hard_class = as.character(hard_class),
    source_rule_reason = as.character(source_rule_reason)
  )]
  rm(current, resolved, hard_status)
  invisible(gc(full = TRUE))
  cat("LOADED_DATASOURCE=", datasource_id, "\n", sep = "")
}

raw_records <- rbindlist(record_chunks, use.names = TRUE, fill = TRUE)
rm(record_chunks, mapping)
invisible(gc(full = TRUE))
setorder(
  raw_records,
  diseaseId,
  targetId,
  datasourceId,
  canonical_key,
  ancestry_group_id,
  score
)
if (nrow(raw_records) == 0L) stop("R12_FAIL_NO_POSITIVE_RAW_ROWS")
if (any(!is.finite(raw_records$score) | raw_records$score <= 0 | raw_records$score > 1)) {
  stop("R08B_FAIL_INVALID_RAW_SCORE")
}

raw_records[, evidence_date := suppressWarnings(as.IDate(
  substr(evidence_date_text, 1L, 10L)
))]
t0_date <- as.IDate(release_date)
if (is.na(t0_date)) stop("R12_FAIL_INVALID_RELEASE_DATE")

component_families <- raw_records[nzchar(ancestry_group_id), .(
  family_signature = paste(
    sort(unique(datatypeId), method = "radix"),
    collapse = "+"
  )
), by = .(pair_key, ancestry_group_id)]

pair_summary <- raw_records[, .(
  positive_raw_rows = .N,
  any_missing_key = any(!nzchar(canonical_key)),
  any_missing_ancestry = any(!nzchar(ancestry_group_id)),
  t0_primary_hard_positive = any(primary_hard_eligible),
  first_evidence_date = if (
    any(!is.na(evidence_date))
  ) min(evidence_date, na.rm = TRUE) else as.IDate(NA),
  last_evidence_date = if (
    any(!is.na(evidence_date))
  ) max(evidence_date, na.rm = TRUE) else as.IDate(NA),
  dated_evidence_fraction = mean(!is.na(evidence_date)),
  ancestry_collapsed_artifact_count = uniqueN(
    ancestry_group_id[nzchar(ancestry_group_id)]
  )
), by = .(pair_key)]

family_summary <- component_families[, .(
  ancestry_collapsed_source_family_breadth = uniqueN(family_signature)
), by = pair_key]
pair_summary <- merge(
  pair_summary,
  family_summary,
  by = "pair_key",
  all.x = TRUE,
  sort = FALSE
)
pair_summary[
  is.na(ancestry_collapsed_source_family_breadth),
  ancestry_collapsed_source_family_breadth := 0L
]

legal_units <- merge(
  legal_units,
  pair_summary,
  by = "pair_key",
  all.x = TRUE,
  sort = FALSE
)
legal_units[is.na(positive_raw_rows), `:=`(
  positive_raw_rows = 0L,
  any_missing_key = TRUE,
  any_missing_ancestry = TRUE,
  t0_primary_hard_positive = FALSE,
  dated_evidence_fraction = 0,
  ancestry_collapsed_artifact_count = 0L,
  ancestry_collapsed_source_family_breadth = 0L
)]
legal_units[, t0_hard_negative := !t0_primary_hard_positive]
legal_units[, common_baseline_abstention := (
  positive_raw_rows == 0L |
  any_missing_key |
  any_missing_ancestry
)]
legal_units[, `:=`(
  first_evidence_age_days = as.numeric(t0_date - first_evidence_date),
  last_evidence_recency_days = as.numeric(t0_date - last_evidence_date),
  recency_numeric = as.numeric(last_evidence_date)
)]

target_global <- legal_units[, .(
  total_artifacts_all_contexts = sum(
    ancestry_collapsed_artifact_count,
    na.rm = TRUE
  )
), by = targetId]
legal_units <- merge(
  legal_units,
  target_global,
  by = "targetId",
  all.x = TRUE,
  sort = FALSE
)
legal_units[, target_global_artifact_count_other_22_contexts := pmax(
  0,
  total_artifacts_all_contexts - ancestry_collapsed_artifact_count
)]
setorder(legal_units, candidate_id, targetId)

operator_input_path <- file.path(out_root, "FORMAL_OPERATOR_INPUT.parquet")
write_parquet(
  as.data.frame(raw_records[, .(
    pair_key,
    diseaseId,
    targetId,
    datasourceId,
    datatypeId,
    canonical_key,
    ancestry_group_id,
    score
  )]),
  operator_input_path,
  compression = "zstd"
)

legal_metrics_path <- file.path(
  out_root,
  "T0_LEGAL_UNIT_BASELINE_METRICS.parquet"
)
write_parquet(
  as.data.frame(legal_units[, .(
    candidate_id,
    context_name,
    diseaseId,
    targetId,
    pair_key,
    associationScore,
    evidenceCount,
    currentNovelty,
    recency_numeric,
    ancestry_collapsed_artifact_count,
    ancestry_collapsed_source_family_breadth,
    t0_primary_hard_positive,
    t0_hard_negative,
    positive_raw_rows,
    any_missing_key,
    any_missing_ancestry,
    common_baseline_abstention
  )]),
  legal_metrics_path,
  compression = "zstd"
)

exposure_path <- file.path(out_root, "T0_EXPOSURE_COVARIATES.parquet")
write_parquet(
  as.data.frame(legal_units[, .(
    candidate_id,
    context_name,
    diseaseId,
    targetId,
    log1p_pair_ancestry_collapsed_artifact_count =
      log1p(ancestry_collapsed_artifact_count),
    pair_source_family_breadth =
      ancestry_collapsed_source_family_breadth,
    log1p_target_global_artifact_count_other_22_contexts =
      log1p(target_global_artifact_count_other_22_contexts),
    first_evidence_age_days,
    last_evidence_recency_days,
    dated_evidence_fraction,
    missing_first_evidence_age = is.na(first_evidence_age_days),
    missing_last_evidence_recency = is.na(last_evidence_recency_days),
    missing_dated_evidence_fraction = is.na(dated_evidence_fraction)
  )]),
  exposure_path,
  compression = "zstd"
)

score_one_cell <- function(
  context_units,
  context_records,
  realization,
  reverse_rows = FALSE
) {
  records <- copy(context_records)
  if (reverse_rows && nrow(records) > 0L) {
    records <- records[rev(seq_len(nrow(records)))]
  }
  bits <- as.integer(unlist(
    realization[c("O1", "O2", "O3", "O4", "O5")],
    use.names = FALSE
  ))
  names(bits) <- c("O1", "O2", "O3", "O4", "O5")
  records[, score_work := score]
  if (bits[["O3"]] == 1L) {
    records[, score_work := rank(
      score_work,
      ties.method = "average",
      na.last = "keep"
    ) / sum(is.finite(score_work)), by = datasourceId]
  }

  invalid_score_targets <- records[
    !is.finite(score_work) | score_work <= 0 | score_work > 1,
    unique(targetId)
  ]
  unresolved_key_targets <- if (bits[["O1"]] == 1L) {
    records[!nzchar(canonical_key), unique(targetId)]
  } else {
    character(0)
  }
  unresolved_ancestry_targets <- if (bits[["O2"]] == 1L) {
    records[!nzchar(ancestry_group_id), unique(targetId)]
  } else {
    character(0)
  }
  records[, group_id := if (bits[["O2"]] == 1L) {
    paste0("ANCESTRY::", ancestry_group_id)
  } else {
    paste0("DATASOURCE::", datasourceId)
  }]

  if (bits[["O1"]] == 1L) {
    units <- records[, .(
      score_work = max(score_work)
    ), by = .(targetId, group_id, canonical_key)]
  } else {
    units <- records[, .(targetId, group_id, score_work)]
  }

  if (bits[["O4"]] == 1L) {
    group_scores <- units[, .(
      group_score = harmonic_normalised(score_work)
    ), by = .(targetId, group_id)]
  } else {
    group_scores <- units[, .(
      group_score = max(score_work)
    ), by = .(targetId, group_id)]
  }

  if (bits[["O5"]] == 1L) {
    target_scores <- group_scores[, .(
      operator_score = harmonic_normalised(group_score)
    ), by = targetId]
  } else {
    target_scores <- group_scores[, .(
      operator_score = deterministic_mean(group_score)
    ), by = targetId]
  }

  ledger <- merge(
    context_units[, .(
      candidate_id,
      context_name,
      diseaseId,
      targetId,
      t0_primary_hard_positive,
      t0_hard_negative,
      positive_raw_rows
    )],
    target_scores,
    by = "targetId",
    all.x = TRUE,
    sort = FALSE
  )
  ledger[, operator_status := "SCORED"]
  ledger[t0_primary_hard_positive == TRUE, operator_status :=
    "INELIGIBLE_T0_PRIMARY_HARD_EVIDENCE"]
  ledger[positive_raw_rows == 0L, operator_status :=
    "ABSTAIN_NO_POSITIVE_RAW_EVIDENCE"]
  ledger[targetId %chin% invalid_score_targets, operator_status :=
    "ABSTAIN_INVALID_SCORE"]
  ledger[targetId %chin% unresolved_key_targets, operator_status :=
    "ABSTAIN_UNRESOLVED_INDEPENDENT_KEY"]
  ledger[targetId %chin% unresolved_ancestry_targets, operator_status :=
    "ABSTAIN_UNRESOLVED_ANCESTRY"]
  ledger[operator_status != "SCORED", operator_score := NA_real_]
  ledger[, `:=`(
    operator_rank = NA_integer_,
    selected_top50 = FALSE,
    survival_normalized_rank = 1
  )]
  ranked_index <- which(
    ledger$operator_status == "SCORED" &
    ledger$t0_hard_negative &
    is.finite(ledger$operator_score) &
    ledger$operator_score > 0
  )
  if (length(ranked_index) > 0L) {
    ranked <- ledger[ranked_index]
    setorder(ranked, -operator_score, targetId)
    ranked[, operator_rank := seq_len(.N)]
    denominator <- max(nrow(ranked) - 1L, 1L)
    ranked[, selected_top50 := operator_rank <= 50L]
    ranked[
      selected_top50 == TRUE,
      survival_normalized_rank := (operator_rank - 1) / denominator
    ]
    ledger[
      ranked,
      on = "targetId",
      `:=`(
        operator_rank = i.operator_rank,
        selected_top50 = i.selected_top50,
        survival_normalized_rank = i.survival_normalized_rank
      )
    ]
  }
  setorder(ledger, targetId)
  ledger[, `:=`(
    realization_id = as.character(realization$realization_id),
    operator_code = as.character(realization$operator_code)
  )]
  setcolorder(ledger, c(
    "candidate_id", "context_name", "diseaseId", "targetId",
    "realization_id", "operator_code", "operator_status",
    "operator_score", "operator_rank", "selected_top50",
    "survival_normalized_rank", "t0_primary_hard_positive",
    "t0_hard_negative", "positive_raw_rows"
  ))
  ledger
}

run_matrix <- function(reverse_order = FALSE, retain_ledgers = FALSE) {
  context_order <- universe$candidate_id
  realization_order <- seq_len(nrow(operator_contract))
  if (reverse_order) {
    context_order <- rev(context_order)
    realization_order <- rev(realization_order)
  }
  ledger_rows <- if (retain_ledgers) {
    vector("list", nrow(universe) * nrow(operator_contract))
  } else {
    NULL
  }
  manifest_rows <- vector("list", nrow(universe) * nrow(operator_contract))
  index <- 0L
  for (candidate in context_order) {
    context_units <- legal_units[candidate_id == candidate]
    context_records <- raw_records[diseaseId == context_units$diseaseId[[1]]]
    for (operator_index in realization_order) {
      index <- index + 1L
      realization <- operator_contract[operator_index, , drop = FALSE]
      started <- proc.time()[["elapsed"]]
      ledger <- score_one_cell(
        context_units,
        context_records,
        realization,
        reverse_rows = reverse_order
      )
      elapsed <- proc.time()[["elapsed"]] - started
      cell_hash <- canonical_cell_hash(ledger)
      selected_hash <- top50_hash(ledger)
      manifest_rows[[index]] <- data.frame(
        run_order = ifelse(reverse_order, "REVERSED", "FORWARD"),
        candidate_id = candidate,
        context_name = context_units$context_name[[1]],
        diseaseId = context_units$diseaseId[[1]],
        realization_id = realization$realization_id,
        operator_code = realization$operator_code,
        legal_unit_rows = nrow(ledger),
        eligible_hard_negative_rows = sum(ledger$t0_hard_negative),
        scored_eligible_rows = sum(
          ledger$operator_status == "SCORED" &
          ledger$t0_hard_negative
        ),
        abstained_rows = sum(grepl("^ABSTAIN_", ledger$operator_status)),
        ineligible_t0_hard_rows = sum(
          ledger$operator_status ==
          "INELIGIBLE_T0_PRIMARY_HARD_EVIDENCE"
        ),
        selected_top50_rows = sum(ledger$selected_top50),
        canonical_cell_sha256 = cell_hash,
        selected_top50_sha256 = selected_hash,
        elapsed_seconds = elapsed,
        technical_status = "CELL_COMPLETE",
        t1_access = "PROHIBITED_NOT_ACCESSED",
        checked_date = checked_date,
        stringsAsFactors = FALSE
      )
      if (retain_ledgers) ledger_rows[[index]] <- ledger
      cat(
        "CELL_COMPLETE=", candidate, "::",
        realization$realization_id, "::",
        ifelse(reverse_order, "REVERSED", "FORWARD"),
        "\n",
        sep = ""
      )
    }
  }
  list(
    manifest = rbindlist(manifest_rows, use.names = TRUE, fill = TRUE),
    ledgers = if (retain_ledgers) {
      rbindlist(ledger_rows, use.names = TRUE, fill = TRUE)
    } else {
      NULL
    }
  )
}

forward <- run_matrix(reverse_order = FALSE, retain_ledgers = TRUE)
reverse <- run_matrix(reverse_order = TRUE, retain_ledgers = FALSE)

forward_manifest <- forward$manifest
reverse_manifest <- reverse$manifest
setorder(forward_manifest, candidate_id, realization_id)
setorder(reverse_manifest, candidate_id, realization_id)

comparison <- merge(
  forward_manifest[, .(
    candidate_id,
    diseaseId,
    realization_id,
    operator_code,
    forward_cell_sha256 = canonical_cell_sha256,
    forward_top50_sha256 = selected_top50_sha256,
    forward_rows = legal_unit_rows,
    forward_selected = selected_top50_rows
  )],
  reverse_manifest[, .(
    candidate_id,
    diseaseId,
    realization_id,
    operator_code,
    reverse_cell_sha256 = canonical_cell_sha256,
    reverse_top50_sha256 = selected_top50_sha256,
    reverse_rows = legal_unit_rows,
    reverse_selected = selected_top50_rows
  )],
  by = c("candidate_id", "diseaseId", "realization_id", "operator_code"),
  all = TRUE,
  sort = TRUE
)
comparison[, deterministic := (
  forward_cell_sha256 == reverse_cell_sha256 &
  forward_top50_sha256 == reverse_top50_sha256 &
  forward_rows == reverse_rows &
  forward_selected == reverse_selected
)]
expected_cells <- nrow(universe) * nrow(operator_contract)
if (nrow(comparison) != expected_cells || !all(comparison$deterministic)) {
  stop("R08B_FAIL_FORWARD_REVERSED_MISMATCH")
}

status_matrix <- forward$ledgers
setorder(status_matrix, candidate_id, realization_id, targetId)
expected_status_rows <- nrow(legal_units) * nrow(operator_contract)
if (
  nrow(status_matrix) != expected_status_rows ||
  uniqueN(
    status_matrix,
    by = c("candidate_id", "realization_id", "targetId")
  ) != expected_status_rows
) {
  stop("R08B_FAIL_STATUS_MATRIX_DIMENSION")
}

status_path <- file.path(out_root, "LEGAL_UNIT_OPERATOR_STATUS_MATRIX.parquet")
write_parquet(
  as.data.frame(status_matrix),
  status_path,
  compression = "zstd"
)

abstention_ledger <- status_matrix[
  grepl("^ABSTAIN_", operator_status)
]
write_parquet(
  as.data.frame(abstention_ledger),
  file.path(out_root, "MANDATORY_ABSTENTION_LEDGER.parquet"),
  compression = "zstd"
)

survival <- status_matrix[, .(
  selection_count = sum(selected_top50),
  selection_rate = mean(selected_top50),
  median_normalized_rank = median(survival_normalized_rank),
  p90_normalized_rank = as.numeric(
    quantile(survival_normalized_rank, probs = 0.90, type = 7)
  ),
  operator_scored_count = sum(operator_status == "SCORED"),
  operator_abstention_count = sum(grepl("^ABSTAIN_", operator_status)),
  t0_primary_hard_positive = first(t0_primary_hard_positive),
  t0_hard_negative = first(t0_hard_negative)
), by = .(candidate_id, context_name, diseaseId, targetId)]
survival[, primary_threshold_pass := (
  t0_hard_negative &
  selection_count >= 26L
)]
setorder(
  survival,
  candidate_id,
  -selection_count,
  median_normalized_rank,
  p90_normalized_rank,
  targetId
)
survival[, threshold_order := seq_len(.N), by = candidate_id]
survival[, trace_dt_nominated := (
  primary_threshold_pass &
  threshold_order <= 50L
)]
setorder(survival, candidate_id, targetId)
if (nrow(survival) != nrow(legal_units)) {
  stop("R12_FAIL_SURVIVAL_ROWS_NOT_LEGAL_UNIT_COUNT")
}

write_parquet(
  as.data.frame(survival),
  file.path(out_root, "TARGET_CONTEXT_SURVIVAL_TABLE.parquet"),
  compression = "zstd"
)

trace_fixed_rows <- list()
trace_tie_rows <- list()
for (candidate in universe$candidate_id) {
  eligible <- copy(survival[
    candidate_id == candidate &
    primary_threshold_pass == TRUE
  ])
  setorder(
    eligible,
    -selection_count,
    median_normalized_rank,
    p90_normalized_rank,
    targetId
  )
  eligible[, pretruncation_order := seq_len(.N)]
  eligible[, retained_b50 := pretruncation_order <= 50L]
  trace_tie_rows[[length(trace_tie_rows) + 1L]] <- eligible[, .(
    candidate_id,
    context_name,
    diseaseId,
    targetId,
    selection_count,
    median_normalized_rank,
    p90_normalized_rank,
    pretruncation_order,
    retained_b50
  )]
  selected <- head(eligible, 50L)
  fixed <- data.table(slot = 1:50)
  fixed[, `:=`(
    candidate_id = candidate,
    context_name = universe[
      candidate_id == candidate,
      context_name
    ][[1]],
    diseaseId = universe[
      candidate_id == candidate,
      open_targets_disease_id
    ][[1]]
  )]
  fixed[, `:=`(
    targetId = "",
    selection_count = NA_integer_,
    median_normalized_rank = NA_real_,
    p90_normalized_rank = NA_real_,
    slot_status = "UNFILLED_ZERO"
  )]
  if (nrow(selected) > 0L) {
    fixed[seq_len(nrow(selected)), `:=`(
      targetId = selected$targetId,
      selection_count = selected$selection_count,
      median_normalized_rank = selected$median_normalized_rank,
      p90_normalized_rank = selected$p90_normalized_rank,
      slot_status = "TRACE_DT_NOMINATION"
    )]
  }
  trace_fixed_rows[[length(trace_fixed_rows) + 1L]] <- fixed
}
trace_fixed <- rbindlist(trace_fixed_rows)
trace_ties <- rbindlist(trace_tie_rows, fill = TRUE)
setcolorder(trace_fixed, c(
  "candidate_id", "context_name", "diseaseId", "slot", "targetId",
  "selection_count", "median_normalized_rank", "p90_normalized_rank",
  "slot_status"
))
write_tsv(
  trace_fixed,
  file.path(out_root, "TRACE_DT_B50_NOMINATION_LISTS.tsv"),
  na = ""
)
write_tsv(
  trace_ties,
  file.path(out_root, "DETERMINISTIC_TIE_BREAK_LOG.tsv"),
  na = ""
)

baseline_metric_map <- list(
  B01 = "associationScore",
  B02 = "evidenceCount",
  B03 = "currentNovelty",
  B04 = "recency_numeric",
  B05 = "ancestry_collapsed_artifact_count",
  B06 = "ancestry_collapsed_source_family_breadth"
)
baseline_rows <- list()
for (candidate in universe$candidate_id) {
  context_units <- copy(legal_units[candidate_id == candidate])
  context_units <- context_units[
    t0_hard_negative == TRUE &
    common_baseline_abstention == FALSE
  ]
  for (baseline_id in names(baseline_metric_map)) {
    metric <- baseline_metric_map[[baseline_id]]
    eligible <- context_units[is.finite(get(metric))]
    setorderv(
      eligible,
      c(metric, "targetId"),
      c(-1L, 1L),
      na.last = TRUE
    )
    selected <- head(eligible, 50L)
    fixed <- data.table(slot = 1:50)
    fixed[, `:=`(
      baseline_id = baseline_id,
      baseline_name = baseline_contract[
        baseline_contract$baseline_id == baseline_id,
        "baseline_name"
      ][[1]],
      candidate_id = candidate,
      context_name = universe[
        candidate_id == candidate,
        context_name
      ][[1]],
      diseaseId = universe[
        candidate_id == candidate,
        open_targets_disease_id
      ][[1]],
      targetId = "",
      metric_name = metric,
      metric_value = NA_real_,
      slot_status = "UNFILLED_ZERO"
    )]
    if (nrow(selected) > 0L) {
      fixed[seq_len(nrow(selected)), `:=`(
        targetId = selected$targetId,
        metric_value = selected[[metric]],
        slot_status = "BASELINE_NOMINATION"
      )]
    }
    baseline_rows[[length(baseline_rows) + 1L]] <- fixed
  }
}
baseline_lists <- rbindlist(baseline_rows)
setcolorder(baseline_lists, c(
  "baseline_id", "baseline_name", "candidate_id", "context_name",
  "diseaseId", "slot", "targetId", "metric_name", "metric_value",
  "slot_status"
))
write_tsv(
  baseline_lists,
  file.path(out_root, "SIX_BASELINE_B50_NOMINATION_LISTS.tsv"),
  na = ""
)

write_tsv(
  forward_manifest,
  file.path(out_root, "FORWARD_ORDER_MANIFEST.tsv")
)
write_tsv(
  reverse_manifest,
  file.path(out_root, "REVERSED_ORDER_MANIFEST.tsv")
)
write_tsv(
  comparison,
  file.path(out_root, "FORWARD_REVERSED_COMPARISON.tsv")
)

absent_context_rows <- context_evaluability[
  evaluability_status == "NOT_EVALUABLE_CONTEXT_ABSENT"
]
failure_parts <- list()
if (nrow(absent_context_rows) > 0L) {
  failure_parts[[length(failure_parts) + 1L]] <- data.frame(
    event_id = sprintf(
      "R12-CONTEXT-%02d",
      seq_len(nrow(absent_context_rows))
    ),
    event_type = rep("CONTEXT_NON_EVALUABLE", nrow(absent_context_rows)),
    stage = rep(
      "HISTORICAL_RELEASE_ADDRESSABILITY",
      nrow(absent_context_rows)
    ),
    evidence = paste0(
      absent_context_rows$candidate_id,
      " | ",
      absent_context_rows$context_name,
      " | ",
      absent_context_rows$diseaseId,
      " absent from association_overall_direct"
    ),
    action = rep(
      "Retain frozen context as NOT_EVALUABLE_CONTEXT_ABSENT; do not remap",
      nrow(absent_context_rows)
    ),
    disposition = rep(
      "VERSION_LOCKED_FAIL_CLOSED_CONTEXT_RETENTION",
      nrow(absent_context_rows)
    ),
    t1_access = rep(
      "PROHIBITED_NOT_ACCESSED",
      nrow(absent_context_rows)
    ),
    checked_date = rep(checked_date, nrow(absent_context_rows)),
    stringsAsFactors = FALSE
  )
}
failure_parts[[length(failure_parts) + 1L]] <- data.frame(
    event_id = "R08B-B01",
    event_type = "BOUNDARY",
    stage = "FORMAL_T0_MATRIX",
    evidence =
      "Historical matrix generated for exact-ID-evaluable contexts; independent implementation QC not yet complete",
    action =
      "Do not write scientific Results, inspect T1 or create result-type Figures",
    disposition = "PENDING_INDEPENDENT_QC",
    t1_access = "PROHIBITED_NOT_ACCESSED",
    checked_date = checked_date,
    stringsAsFactors = FALSE
)
failure_log <- rbindlist(failure_parts, use.names = TRUE, fill = TRUE)
write_tsv(
  failure_log,
  file.path(out_root, "FAILURE_AND_DEVIATION_LOG.tsv")
)

metrics <- data.frame(
  metric = c(
    "frozen_context_count",
    "evaluable_context_count",
    "non_evaluable_context_count",
    "operator_count",
    "context_operator_cells",
    "legal_unit_count",
    "legal_unit_operator_status_rows",
    "forward_reversed_deterministic_cells",
    "trace_fixed_slots",
    "baseline_count",
    "baseline_fixed_slots",
    "t1_access"
  ),
  value = c(
    nrow(frozen_universe),
    nrow(universe),
    nrow(frozen_universe) - nrow(universe),
    nrow(operator_contract),
    nrow(forward_manifest),
    nrow(legal_units),
    nrow(status_matrix),
    sum(comparison$deterministic),
    nrow(trace_fixed),
    6,
    nrow(baseline_lists),
    "NOT_ACCESSED_NOT_REQUIRED"
  ),
  expected = c(
    nrow(frozen_universe),
    nrow(universe),
    nrow(frozen_universe) - nrow(universe),
    nrow(operator_contract),
    expected_cells,
    nrow(legal_units),
    expected_status_rows,
    expected_cells,
    nrow(universe) * 50L,
    nrow(baseline_contract),
    nrow(universe) * nrow(baseline_contract) * 50L,
    "NOT_ACCESSED_NOT_REQUIRED"
  ),
  status = c(
    "PASS", "PASS", "PASS", "PASS", "PASS", "PASS",
    "PASS", "PASS", "PASS", "PASS", "PASS", "PASS"
  ),
  checked_date = checked_date,
  stringsAsFactors = FALSE
)
write_tsv(metrics, file.path(out_root, "R08B_TECHNICAL_METRICS.tsv"))

writeLines(
  c(
    "# TRACE-DT R12 release-matrix execution state",
    "",
    paste0("Checked date: ", checked_date),
    "",
    paste0("Release: `", release_id, "`"),
    "",
    "State: `R12_RELEASE_MATRIX_COMPLETE_PENDING_INDEPENDENT_QC`",
    "",
    paste0(
      "- Frozen contexts retained: ",
      nrow(frozen_universe),
      "; exact-ID evaluable: ",
      nrow(universe),
      "; not evaluable because the exact disease identifier was absent: ",
      nrow(frozen_universe) - nrow(universe),
      "."
    ),
    paste0("- ", expected_cells, "/", expected_cells, " context-operator cells written."),
    paste0("- ", expected_status_rows, "/", expected_status_rows, " legal-unit-operator status rows written."),
    paste0("- Forward/reversed order comparison: ", expected_cells, "/", expected_cells, " deterministic."),
    "- T1: `NOT_ACCESSED_NOT_REQUIRED`.",
    "- Interpretation remains blocked until R12 parity/QC passes.",
    "",
    "This state is not a scientific conclusion and does not authorize",
    "superiority, target interpretation or manuscript Results."
  ),
  file.path(out_root, "R08B_EXECUTION_STATE.md"),
  useBytes = TRUE
)

cat("R08B_FORWARD_CELLS=", nrow(forward_manifest), "\n", sep = "")
cat("R08B_STATUS_ROWS=", nrow(status_matrix), "\n", sep = "")
cat(
  "R08B_FORWARD_REVERSED_MATCH=",
  sum(comparison$deterministic),
  "/",
  nrow(comparison),
  "\n",
  sep = ""
)
cat("R08B_STATE=PENDING_INDEPENDENT_QC\n")

rm(
  status_matrix,
  raw_records,
  legal_units,
  survival,
  forward,
  reverse
)
invisible(gc(full = TRUE))
while (sink.number() > 0L) sink()
