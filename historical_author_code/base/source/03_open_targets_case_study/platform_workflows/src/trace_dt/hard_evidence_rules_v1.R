# TRACE-DT hard-evidence rules v1
# Outcome-free freeze: 2026-07-24
# Legal unit: exact diseaseId x Ensembl targetId.
# This file defines primary-hard-positive exclusion matches. Historical
# internal variables named "eligible" mean eligible to trigger exclusion, not
# eligible for nomination. The scored pool requires t0_hard_negative=TRUE.
# This file does not read prospective outcome data or rank targets.

field_text_v1 <- function(df, field_name) {
  if (!field_name %in% names(df)) return(rep("", nrow(df)))
  x <- df[[field_name]]
  if (is.data.frame(x)) {
    return(vapply(
      seq_len(nrow(x)),
      function(i) {
        value <- unlist(x[i, , drop = FALSE], recursive = TRUE, use.names = FALSE)
        value <- trimws(tolower(as.character(value)))
        paste(sort(unique(value[nzchar(value)])), collapse = "|")
      },
      character(1)
    ))
  }
  if (is.list(x)) {
    return(vapply(
      x,
      function(value) {
        value <- unlist(value, recursive = TRUE, use.names = FALSE)
        value <- trimws(tolower(as.character(value)))
        paste(sort(unique(value[nzchar(value)])), collapse = "|")
      },
      character(1)
    ))
  }
  value <- trimws(tolower(as.character(x)))
  value[is.na(value)] <- ""
  value
}

field_numeric_v1 <- function(df, field_name) {
  if (!field_name %in% names(df)) return(rep(NA_real_, nrow(df)))
  suppressWarnings(as.numeric(df[[field_name]]))
}

contains_token_v1 <- function(value, tokens) {
  pattern <- paste0("(^|\\|)(", paste(tokens, collapse = "|"), ")(\\||$)")
  grepl(pattern, value, perl = TRUE)
}

