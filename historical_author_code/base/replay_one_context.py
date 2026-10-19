"""Dependency-free replay of one real context from DERIVED canonical records.

This does NOT reconstruct raw eligibility predicates, keys or provenance DAGs.
Run from the extracted Additional file 3 code directory with Python >=3.10.
"""
from pathlib import Path
import csv,json,sys,math
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source/03_open_targets_case_study/platform_workflows/src'))
from trace_dt.scoring_reference import CanonicalRecord,score_context,average_percentile,harmonic_normalized
def rows(name):
    with (HERE/'analysis'/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f,delimiter='\t'))
def boolean(x):return str(x).strip().lower() in ['true','1']
inputs=rows('Table_S33_One_Context_Canonical_Input.tsv')
flags=rows('Table_S34_One_Context_Eligibility_Input.tsv')
expected=rows('Table_S35_One_Context_Expected_Output.tsv')
records=[CanonicalRecord(r['targetId'],r['datasourceId'],r['canonical_key'],r['ancestry_group_id'],float(r['score'])) for r in inputs]
targets=sorted({r['targetId'] for r in expected})
excluded={r['targetId'] for r in flags if boolean(r['t0_primary_hard_positive'])}
receipt=[]
for i in range(32):
    code=format(i,'05b');old={r['targetId']:r for r in expected if r['operator_code']==code}
    replay=score_context(target_ids=targets,records=records,primary_excluded_targets=excluded,operator_code=code)
    state=rank=selection=0;diff=0
    for r in replay:
        e=old[r.target_id]
        state+=r.status!=e['operator_status']
        rank+=(r.rank or 0)!=(int(float(e['operator_rank'])) if e['operator_rank'] else 0)
        selection+=r.selected_top_k!=boolean(e['selected_top50'])
        if r.score is not None:diff=max(diff,abs(r.score-float(e['operator_score'])))
    assert state==rank==selection==0 and diff<1e-12,(code,state,rank,selection,diff)
    receipt.append({'code':code,'max_score_difference':diff,'state_mismatches':state,'rank_mismatches':rank,'selection_mismatches':selection})
assert average_percentile([.17,.63,.28,.91,.42])==[.2,.8,.4,1,.6]
assert average_percentile([1,1,.2,.2])==[.875,.875,.375,.375]
assert math.isclose(harmonic_normalized([.22,.57,.31,.81]),.7029268292682928)
assert math.isclose(harmonic_normalized([.72,.40,.81,.28]),.7389268292682928)
result={'layer':'DERIVED_CANONICAL_RECORDS_NOT_RAW','context':'CCTX019','target_count':len(targets),'retained_rows':len(inputs),'all32':receipt,'teaching_regressions':'PASS'}
print(json.dumps(result,indent=2))
