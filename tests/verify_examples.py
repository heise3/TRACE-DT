"""Verify installed CLI outputs against both frozen examples (MIT)."""
from pathlib import Path
import tempfile,subprocess
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
 for name,budget,expected in [('example_scores.tsv',3,'example_output'),('asymmetric_overlap_scores.tsv',2,'asymmetric_overlap_output')]:
  out=Path(tmp)/expected
  subprocess.run(['trace-dt','--input',str(root/'examples'/name),'--budget',str(budget),'--output-dir',str(out)],check=True,capture_output=True)
  for f in ['cell_contract.tsv','pairwise_audit.tsv','target_membership.tsv']:
   assert (out/f).read_bytes()==(root/'examples'/expected/f).read_bytes(),(name,f)
print('PASS: both examples reproduce all three expected TSVs byte for byte')
