suppressPackageStartupMessages(library(arrow))
suppressPackageStartupMessages(library(data.table))

# Read-only audit of deterministic cutoff ties in the frozen R16
# target-cancer-specification matrix. The script never recomputes an operator
# score. It only:
#   1. verifies the frozen ascending-ID top-50 memberships;
#   2. reverses target-ID order within exact score ties;
#   3. recomputes list-overlap summaries from those frozen scores.

args <- commandArgs(trailingOnly = TRUE)
script_arg <- commandArgs(trailingOnly = FALSE)
script_arg <- script_arg[grepl("^--file=", script_arg)]
if (length(script_arg) != 1L) stop("R16_AUTHOR_SPEC_TIE_AUDIT_SCRIPT_PATH_NOT_RESOLVED")
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

matrix_path <- file.path(
  artifact_root,
  "data",
  "derived",
  "ot26_06",
  "legal_unit_operator_status_matrix.parquet"
)
output_root <- if (length(args) >= 1L) {
  normalizePath(args[[1]], winslash = "/", mustWork = FALSE)
} else {
  file.path(artifact_root, "work", "author_spec_tie_sensitivity")
}

if (!file.exists(matrix_path)) {
  stop("R16_AUTHOR_SPEC_TIE_AUDIT_MATRIX_NOT_FOUND: ", matrix_path)
}

matrix <- as.data.table(read_parquet(matrix_path))
required_columns <- c(
  "candidate_id",
  "context_name",
  "diseaseId",
  "targetId",
  "realization_id",
  "operator_code",
  "operator_status",
  "operator_score",
  "operator_rank",
  "selected_top50",
  "t0_hard_negative"
)
if (!all(required_columns %in% names(matrix))) {
  stop("R16_AUTHOR_SPEC_TIE_AUDIT_MATRIX_SCHEMA_MISMATCH")
}

eligible <- matrix[
  operator_status == "SCORED" &
    t0_hard_negative == TRUE &
    is.finite(operator_score) &
    operator_score > 0
]

cell_contract <- unique(
  eligible[
    ,
    .(
      candidate_id,
      context_name,
      diseaseId,
      realization_id,
      operator_code
    )
  ]
)
if (
  nrow(cell_contract) != 736L ||
    uniqueN(cell_contract$candidate_id) != 23L ||
    uniqueN(cell_contract$realization_id) != 32L
) {
  stop("R16_AUTHOR_SPEC_TIE_AUDIT_CELL_CONTRACT_FAILED")
}
if (!all(nchar(cell_contract$operator_code) == 5L)) {
  stop("R16_AUTHOR_SPEC_TIE_AUDIT_OPERATOR_CODE_LENGTH_FAILED")
}

ascending <- copy(eligible)
setorder(
  ascending,
  candidate_id,
  realization_id,
  -operator_score,
  targetId
)
ascending[
  ,
  ascending_rank_recomputed := seq_len(.N),
  by = .(candidate_id, realization_id)
]

reverse_id <- copy(eligible)
setorder(
  reverse_id,
  candidate_id,
  realization_id,
  -operator_score,
  -targetId
)
reverse_id[
  ,
  reverse_id_rank := seq_len(.N),
  by = .(candidate_id, realization_id)
]

ascending_top50 <- ascending[
  ascending_rank_recomputed <= 50L,
  .(
    candidate_id,
    context_name,
    diseaseId,
    realization_id,
    operator_code,
    targetId,
    operator_score,
    ascending_rank_recomputed
  )
]
reverse_top50 <- reverse_id[
  reverse_id_rank <= 50L,
  .(
    candidate_id,
    realization_id,
    targetId,
    reverse_id_rank
  )
]
frozen_top50 <- matrix[
  selected_top50 == TRUE,
  .(
    candidate_id,
    realization_id,
    targetId,
    operator_rank
  )
]

if (
  nrow(ascending_top50) != 36800L ||
    nrow(reverse_top50) != 36800L ||
    nrow(frozen_top50) != 36800L
) {
  stop("R16_AUTHOR_SPEC_TIE_AUDIT_TOP50_DIMENSION_FAILED")
}

