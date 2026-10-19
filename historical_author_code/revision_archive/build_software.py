from pathlib import Path
import shutil,csv,json,hashlib
R=Path(__file__).resolve().parents[1]; D=R/'deliverables'; S=R.parent/'GIGA_WORK/stage/r33'; software=D/'software/TRACE_DT';software.mkdir(parents=True,exist_ok=True)
core=S/'source/02_software'
for name in ['trace_rank_audit.py','LICENSE','OUTPUT_SCHEMA.tsv','DATA_DICTIONARY.md']:
 shutil.copy2(core/name,software/name)
shutil.copytree(core/'examples',software/'examples',dirs_exist_ok=True)
(software/'tests').mkdir(exist_ok=True)
shutil.copy2(core/'tests/test_trace_rank_audit.py',software/'tests')
(software/'pyproject.toml').write_text('''[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "trace-dt"
version = "1.2.1.post1"
description = "Auditing membership and exact substitution bounds in fixed-capacity ranked lists"
readme = "README.md"
requires-python = ">=3.10"
license = {file = "LICENSE"}
authors = [{name="TRACE-DT authors"}]
dependencies = []

[project.scripts]
trace-dt = "trace_rank_audit:main"

[tool.setuptools]
py-modules = ["trace_rank_audit"]
''')
(software/'README.md').write_text('''# TRACE-DT

A fixed score table need not determine one fixed-capacity shortlist. TRACE-DT reports necessary and possible candidates, one ascending-identifier list, and exact pairwise substitution bounds.

## Install and run (Python >=3.10)

From this directory, run:

```sh
python -m pip install .
trace-dt --version
trace-dt --input examples/asymmetric_overlap_scores.tsv --output-dir /tmp/trace-dt-example-new --budget 2
```

Choose a new output directory. The asymmetric example has exact substitution bounds [0.5, 1.0] and independent uniform-tie expectation 0.75. The command requires no third-party runtime dependency. Installation uses setuptools; an offline wheel is supplied in ../wheels/. You can install the wheel with `python -m pip install --no-deps ../wheels/trace_dt-1.2.1.post1-py3-none-any.whl`.

The local packaging version is 1.2.1.post1; `--version` reports the unchanged calculation engine 1.2.1. This local distribution has not been published to PyPI or added to the existing GitHub release. No new public release is implied.

## Input

UTF-8 TSV, one row for every context_id, candidate_id, specification_id combination, with one finite score. Extra columns are ignored. Each cell must contain at least the requested capacity. Duplicate rows, invalid scores and nonempty output directories fail closed. Exact floating-point equality defines ties by default; `--tie-tolerance` explicitly changes this contract.

## Outputs

- cell_contract.tsv: cutoff, boundary block size, remaining places, necessary and possible counts.
- target_membership.tsv: candidate scores, necessary/possible/realized membership and marginal uniform-tie probabilities.
- pairwise_audit.tsv: realized and exact minimum/maximum overlap and substitution; independent uniform-tie expectation; chance-adjusted overlap.
- audit_receipt.json: input hash, parameters, engine version and timestamp.

See OUTPUT_SCHEMA.tsv for the complete schema. The possible set is a union over admissible lists, not a larger recommended shortlist. Excluded or provenance-abstained database records are handled before the generic score input, not inferred by this engine.

## Examples and tests

```sh
python -m unittest discover -s tests -v
trace-dt --input examples/ovarian_scores.tsv --output-dir /tmp/trace-dt-ovarian-new --budget 50
```

Expected small-example outputs are supplied in examples/. Three TSV outputs are byte reproducible; receipt timestamps differ unless `--receipt-completed-utc` is fixed. The real ovarian score-table example begins at frozen scores. A separate derived-canonical-record replay is in the review package's reproduction/ folder and retains its own historical license boundary.

## Provenance and rights

trace_rank_audit.py is byte-identical to the MIT-licensed engine in the nested original artifact archived at https://doi.org/10.5281/zenodo.23353811. The MIT file here applies to generic engine code. It does not relicense examples derived from Open Targets, historical database workflows, figures, or other upstream content. Open Targets-derived example data retain the original component terms described by the frozen archive. The software license does not imply biological validation.
''')
source=S/'source/03_open_targets_case_study/derived_input/open_targets_26_06_scores.tsv'
with source.open() as f,(software/'examples/ovarian_scores.tsv').open('w') as o:
 r=csv.DictReader(f,delimiter='\t');w=csv.DictWriter(o,fieldnames=r.fieldnames,delimiter='\t',lineterminator='\n');w.writeheader();n=0
 for row in r:
  if row['context_id']=='CCTX019':w.writerow(row);n+=1
rep=D/'reproduction/ovarian';rep.mkdir(parents=True,exist_ok=True)
shutil.copy2(S/'replay_one_context.py',rep)
p=rep/'source/03_open_targets_case_study/platform_workflows/src/trace_dt';p.mkdir(parents=True,exist_ok=True)
for name in ['scoring_reference.py','__init__.py']:shutil.copy2(S/'source/03_open_targets_case_study/platform_workflows/src/trace_dt'/name,p/name)
(rep/'analysis').mkdir(exist_ok=True)
for name in ['Table_S33_One_Context_Canonical_Input.tsv','Table_S34_One_Context_Eligibility_Input.tsv','Table_S35_One_Context_Expected_Output.tsv']:
 shutil.copy2(R/'working/frozen/tables'/name,rep/'analysis'/name)
(rep/'LICENSE_SCOPE.txt').write_text('Historical scoring_reference.py and replay route are provided under the original author-review-only terms. No license change is made. The generic engine has a separate existing MIT license. This is a derived-input replay, not raw acquisition. Run python replay_one_context.py from this folder.\n')
print(json.dumps({'example_rows':n,'engine_sha256':hashlib.sha256((software/'trace_rank_audit.py').read_bytes()).hexdigest()}))
