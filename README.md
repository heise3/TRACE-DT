# TRACE-DT

Audit necessary and possible membership and exact pairwise substitution bounds in fixed-capacity ranked score tables. The engine uses only the Python standard library. Packaging version **1.2.1.post1**, unchanged calculation engine **1.2.1**. Python 3.10 or later.

## Install and run in five minutes

```sh
python -m pip install "git+https://github.com/heise3/TRACE-DT.git@v1.2.1.post1"
trace-dt --help
```

To run the supplied examples and tests:

```sh
git clone --branch v1.2.1.post1 https://github.com/heise3/TRACE-DT.git
cd TRACE-DT
python -m pip install .
python -m unittest discover -s tests -v
trace-dt --input examples/example_scores.tsv --budget 3 --output-dir /tmp/trace-dt-example-new
```

Use a new output directory. See examples/ for both small score tables and expected cell_contract.tsv, target_membership.tsv and pairwise_audit.tsv. Inputs contain context_id, candidate_id, specification_id and finite score. Scores are not recomputed by the engine. Duplicate candidates, invalid scores and insufficient capacity are rejected. Necessary means selected in every admissible tie resolution; possible means selected in at least one. Exact pairwise bounds describe exchanges permitted by cutoff ties.

## Verification

The unchanged engine passed 21 tests and both examples reproduced their three expected TSVs byte for byte on macOS. The project contact independently reported the same 21-test pass and example parity on Linux on 19 October 2026; raw Linux logs and exact environment versions were not supplied. These are functional checks, not cross-platform performance measurements. A real ovarian-context derived-data replay is included; complete raw-to-derived acquisition is not claimed.

## Scientific applications and data

revision/ contains frozen unrestricted and restricted official-score inputs, DISEASES view inputs, new output tables and reproduction scripts. See revision/README.md. Single-cell memberships equal the elementary cutoff-block baseline; the tool integrates this calculation with cross-list exact bounds and reports. No biological or therapeutic validity is inferred from necessary membership.

The unchanged earlier full code/data archive is [Zenodo 10.5281/zenodo.23353811](https://doi.org/10.5281/zenodo.23353811), with a [single-file GitHub mirror](https://github.com/heise3/TRACE-DT/releases/tag/r40-2026-10-13). Original ZIP SHA-256: df8ff4e84a6aef9f5e9f1c15524c60b04c553b345b901ab697dc177c678de141. The earlier snapshot is distinct from the new revision outputs.

## License

Author software is MIT; see LICENSE, LICENSING.md and AUTHOR_CODE_LICENSE_SCOPE.csv. Data and third-party components retain their existing source-specific rights. The historical author-code copies remain byte identical and are covered by the explicit MIT addendum. No blanket data or image relicensing is asserted.