frozen_reconciliation <- merge(
  frozen_top50,
  ascending_top50[
    ,
    .(
      candidate_id,
      realization_id,
      targetId,
      ascending_rank_recomputed
    )
  ],
  by = c("candidate_id", "realization_id", "targetId"),
  all = TRUE,
  sort = TRUE
)
frozen_membership_exact <- (
  nrow(frozen_reconciliation) == 36800L &&
    all(!is.na(frozen_reconciliation$operator_rank)) &&
    all(!is.na(frozen_reconciliation$ascending_rank_recomputed))
)
frozen_order_exact <- (
  frozen_membership_exact &&
    all(
      frozen_reconciliation$operator_rank ==
        frozen_reconciliation$ascending_rank_recomputed
    )
)
if (!frozen_membership_exact || !frozen_order_exact) {
  stop("R16_AUTHOR_SPEC_TIE_AUDIT_FROZEN_TOP50_RECONCILIATION_FAILED")
}

tie_by_cell <- ascending[
  ,
  {
    score_50 <- operator_score[[50L]]
    score_51 <- operator_score[[51L]]
    original_ids <- targetId[seq_len(50L)]
    alternative_ids <- reverse_top50[
      candidate_id == .BY$candidate_id &
        realization_id == .BY$realization_id,
      targetId
    ]
    tie_mask <- operator_score == score_50
    intersection_count <- length(intersect(original_ids, alternative_ids))
    list(
      context_name = context_name[[1L]],
      diseaseId = diseaseId[[1L]],
      operator_code = operator_code[[1L]],
      O1 = as.integer(substr(operator_code[[1L]], 1L, 1L)),
      O2 = as.integer(substr(operator_code[[1L]], 2L, 2L)),
      O3 = as.integer(substr(operator_code[[1L]], 3L, 3L)),
      O4 = as.integer(substr(operator_code[[1L]], 4L, 4L)),
      O5 = as.integer(substr(operator_code[[1L]], 5L, 5L)),
      scored_hard_negative_targets = .N,
      rank50_score = score_50,
      rank51_score = score_51,
      rank50_51_margin = score_50 - score_51,
      exact_cutoff_tie = score_50 == score_51,
      cutoff_tie_block_size = sum(tie_mask),
      cutoff_tie_inside_top50 =
        sum(tie_mask & ascending_rank_recomputed <= 50L),
      cutoff_tie_outside_top50 =
        sum(tie_mask & ascending_rank_recomputed > 50L),
      ascending_vs_reverse_intersection = intersection_count,
      reverse_id_substitution = 1 - intersection_count / 50
    )
  },
  by = .(candidate_id, realization_id)
]
setorder(tie_by_cell, candidate_id, realization_id)
tie_by_cell[
  ,
  `:=`(
    frozen_top50_membership_reproduced = frozen_membership_exact,
    frozen_top50_order_reproduced = frozen_order_exact
  )
]

if (
  nrow(tie_by_cell) != 736L ||
    sum(tie_by_cell$exact_cutoff_tie) != 385L ||
    sum(tie_by_cell$reverse_id_substitution > 0) != 385L
) {
  stop("R16_AUTHOR_SPEC_TIE_AUDIT_EXPECTED_TIE_COUNTS_FAILED")
}

summarise_ties <- function(value, scope, score_transform) {
  tied <- value[exact_cutoff_tie == TRUE]
  changed <- value[reverse_id_substitution > 0]
  data.table(
    scope = scope,
    score_transform = score_transform,
    cells = nrow(value),
    exact_cutoff_tie_cells = nrow(tied),
    exact_cutoff_tie_rate = nrow(tied) / nrow(value),
    reverse_id_changed_cells = nrow(changed),
    mean_reverse_id_substitution_all_cells =
      mean(value$reverse_id_substitution),
    median_reverse_id_substitution_all_cells =
      median(value$reverse_id_substitution),
    mean_reverse_id_substitution_changed_cells =
      if (nrow(changed) > 0L) {
        mean(changed$reverse_id_substitution)
      } else {
        NA_real_
      },
    maximum_reverse_id_substitution =
      max(value$reverse_id_substitution),
    median_cutoff_tie_block_size =
      if (nrow(tied) > 0L) median(tied$cutoff_tie_block_size) else NA_real_,
    q25_cutoff_tie_block_size =
      if (nrow(tied) > 0L) {
        as.numeric(quantile(tied$cutoff_tie_block_size, 0.25))
      } else {
        NA_real_
      },
    q75_cutoff_tie_block_size =
      if (nrow(tied) > 0L) {
        as.numeric(quantile(tied$cutoff_tie_block_size, 0.75))
      } else {
        NA_real_
      },
    maximum_cutoff_tie_block_size =
      if (nrow(tied) > 0L) max(tied$cutoff_tie_block_size) else NA_integer_,
    median_tie_members_inside_top50 =
      if (nrow(tied) > 0L) {
        median(tied$cutoff_tie_inside_top50)
      } else {
        NA_real_
      },
    median_tie_members_outside_top50 =
      if (nrow(tied) > 0L) {
        median(tied$cutoff_tie_outside_top50)
      } else {
        NA_real_
      },
    maximum_tie_members_outside_top50 =
      if (nrow(tied) > 0L) {
        max(tied$cutoff_tie_outside_top50)
      } else {
        NA_integer_
      }
  )
}

