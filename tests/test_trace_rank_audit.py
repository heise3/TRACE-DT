import csv
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_rank_audit import (
    build_cell,
    exact_intersection_bounds,
    expected_intersection,
    integerize_proportional_budget,
    run,
    validate_receipt_completed_utc,
    validate_tie_tolerance,
)


def admissible_lists(cell):
    for chosen in itertools.combinations(sorted(cell.tied), cell.remaining_seats):
        yield cell.strict_above | frozenset(chosen)


class TestTraceRankAudit(unittest.TestCase):
    def test_header_only_input_fails_closed_with_nonzero_cli_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "header_only.tsv"
            output_dir = temp_path / "out"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "no scored candidate rows"):
                run(input_path, output_dir, budget=1)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "trace_rank_audit.py"),
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(temp_path / "cli_out"),
                    "--budget",
                    "1",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, "")
            self.assertIn("no scored candidate rows", completed.stderr)
            self.assertTrue(completed.stderr.startswith("ERROR: "))
            self.assertNotIn("Traceback", completed.stderr)
            self.assertFalse((temp_path / "cli_out" / "audit_receipt.json").exists())

    def test_proportional_budget_uses_floor_with_minimum_one(self):
        self.assertEqual(integerize_proportional_budget(100, "0.005"), 1)
        self.assertEqual(integerize_proportional_budget(500, "0.005"), 2)
        self.assertEqual(integerize_proportional_budget(599, "0.005"), 2)
        self.assertEqual(integerize_proportional_budget(600, "0.005"), 3)
        self.assertEqual(integerize_proportional_budget(12680, "0.02"), 253)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            integerize_proportional_budget(0, "0.01")
        with self.assertRaisesRegex(ValueError, "0 < proportion <= 1"):
            integerize_proportional_budget(100, "1.01")

    def test_no_tie_identical_lists(self):
        scores = {f"G{i:03d}": float(100 - i) for i in range(60)}
        a = build_cell("C1", "A", scores, 50)
        b = build_cell("C1", "B", scores, 50)
        self.assertEqual(len(a.strict_above), 49)
        self.assertEqual(len(a.tied), 1)
        self.assertEqual(len(a.necessary), 50)
        self.assertEqual(a.necessary, a.deterministic)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertEqual(a.guaranteed, a.necessary)
        self.assertEqual(len(caught), 1)
        self.assertIs(caught[0].category, DeprecationWarning)
        self.assertIn("use Cell.necessary", str(caught[0].message))
        self.assertEqual(exact_intersection_bounds(a, b), (50, 50))
        self.assertEqual(expected_intersection(a, b), 50)

    def test_all_tied_lists_have_exact_bounds(self):
        scores_a = {f"G{i:03d}": 1.0 for i in range(100)}
        scores_b = {f"G{i:03d}": 1.0 for i in range(50, 150)}
        a = build_cell("C1", "A", scores_a, 50)
        b = build_cell("C1", "B", scores_b, 50)
        minimum, maximum = exact_intersection_bounds(a, b)
        self.assertEqual(minimum, 0)
        self.assertEqual(maximum, 50)
        self.assertEqual(expected_intersection(a, b), 12.5)

    def test_capacity_failure(self):
        scores = {f"G{i:03d}": float(i) for i in range(49)}
        with self.assertRaisesRegex(ValueError, "scores < B=50"):
            build_cell("C1", "A", scores, 50)

    def test_deterministic_tie_break_uses_candidate_identifier_only(self):
        scores = {"G003": 1.0, "G001": 1.0, "G002": 1.0}
        cell = build_cell("C1", "S1", scores, 2)
        self.assertEqual(cell.strict_above, frozenset())
        self.assertEqual(cell.necessary, frozenset())
        self.assertEqual(cell.tied, frozenset({"G001", "G002", "G003"}))
        self.assertEqual(cell.deterministic, frozenset({"G001", "G002"}))
        self.assertEqual(cell.possible, cell.tied)

    def test_chance_overlap_uses_each_scored_universe(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            output_dir = temp_path / "out"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                + "".join(f"C1\tA{i}\tS1\t{100-i}\n" for i in range(10))
                + "".join(f"C1\tA{i}\tS2\t{100-i}\n" for i in range(5, 15)),
                encoding="utf-8",
            )
            run(input_path, output_dir, budget=2)
            with (output_dir / "pairwise_audit.tsv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                row = next(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(int(row["candidate_a_n"]), 10)
            self.assertEqual(int(row["candidate_b_n"]), 10)
            self.assertEqual(int(row["candidate_shared_n"]), 5)
            self.assertEqual(float(row["intersection_expected_chance"]), 0.2)

    def test_sharp_bounds_equal_exhaustive_enumeration(self):
        cases = [
            (
                {"a": 3, "b": 2, "c": 2, "d": 1},
                {"a": 3, "b": 2, "c": 1, "e": 2},
                2,
            ),
            ({"a": 1, "b": 1, "c": 1}, {"b": 1, "c": 1, "d": 1}, 2),
            (
                {"a": 4, "b": 3, "c": 2, "d": 2, "e": 1},
                {"a": 4, "c": 3, "d": 3, "f": 1},
                3,
            ),
            ({"a": 3, "b": 2, "c": 1}, {"a": 3, "b": 2, "c": 1}, 2),
        ]
        for scores_a, scores_b, budget in cases:
            with self.subTest(scores_a=scores_a, scores_b=scores_b, budget=budget):
                a = build_cell("C1", "A", scores_a, budget)
                b = build_cell("C1", "B", scores_b, budget)
                overlaps = [
                    len(x & y)
                    for x in admissible_lists(a)
                    for y in admissible_lists(b)
                ]
                self.assertEqual(
                    exact_intersection_bounds(a, b), (min(overlaps), max(overlaps))
                )

    def test_tolerance_expands_boundary_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            output_dir = temp_path / "out"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                "C1\ta\tS1\t1.0\nC1\tb\tS1\t0.9\nC1\tc\tS1\t0.8999999999995\n"
                "C1\ta\tS2\t1.0\nC1\tb\tS2\t0.9\nC1\tc\tS2\t0.8999999999995\n",
                encoding="utf-8",
            )
            summary = run(input_path, output_dir, budget=2, tie_tolerance=1e-12)
            self.assertEqual(summary["tie_tolerance"], 1e-12)
            with (output_dir / "cell_contract.tsv").open(
                "r", encoding="utf-8"
            ) as handle:
                row = next(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(int(row["tie_block_n"]), 2)
            receipt = json.loads(
                (output_dir / "audit_receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["engine_version"], "1.2.1")

    def test_necessary_membership_equals_intersection_of_all_legal_lists(self):
        """Exhaustively verify the defining quantifier for all N <= 6."""
        for n in range(1, 7):
            candidate_ids = tuple(f"G{i}" for i in range(n))
            for score_pattern in itertools.product(range(3), repeat=n):
                scores = dict(zip(candidate_ids, map(float, score_pattern)))
                for budget in range(1, n + 1):
                    cell = build_cell("C1", "S1", scores, budget)
                    legal = list(admissible_lists(cell))
                    intersection = frozenset.intersection(*legal)
                    union = frozenset.union(*legal)
                    self.assertEqual(cell.necessary, intersection)
                    self.assertEqual(cell.possible, union)
                    self.assertEqual(len(cell.deterministic), budget)
                    self.assertTrue(cell.necessary <= cell.deterministic)
                    for candidate in candidate_ids:
                        probability = (
                            1.0
                            if candidate in cell.strict_above
                            else cell.tie_probability
                            if candidate in cell.tied
                            else 0.0
                        )
                        self.assertEqual(candidate in cell.necessary, probability == 1.0)
                    if cell.remaining_seats == len(cell.tied):
                        self.assertEqual(len(cell.necessary), budget)
                        self.assertEqual(cell.necessary, cell.possible)

    def test_sharp_bounds_exhaustive_all_three_level_scores_n4(self):
        """Exhaustively compare analytic bounds with legal-list enumeration.

        The two universe layouts cover identical and partially overlapping
        candidate sets. Every three-level score assignment and every legal
        budget for N=4 is tested.
        """
        universes = (
            (("a", "b", "c", "d"), ("a", "b", "c", "d")),
            (("a", "b", "c", "d"), ("b", "c", "d", "e")),
        )
        patterns = tuple(itertools.product(range(3), repeat=4))
        for ids_a, ids_b in universes:
            for pattern_a in patterns:
                scores_a = dict(zip(ids_a, map(float, pattern_a)))
                for pattern_b in patterns:
                    scores_b = dict(zip(ids_b, map(float, pattern_b)))
                    for budget in range(1, 5):
                        a = build_cell("C1", "A", scores_a, budget)
                        b = build_cell("C1", "B", scores_b, budget)
                        overlaps = tuple(
                            len(x & y)
                            for x in admissible_lists(a)
                            for y in admissible_lists(b)
                        )
                        self.assertEqual(
                            exact_intersection_bounds(a, b),
                            (min(overlaps), max(overlaps)),
                        )

    def test_output_uses_necessary_semantics_for_unique_cutoff(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            output_dir = temp_path / "out"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                "C1\ta\tS1\t3\nC1\tb\tS1\t2\nC1\tc\tS1\t1\n"
                "C1\ta\tS2\t3\nC1\tb\tS2\t2\nC1\tc\tS2\t1\n",
                encoding="utf-8",
            )
            run(input_path, output_dir, budget=2)
            with (output_dir / "cell_contract.tsv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertTrue(all(int(row["necessary_n"]) == 2 for row in rows))
            with (output_dir / "target_membership.tsv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                membership = list(csv.DictReader(handle, delimiter="\t"))
            selected = [
                row
                for row in membership
                if row["specification_id"] == "S1"
                and int(row["necessary_selected"]) == 1
            ]
            self.assertEqual({row["candidate_id"] for row in selected}, {"a", "b"})
            self.assertTrue(
                all(float(row["uniform_tie_selection_probability"]) == 1.0 for row in selected)
            )

    def test_negative_tolerance_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            build_cell("C1", "S1", {"a": 2.0, "b": 1.0}, 1, -1e-12)

    def test_nonfinite_and_malformed_tolerances_are_controlled_cli_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                "C1\ta\tS1\t2\nC1\tb\tS1\t1\n",
                encoding="utf-8",
            )
            for index, token in enumerate(
                (
                    "nan",
                    "NaN",
                    "inf",
                    "+inf",
                    "+Inf",
                    "-inf",
                    "-Inf",
                    "not-a-number",
                )
            ):
                with self.subTest(token=token):
                    output_dir = temp_path / f"invalid_tolerance_{index}"
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(ROOT / "trace_rank_audit.py"),
                            "--input",
                            str(input_path),
                            "--output-dir",
                            str(output_dir),
                            "--budget",
                            "1",
                            "--tie-tolerance",
                            token,
                        ],
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, "")
                    self.assertTrue(
                        completed.stderr.startswith("ERROR: ")
                        or "error:" in completed.stderr.lower()
                    )
                    if token.lower() != "-inf":
                        self.assertIn("finite non-negative number", completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)
                    self.assertFalse((output_dir / "audit_receipt.json").exists())
                    self.assertFalse(output_dir.exists())

        for value in (float("nan"), float("inf"), float("-inf"), "bad"):
            with self.subTest(direct_value=value):
                with self.assertRaisesRegex(ValueError, "finite non-negative number"):
                    validate_tie_tolerance(value)
                with self.assertRaisesRegex(ValueError, "finite non-negative number"):
                    build_cell("C1", "S1", {"a": 2.0, "b": 1.0}, 1, value)

    def test_receipt_timestamp_requires_timezone_aware_utc(self):
        self.assertEqual(
            validate_receipt_completed_utc("2026-08-08T00:00:00Z"),
            "2026-08-08T00:00:00Z",
        )
        for value in (
            "",
            "NOT_A_TIMESTAMP",
            "2026-08-08",
            "2026-08-08T00:00:00",
            "2026-08-08T08:00:00+08:00",
            " 2026-08-08T00:00:00+00:00",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "timestamp|UTC"):
                    validate_receipt_completed_utc(value)

    def test_malformed_receipt_timestamp_is_controlled_cli_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            output_dir = temp_path / "out"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                "C1\ta\tS1\t2\nC1\tb\tS1\t1\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "trace_rank_audit.py"),
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--budget",
                    "1",
                    "--receipt-completed-utc",
                    "NOT_A_TIMESTAMP",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, "")
            self.assertTrue(completed.stderr.startswith("ERROR: "))
            self.assertIn("ISO-8601 UTC timestamp", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)
            self.assertFalse(output_dir.exists())

    def test_empty_or_padded_identifiers_fail_before_output_creation(self):
        header = ("context_id", "candidate_id", "specification_id", "score")
        invalid_rows = (
            ("", "G1", "S1", "1"),
            ("C1", "", "S1", "1"),
            ("C1", "G1", "", "1"),
            (" C1", "G1", "S1", "1"),
            ("C1", "G1 ", "S1", "1"),
            ("C1", "G1", " S1", "1"),
        )
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            for index, row in enumerate(invalid_rows):
                with self.subTest(row=row):
                    input_path = temp_path / f"invalid_identifier_{index}.tsv"
                    output_dir = temp_path / f"out_{index}"
                    input_path.write_text(
                        "\t".join(header) + "\n" + "\t".join(row) + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        ValueError, "identifier|context_id|candidate_id|specification_id"
                    ):
                        run(input_path, output_dir, budget=1)
                    self.assertFalse(output_dir.exists())

    def test_output_schema_matches_actual_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            output_dir = temp_path / "out"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                + "".join(f"C1\tG{i}\tS1\t{10-i}\n" for i in range(5))
                + "".join(f"C1\tG{i}\tS2\t{9-i}\n" for i in range(5)),
                encoding="utf-8",
            )
            run(input_path, output_dir, budget=2)
            declared = {}
            with (ROOT / "OUTPUT_SCHEMA.tsv").open("r", encoding="utf-8") as handle:
                for row in csv.DictReader(handle, delimiter="\t"):
                    declared.setdefault(row["file"], []).append(row["column"])
            for filename in (
                "cell_contract.tsv",
                "pairwise_audit.tsv",
                "target_membership.tsv",
            ):
                with (output_dir / filename).open("r", encoding="utf-8") as handle:
                    actual = next(csv.reader(handle, delimiter="\t"))
                self.assertEqual(actual, declared[filename])
            receipt = json.loads(
                (output_dir / "audit_receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(list(receipt), declared["audit_receipt.json"])

    def test_single_specification_writes_declared_empty_pairwise_table(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            output_dir = temp_path / "out"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                "C1\ta\tONLY\t3\nC1\tb\tONLY\t2\nC1\tc\tONLY\t1\n",
                encoding="utf-8",
            )
            summary = run(input_path, output_dir, budget=2)
            declared = {}
            with (ROOT / "OUTPUT_SCHEMA.tsv").open("r", encoding="utf-8") as handle:
                for row in csv.DictReader(handle, delimiter="\t"):
                    declared.setdefault(row["file"], []).append(row["column"])
            pairwise_path = output_dir / "pairwise_audit.tsv"
            with pairwise_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle, delimiter="\t")
                header = next(reader)
                remaining = list(reader)
            self.assertEqual(header, declared["pairwise_audit.tsv"])
            self.assertEqual(remaining, [])
            self.assertEqual(summary["pairwise_comparisons"], 0)
            self.assertTrue(summary["bounds_valid"])

    def test_explicit_receipt_timestamp_is_byte_reproducible(self):
        fixed = "2026-08-08T00:00:00+00:00"
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                "C1\ta\tS1\t3\nC1\tb\tS1\t2\nC1\tc\tS1\t1\n",
                encoding="utf-8",
            )
            outputs = []
            for name in ("first", "second"):
                output_dir = temp_path / name
                run(
                    input_path,
                    output_dir,
                    budget=2,
                    receipt_completed_utc=fixed,
                )
                outputs.append((output_dir / "audit_receipt.json").read_bytes())
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(
                json.loads(outputs[0].decode("utf-8"))["completed_utc"], fixed
            )

    def test_nonempty_output_directory_is_refused_before_skip_membership_rerun(self):
        """A skip rerun cannot retain a stale target-membership file."""
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            input_path = temp_path / "scores.tsv"
            output_dir = temp_path / "out"
            input_path.write_text(
                "context_id\tcandidate_id\tspecification_id\tscore\n"
                "C1\ta\tS1\t3\nC1\tb\tS1\t2\nC1\tc\tS1\t1\n"
                "C1\ta\tS2\t3\nC1\tb\tS2\t2\nC1\tc\tS2\t1\n",
                encoding="utf-8",
            )
            run(input_path, output_dir, budget=2)
            membership = output_dir / "target_membership.tsv"
            original_membership = membership.read_bytes()
            original_receipt = (output_dir / "audit_receipt.json").read_bytes()
            with self.assertRaisesRegex(FileExistsError, "not empty"):
                run(
                    input_path,
                    output_dir,
                    budget=2,
                    emit_target_membership=False,
                )
            self.assertEqual(membership.read_bytes(), original_membership)
            self.assertEqual(
                (output_dir / "audit_receipt.json").read_bytes(), original_receipt
            )


if __name__ == "__main__":
    unittest.main()
