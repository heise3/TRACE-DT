# Reproduce revision analyses

Install requirements.txt into a separate environment. From the repository root:

```
python revision/audit_unrestricted.py --inputs revision/inputs --output /tmp/trace-dt-final-replay
python revision/reproduce_revision.py --original-archive /path/to/original.zip --output-dir /tmp/trace-dt-earlier-replay
```

Use new output directories. The first script repeats Tables S50–S54 from included frozen inputs, checks 276 official-score cells plus 88 DISEASES cells, and reproduces 50 pairwise intersections. The second repeats Tables S46–S49 from the byte-unchanged 525,431,129-byte original archive (Zenodo 10.5281/zenodo.23353811 or the r40-2026-10-13 GitHub release). Expected TSVs are in outputs/. Compare data files; platform metadata in JSON receipts may differ. Both analyses are descriptive, with exact-node pools and retained record counts, not biological validation. SOURCE_LICENSES.tsv describes historical components; LICENSING.md grants MIT only to author code.

render_new_figures.py is the local figure-source record and uses the author workspace layout; the scientific audit above is portable.