tie_summary <- rbindlist(
  list(
    summarise_ties(tie_by_cell, "all_736_cells", "all"),
    summarise_ties(
      tie_by_cell[O3 == 0L],
      "O3_0_cells",
      "raw_released_score"
    ),
    summarise_ties(
      tie_by_cell[O3 == 1L],
      "O3_1_cells",
      "within_datasource_context_percentile"
    )
  ),
  use.names = TRUE
)

make_pairwise_audit <- function(original_memberships, reverse_memberships) {
  context_ids <- sort(unique(original_memberships$candidate_id))
  output <- vector("list", length(context_ids))

  for (context_index in seq_along(context_ids)) {
    candidate <- context_ids[[context_index]]
    original_context <- original_memberships[candidate_id == candidate]
    reverse_context <- reverse_memberships[candidate_id == candidate]
    codes <- unique(
      original_context[
        ,
        .(
          realization_id,
          operator_code,
          context_name,
          diseaseId
        )
      ]
    )
    setorder(codes, realization_id)
    if (nrow(codes) != 32L) {
      stop("R16_AUTHOR_SPEC_TIE_AUDIT_CONTEXT_NOT_32_SPECIFICATIONS")
    }

    original_sets <- split(
      original_context$targetId,
      original_context$realization_id
    )
    reverse_sets <- split(
      reverse_context$targetId,
      reverse_context$realization_id
    )
    combinations <- combn(seq_len(nrow(codes)), 2L)
    rows <- vector("list", ncol(combinations))

    for (pair_index in seq_len(ncol(combinations))) {
      left <- codes[combinations[1L, pair_index]]
      right <- codes[combinations[2L, pair_index]]
      left_bits <- as.integer(
        strsplit(left$operator_code, "", fixed = TRUE)[[1L]]
      )
      right_bits <- as.integer(
        strsplit(right$operator_code, "", fixed = TRUE)[[1L]]
      )
      changed_positions <- which(left_bits != right_bits)
      original_intersection <- length(
        intersect(
          original_sets[[left$realization_id]],
          original_sets[[right$realization_id]]
        )
      )
      reverse_intersection <- length(
        intersect(
          reverse_sets[[left$realization_id]],
          reverse_sets[[right$realization_id]]
        )
      )
      original_distance <- 1 - original_intersection / 50
      reverse_distance <- 1 - reverse_intersection / 50

      rows[[pair_index]] <- data.table(
        candidate_id = candidate,
        context_name = left$context_name,
        diseaseId = left$diseaseId,
        realization_a = left$realization_id,
        realization_b = right$realization_id,
        operator_code_a = left$operator_code,
        operator_code_b = right$operator_code,
        five_factor_hamming_distance = length(changed_positions),
        active_O2_O5_hamming_distance =
          sum(left_bits[2L:5L] != right_bits[2L:5L]),
        direct_toggle_factor =
          if (length(changed_positions) == 1L) {
            paste0("O", changed_positions)
          } else {
            ""
          },
        unchanged_O2_level =
          if (
            length(changed_positions) == 1L &&
              changed_positions[[1L]] != 2L
          ) {
            left_bits[[2L]]
          } else {
            NA_integer_
          },
        ascending_id_intersection = original_intersection,
        reverse_id_intersection = reverse_intersection,
        ascending_id_substitution = original_distance,
        reverse_id_substitution = reverse_distance,
        distance_shift_reverse_minus_ascending =
          reverse_distance - original_distance
      )
    }
    output[[context_index]] <- rbindlist(rows, use.names = TRUE)
  }
  rbindlist(output, use.names = TRUE)
}