hard_evidence_eligibility_v1 <- function(df, datasource_id) {
  n <- nrow(df)
  eligible <- rep(FALSE, n)
  hard_class <- rep("NOT_PRIMARY", n)
  reason <- rep("DATASOURCE_NOT_IN_PRIMARY_WHITELIST", n)

  confidence <- field_text_v1(df, "confidence")
  significance <- field_text_v1(df, "clinicalSignificances")
  origin <- field_text_v1(df, "alleleOrigins")
  stage <- toupper(field_text_v1(df, "clinicalStage"))
  stop_categories <- field_text_v1(df, "trialStopReasonCategories")
  driver_methods <- field_text_v1(df, "significantDriverMethods")
  resource_score <- field_numeric_v1(df, "resourceScore")
  p_value <- field_numeric_v1(df, "resourceScore")
  beta <- field_numeric_v1(df, "beta")
  odds_ratio <- field_numeric_v1(df, "oddsRatio")

  if (datasource_id == "clinical_precedence") {
    hard_class[] <- "CLINICAL"
    permitted_stage <- stage %in% c(
      "PHASE_2", "PHASE_2_3", "PHASE_3", "PHASE_4",
      "PREAPPROVAL", "APPROVAL"
    )
    prohibited_stop <- grepl(
      "(^|\\|)(negative|safety_sideeffects)(\\||$)",
      stop_categories,
      perl = TRUE
    )
    eligible <- permitted_stage & !prohibited_stop
    reason <- ifelse(
      eligible,
      "QUALIFY_PHASE_II_PLUS_OR_REGULATORY_WITHOUT_NEGATIVE_OR_SAFETY_STOP",
      "FAIL_STAGE_OR_STOP_REASON"
    )
  } else if (datasource_id == "clingen") {
    hard_class[] <- "HUMAN_GENETIC"
    eligible <- confidence %in% c("strong", "definitive")
    reason <- ifelse(eligible, "QUALIFY_STRONG_OR_DEFINITIVE", "FAIL_CONFIDENCE")
  } else if (datasource_id == "gene2phenotype") {
    hard_class[] <- "HUMAN_GENETIC"
    eligible <- confidence %in% c(
      "strong", "definitive", "both rd and if", "both_rd_and_if"
    )
    reason <- ifelse(eligible, "QUALIFY_STRONG_CAUSAL_G2P", "FAIL_CONFIDENCE")
  } else if (datasource_id == "genomics_england") {
    hard_class[] <- "HUMAN_GENETIC"
    eligible <- confidence == "green"
    reason <- ifelse(eligible, "QUALIFY_DIAGNOSTIC_GRADE_GREEN", "FAIL_CONFIDENCE")
  } else if (datasource_id == "eva") {
    hard_class[] <- "HUMAN_GENETIC"
    pathogenic <- contains_token_v1(
      significance,
      c("pathogenic", "likely pathogenic")
    )
    reviewed <- confidence %in% c(
      "criteria provided, single submitter",
      "criteria provided, multiple submitters, no conflicts"
    )
    germline <- contains_token_v1(
      origin,
      c("germline", "de novo", "maternal", "paternal", "inherited")
    )
    eligible <- pathogenic & reviewed & germline
    reason <- ifelse(
      eligible,
      "QUALIFY_REVIEWED_PATHOGENIC_GERMLINE",
      "FAIL_SIGNIFICANCE_REVIEW_OR_ORIGIN"
    )
  } else if (datasource_id == "gene_burden") {
    hard_class[] <- "HUMAN_GENETIC"
    effect_resolved <- is.finite(beta) | is.finite(odds_ratio)
    eligible <- is.finite(p_value) & p_value <= 5e-8 & effect_resolved
    reason <- ifelse(
      eligible,
      "QUALIFY_GENOME_WIDE_SIGNIFICANT_BURDEN_WITH_EFFECT",
      "FAIL_PVALUE_OR_EFFECT"
    )
  } else if (datasource_id == "gwas_credible_sets") {
    hard_class[] <- "HUMAN_GENETIC"
    eligible <- is.finite(resource_score) & resource_score >= 0.5
    reason <- ifelse(
      eligible,
      "QUALIFY_L2G_AT_LEAST_0_5",
      "FAIL_L2G_STRONG_THRESHOLD"
    )
  } else if (datasource_id == "orphanet") {
    hard_class[] <- "HUMAN_GENETIC"
    eligible <- confidence == "assessed"
    reason <- ifelse(
      eligible,
      "QUALIFY_ORPHANET_ASSESSED_RELATION",
      "FAIL_CONFIDENCE"
    )
  } else if (datasource_id == "uniprot_variants") {
    hard_class[] <- "HUMAN_GENETIC"
    eligible <- confidence == "high"
    reason <- ifelse(
      eligible,
      "QUALIFY_HIGH_CONFIDENCE_CURATED_VARIANT",
      "FAIL_CONFIDENCE"
    )
  } else if (datasource_id == "cancer_gene_census") {
    hard_class[] <- "SOMATIC_CANCER_GENETIC"
    eligible <- is.finite(resource_score) & resource_score >= 0.5
    reason <- ifelse(
      eligible,
      "QUALIFY_CGC_CAUSAL_SCORE_AT_LEAST_0_5",
      "FAIL_CGC_CAUSAL_THRESHOLD"
    )
  } else if (datasource_id == "eva_somatic") {
    hard_class[] <- "SOMATIC_CANCER_GENETIC"
    pathogenic <- contains_token_v1(
      significance,
      c("pathogenic", "likely pathogenic")
    )
    reviewed <- confidence %in% c(
      "criteria provided, single submitter",
      "criteria provided, multiple submitters, no conflicts"
    )
    somatic <- contains_token_v1(origin, "somatic")
    eligible <- pathogenic & reviewed & somatic
    reason <- ifelse(
      eligible,
      "QUALIFY_REVIEWED_PATHOGENIC_SOMATIC",
      "FAIL_SIGNIFICANCE_REVIEW_OR_ORIGIN"
    )
  } else if (datasource_id == "intogen") {
    hard_class[] <- "SOMATIC_CANCER_GENETIC"
    eligible <- (
      is.finite(resource_score) &
      resource_score <= 0.01 &
      nzchar(driver_methods)
    )
    reason <- ifelse(
      eligible,
      "QUALIFY_SIGNIFICANT_DRIVER_Q_LE_0_01",
      "FAIL_DRIVER_METHOD_OR_QVALUE"
    )
  }

  data.frame(
    primary_hard_eligible = eligible,
    hard_class = hard_class,
    source_rule_reason = reason,
    stringsAsFactors = FALSE
  )
}
