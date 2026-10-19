from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

import pyarrow.parquet as pq


PATCH_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = PATCH_ROOT / "workflow" / "reconstruct_release_matrix.R"
CONTRACTS = PATCH_ROOT / "contracts"
MAPPING = (
    PATCH_ROOT
    / "data"
    / "derived"
    / "ot26_06"
    / "source_unit_provenance_mapping.parquet"
)

EXPECTED_CONTRACTS = {
    "specification_realizations_32.tsv": (
        32,
        {"realization_id", "operator_code", "O1", "O2", "O3", "O4", "O5"},
    ),
    "baseline_registry_6.tsv": (
        6,
        {"baseline_id", "baseline_name", "legal_unit", "metric", "budget"},
    ),
    "R16_CANONICAL_KEY_PROVENANCE_CONTRACT.tsv": (
        20,
        {
            "datasource_id",
            "local_dataset",
            "key_tier_priority_first_complete_wins",
            "mapping_join_key",
        },
    ),
    "datasource_registry_20.tsv": (
        20,
        {"datasourceId", "datatypeId", "weight", "toPropagate"},
    ),
    "context_identifier_contract_23.tsv": (
        23,
        {"candidate_id", "context_name", "open_targets_disease_id"},
    ),
}

EXPECTED_MAPPING_COLUMNS = [
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
    "checked_date",
]
EXPECTED_MAPPING_SHA256 = (
    "504eeac576ef877560bdb901ab3f8bc361cd8852cf71e23c3cd86b5cae33949a"
)


def _rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        values = list(reader)
        assert reader.fieldnames is not None
        return reader.fieldnames, values


def _rscript() -> str:
    candidates = [
        os.environ.get("R_SCRIPT"),
        shutil.which("Rscript"),
        r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise AssertionError("Rscript was not found; set R_SCRIPT to its absolute path")


def test_v11_contract_preflight_executes_without_raw_inputs() -> None:
    completed = subprocess.run(
        [_rscript(), str(WORKFLOW), "--contracts-only"],
        cwd=PATCH_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
        check=False,
    )
    combined = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode == 0, combined
    for token in (
        "TRACE_DT_V11_CONTRACT_PREFLIGHT",
        "MODE=CONTRACTS_ONLY_NO_RAW_INPUTS",
        "OPERATOR_ROWS=32",
        "BASELINE_ROWS=6",
        "CANONICAL_KEY_ROWS=20",
        "DATASOURCE_ROWS=20",
        "CONTEXT_ROWS=23",
        "PROVENANCE_MAPPING_ROWS=528893",
        "RAW_INPUTS_ACCESSED=FALSE",
        "DOWNLOADS_PERFORMED=FALSE",
        "FORMAL_MATRIX_RUN=FALSE",
        "CONTRACT_PREFLIGHT_PASS",
    ):
        assert token in completed.stdout


def test_packaged_contracts_and_mapping_match_declared_schema() -> None:
    for filename, (expected_rows, required_fields) in EXPECTED_CONTRACTS.items():
        fields, values = _rows(CONTRACTS / filename)
        assert len(values) == expected_rows
        assert required_fields.issubset(fields)

    operator_fields, operator_rows = _rows(
        CONTRACTS / "specification_realizations_32.tsv"
    )
    assert "operator_code" in operator_fields
    assert [row["operator_code"] for row in operator_rows] == [
        format(index, "05b") for index in range(32)
    ]

    metadata_fields, metadata_rows = _rows(
        CONTRACTS / "provenance_mapping_metadata.tsv"
    )
    assert {
        "row_count",
        "row_group_count",
        "byte_size",
        "sha256",
        "columns_pipe",
    }.issubset(metadata_fields)
    assert len(metadata_rows) == 1
    metadata = metadata_rows[0]

    parquet = pq.ParquetFile(MAPPING)
    assert parquet.metadata.num_rows == 528_893
    assert parquet.metadata.num_row_groups == 19
    assert parquet.schema_arrow.names == EXPECTED_MAPPING_COLUMNS
    assert int(metadata["row_count"]) == parquet.metadata.num_rows
    assert int(metadata["row_group_count"]) == parquet.metadata.num_row_groups
    assert int(metadata["byte_size"]) == MAPPING.stat().st_size
    assert metadata["columns_pipe"].split("|") == parquet.schema_arrow.names
    assert hashlib.sha256(MAPPING.read_bytes()).hexdigest() == EXPECTED_MAPPING_SHA256
    assert metadata["sha256"] == EXPECTED_MAPPING_SHA256


def test_preflight_is_positioned_before_formal_raw_cli_validation() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    preflight_call = source.index('if (isTRUE(cli[["contracts-only"]]))')
    formal_required_cli = source.index(
        'required_cli <- c("release-root", "output-root", "release-id", "release-date")'
    )
    raw_open = source.index(
        'open_dataset(file.path(ot_root, "association_overall_direct"))'
    )
    assert preflight_call < formal_required_cli < raw_open
