# TRACE-DT v1.3.0

Audit necessary/possible shortlist membership, exact pairwise seat replacement,
and capacity-coupled q-of-M consensus. Python >=3.10; no third-party runtime dependencies.
The optional consensus output distinguishes proven optima from certified outer
bounds and includes explicit feasible allocations. See [CONSENSUS.md](CONSENSUS.md).

## Install and run

```sh
python -m pip install "git+https://github.com/heise3/TRACE-DT.git@v1.3.0"
trace-dt --help
```

From the supplied source archive:

```sh
python -m pip install .
trace-dt --input examples/consensus_scores.tsv --budget 2 --consensus-thresholds 1,2,3 --output-dir consensus_result
python -m unittest discover -s tests -v
```

Use a new output directory. The consensus teaching fixture has marginal counts
[0,3] and exact joint size [2,3] at q=2. An installed-wheel alternative is included
with the release. Inputs use context_id, candidate_id, specification_id and score.
Duplicate candidates, nonfinite scores and insufficient capacity are rejected.
The established three TSV output schemas and values remain compatible; consensus
adds optional output files and the receipt identifies the new engine version.

## Verification and computational materials

The v1.3.0 macOS suite has 27 passing test methods, including exhaustive small
consensus fixtures, pairwise reduction and interrupted-search enclosure. Three
legacy examples reproduce all nine established TSVs byte for byte. The current
GitHub Actions status records Linux installation and test execution for each commit.
These checks concern correctness and compatibility, not platform performance.

The v1.3.0 release asset Software_and_Data.zip contains complete derived inputs,
native-view replay scripts, all 811 consensus tasks and their witnesses, source
inventories and hashes. It contains no manuscript text. General consensus search
can remain bounded rather than exact; always retain proof status with endpoints.

The earlier installable software and revision-data archive remains at
[Zenodo 10.5281/zenodo.23472693](https://doi.org/10.5281/zenodo.23472693), matching
v1.2.1.post1. It does not contain the new consensus module. The earlier full archive
is [Zenodo 10.5281/zenodo.23353811](https://doi.org/10.5281/zenodo.23353811).
Existing DOI contents and historical release tags are preserved.

## Registry and licensing

[bio.tools:trace-dt](https://bio.tools/trace-dt); RRID:SCR_029151.
Author-owned software and analysis scripts are MIT. See LICENSE, LICENSING.md and
AUTHOR_CODE_LICENSE_SCOPE.csv. Third-party datasets and historical components
retain their source-specific rights; software licensing does not relicense data.