pairwise <- make_pairwise_audit(ascending_top50, reverse_top50)
setorder(pairwise, candidate_id, realization_a, realization_b)
if (
  nrow(pairwise) != 11408L ||
    sum(pairwise$five_factor_hamming_distance == 1L) != 1840L
) {
  stop("R16_AUTHOR_SPEC_TIE_AUDIT_PAIRWISE_DIMENSION_FAILED")
}

summarise_factor <- function(
  value,
  contrast_scope,
  factor,
  O2_grouping
) {
  data.table(
    contrast_scope = contrast_scope,
    factor = factor,
    O2_grouping = O2_grouping,
    context_pair_rows = nrow(value),
    ascending_id_mean_substitution =
      mean(value$ascending_id_substitution),
    reverse_id_mean_substitution =
      mean(value$reverse_id_substitution),
    mean_shift_reverse_minus_ascending =
      mean(value$distance_shift_reverse_minus_ascending),
    median_shift_reverse_minus_ascending =
      median(value$distance_shift_reverse_minus_ascending),
    minimum_shift_reverse_minus_ascending =
      min(value$distance_shift_reverse_minus_ascending),
    maximum_shift_reverse_minus_ascending =
      max(value$distance_shift_reverse_minus_ascending),
    rows_with_distance_change =
      sum(value$distance_shift_reverse_minus_ascending != 0)
  )
}

factor_rows <- vector("list", 11L)
factor_index <- 0L
for (factor_name in paste0("O", 1L:5L)) {
  factor_index <- factor_index + 1L
  factor_rows[[factor_index]] <- summarise_factor(
    pairwise[
      five_factor_hamming_distance == 1L &
        direct_toggle_factor == factor_name
    ],
    "marginal_direct_toggle",
    factor_name,
    "averaged_over_O2"
  )
}
for (factor_name in c("O3", "O4", "O5")) {
  for (O2_level in 0L:1L) {
    factor_index <- factor_index + 1L
    factor_rows[[factor_index]] <- summarise_factor(
      pairwise[
        five_factor_hamming_distance == 1L &
          direct_toggle_factor == factor_name &
          unchanged_O2_level == O2_level
      ],
      "O2_conditional_direct_toggle",
      factor_name,
      if (O2_level == 0L) {
        "datasource"
      } else {
        "evidence_lineage"
      }
    )
  }
}
factor_effects <- rbindlist(factor_rows, use.names = TRUE)

global_sensitivity <- data.table(
  metric = c(
    "frozen_top50_memberships_reproduced",
    "frozen_top50_orders_reproduced",
    "context_specification_cells",
    "exact_cutoff_tie_cells",
    "mean_reverse_id_list_substitution_over_736_cells",
    "median_cutoff_tie_block_size_among_tied_cells",
    "q25_cutoff_tie_block_size_among_tied_cells",
    "q75_cutoff_tie_block_size_among_tied_cells",
    "maximum_cutoff_tie_block_size",
    "context_specification_pair_rows",
    "ascending_id_all_pair_mean_substitution",
    "reverse_id_all_pair_mean_substitution",
    "all_pair_mean_shift_reverse_minus_ascending",
    "all_pair_rows_with_distance_change",
    "minimum_pairwise_distance_shift",
    "maximum_pairwise_distance_shift"
  ),
  value = as.character(c(
    frozen_membership_exact,
    frozen_order_exact,
    nrow(tie_by_cell),
    sum(tie_by_cell$exact_cutoff_tie),
    format(mean(tie_by_cell$reverse_id_substitution), digits = 17),
    format(
      median(
        tie_by_cell[
          exact_cutoff_tie == TRUE,
          cutoff_tie_block_size
        ]
      ),
      digits = 17
    ),
    format(
      quantile(
        tie_by_cell[
          exact_cutoff_tie == TRUE,
          cutoff_tie_block_size
        ],
        0.25
      ),
      digits = 17
    ),
    format(
      quantile(
        tie_by_cell[
          exact_cutoff_tie == TRUE,
          cutoff_tie_block_size
        ],
        0.75
      ),
      digits = 17
    ),
    max(
      tie_by_cell[
        exact_cutoff_tie == TRUE,
        cutoff_tie_block_size
      ]
    ),
    nrow(pairwise),
    format(mean(pairwise$ascending_id_substitution), digits = 17),
    format(mean(pairwise$reverse_id_substitution), digits = 17),
    format(
      mean(pairwise$distance_shift_reverse_minus_ascending),
      digits = 17
    ),
    sum(pairwise$distance_shift_reverse_minus_ascending != 0),
    format(
      min(pairwise$distance_shift_reverse_minus_ascending),
      digits = 17
    ),
    format(
      max(pairwise$distance_shift_reverse_minus_ascending),
      digits = 17
    )
  )),
  denominator_or_scope = c(
    "36800 selected memberships",
    "36800 selected memberships",
    "23 contexts x 32 specifications",
    "736 cells",
    "736 cells",
    "385 exact-cutoff-tie cells",
    "385 exact-cutoff-tie cells",
    "385 exact-cutoff-tie cells",
    "385 exact-cutoff-tie cells",
    "23 contexts x 496 unordered specification pairs",
    "11408 pair rows",
    "11408 pair rows",
    "11408 pair rows",
    "11408 pair rows",
    "11408 pair rows",
    "11408 pair rows"
  )
)

dir.create(output_root, recursive = TRUE, showWarnings = FALSE)
fwrite(
  tie_by_cell,
  file.path(output_root, "R16_AUTHOR_SPEC_TIE_BLOCK_BY_CELL.tsv"),
  sep = "\t",
  quote = FALSE,
  na = ""
)
fwrite(
  tie_summary,
  file.path(output_root, "R16_AUTHOR_SPEC_TIE_BLOCK_SUMMARY.tsv"),
  sep = "\t",
  quote = FALSE,
  na = ""
)
fwrite(
  pairwise,
  file.path(output_root, "R16_REVERSE_ID_DISTANCE_BY_CONTEXT_PAIR.tsv"),
  sep = "\t",
  quote = FALSE,
  na = ""
)
fwrite(
  factor_effects,
  file.path(output_root, "R16_REVERSE_ID_FACTOR_EFFECTS.tsv"),
  sep = "\t",
  quote = FALSE,
  na = ""
)
fwrite(
  global_sensitivity,
  file.path(output_root, "R16_REVERSE_ID_GLOBAL_SENSITIVITY_SUMMARY.tsv"),
  sep = "\t",
  quote = FALSE,
  na = ""
)

cat("R16_AUTHOR_SPEC_TIE_SENSITIVITY_AUDIT=PASS\n")
cat("CELL_ROWS=", nrow(tie_by_cell), "\n", sep = "")
cat(
  "EXACT_CUTOFF_TIE_CELLS=",
  sum(tie_by_cell$exact_cutoff_tie),
  "\n",
  sep = ""
)
cat(
  "MEAN_REVERSE_ID_LIST_SUBSTITUTION=",
  format(mean(tie_by_cell$reverse_id_substitution), digits = 17),
  "\n",
  sep = ""
)
cat(
  "MEDIAN_TIED_BLOCK_SIZE=",
  median(
    tie_by_cell[
      exact_cutoff_tie == TRUE,
      cutoff_tie_block_size
    ]
  ),
  "\n",
  sep = ""
)
cat(
  "MAXIMUM_TIED_BLOCK_SIZE=",
  max(
    tie_by_cell[
      exact_cutoff_tie == TRUE,
      cutoff_tie_block_size
    ]
  ),
  "\n",
  sep = ""
)
cat("PAIRWISE_ROWS=", nrow(pairwise), "\n", sep = "")
cat(
  "ASCENDING_ID_ALL_PAIR_MEAN=",
  format(mean(pairwise$ascending_id_substitution), digits = 17),
  "\n",
  sep = ""
)
cat(
  "REVERSE_ID_ALL_PAIR_MEAN=",
  format(mean(pairwise$reverse_id_substitution), digits = 17),
  "\n",
  sep = ""
)
cat(
  "ALL_PAIR_MEAN_SHIFT=",
  format(
    mean(pairwise$distance_shift_reverse_minus_ascending),
    digits = 17
  ),
  "\n",
  sep = ""
)
