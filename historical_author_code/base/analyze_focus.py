"""R32 focused, deterministic examples from the unchanged frozen derived inputs."""
from pathlib import Path
import sys,json,itertools,math
import pandas as pd
HERE=Path(__file__).resolve().parent
OLD=HERE if (HERE/'source').is_dir() else HERE.parent/'bd_revision'; A=OLD/'analysis'; SOURCE=OLD/'source'
OUT=HERE/'analysis'; OUT.mkdir(exist_ok=True)
OT=SOURCE/'03_open_targets_case_study'
sys.path.insert(0,str(OT/'platform_workflows/src'))
from trace_dt.scoring_reference import harmonic_normalized,CanonicalRecord,score_context
def write(df,name):df.to_csv(OUT/name,sep='\t',index=False,float_format='%.17g')
c=pd.read_csv(A/'Table_S26_PPP5C_All_Competitors.tsv',sep='\t')
eligible=c[c.crossed_PPP5C_upward & (c.retained_positive_rows>=2) & (c.datasource_count==1) & (c.lineage_count>=2) & c.lineage_all_singletons].sort_values(['retained_positive_rows','canonical_units','targetId'])
raw=pd.read_csv(A/'Table_S28_PPP5C_Upward_Competitor_Records.tsv',sep='\t')
chosen=None
for candidate in eligible.itertuples(index=False):
    rows=raw[raw.targetId==candidate.targetId]
    if rows.score.nunique()>1 and rows.ancestry_group_id.notna().all():chosen=candidate;break
assert chosen is not None
rows=raw[raw.targetId==chosen.targetId].sort_values(['score','canonical_key'],ascending=[False,True])
rows=rows.copy();rows['case_role']='deterministically_selected_upward_competitor'
ppp=pd.read_csv(A/'Table_S21_Case_Record_Chain.tsv',sep='\t')
ppp=ppp[ppp.targetId=='ENSG00000011485'].copy();ppp['case_role']='unchanged_singleton_PPP5C'
write(pd.concat([rows,ppp]),'Table_S36_Grouping_Example_Records.tsv')
matrix_path=OT/'provenance_only_derived_matrices/ot26_06/legal_unit_operator_status_matrix.parquet'
matrix=pd.read_parquet(matrix_path,filters=[('candidate_id','==','CCTX001'),('targetId','in',[chosen.targetId,'ENSG00000011485'])]) if matrix_path.is_file() else pd.read_csv(A/'Grouping_Example_Frozen_Expected_All32.tsv',sep='\t',dtype={'operator_code':str})
details=[]
for target,rr in pd.concat([rows,ppp]).groupby('targetId'):
    records=[CanonicalRecord(r.targetId,r.datasourceId,r.canonical_key,r.ancestry_group_id,r.score) for r in rr.itertuples()]
    for o2,o4,o5 in itertools.product([0,1],repeat=3):
        code=f'0{o2}0{o4}{o5}'
        replay=score_context(target_ids=[target],records=records,primary_excluded_targets=[],operator_code=code)[0]
        frozen=matrix[(matrix.targetId==target)&(matrix.operator_code==code)].iloc[0]
        assert math.isclose(replay.score,frozen.operator_score,rel_tol=0,abs_tol=1e-15)
        groups=rr.groupby('ancestry_group_id' if o2 else 'datasourceId').score.apply(list)
        group_scores=[harmonic_normalized(v) if o4 else max(v) for v in groups]
        details.append(dict(targetId=target,operator_code=code,grouping='lineage' if o2 else 'datasource',within='finite_harmonic' if o4 else 'maximum',across='finite_harmonic' if o5 else 'arithmetic',group_count=len(groups),sorted_group_scores=json.dumps(sorted(group_scores,reverse=True)),recomputed_score=replay.score,frozen_score=frozen.operator_score,score_abs_difference=abs(replay.score-frozen.operator_score),frozen_rank=frozen.operator_rank,frozen_selected=bool(frozen.selected_top50)))
write(pd.DataFrame(details),'Table_S37_Grouping_Example_Operators.tsv')
s31=pd.read_csv(A/'Table_S31_Tie_Method_Fixture_Comparison.tsv',sep='\t')
s32=pd.read_csv(A/'Table_S32_Exhaustive_Ranking_Allocations.tsv',sep='\t')
out=[]
for fixture in ['unique_boundary_fits','untied']:
    sub=s32[s32.fixture==fixture].sort_values(['finite_depth_RBO','order_a','order_b'])
    for label,row in [('min_Q',sub.iloc[0]),('max_Q',sub.iloc[-1])]:
        item=row.to_dict();item['example']=label
        item['tie_blocks_a']='{a,b}|{c,d}' if fixture=='unique_boundary_fits' else '{a}|{b}|{c}|{d}'
        item['tie_blocks_b']='{a,b}|{c,d}' if fixture=='unique_boundary_fits' else '{b}|{a}|{d}|{c}'
        item['necessary_a']=item['necessary_b']='a,b'
        item['possible_a']=item['possible_b']='a,b'
        out.append(item)
write(pd.DataFrame(out),'Table_S38_Concrete_Rank_Objective_Comparison.tsv')
receipt={'selection_rule':'Among the 495 upward-crossing targets, require >=2 retained rows, exactly one datasource, >=2 resolved singleton lineage groups and unequal raw scores; order by retained rows, canonical units, then ascending Ensembl ID. Select the first qualifying pair. O1=0 and O3=0 throughout.','eligible_before_unequal_score_check':len(eligible),'selected_target':chosen.targetId,'scores':rows.score.tolist(),'retained_rows':len(rows),'datasource':rows.datasourceId.unique().tolist(),'lineage_groups':rows.ancestry_group_id.unique().tolist(),'verified_operator_rows':len(details),'max_score_error':max(d['score_abs_difference'] for d in details)}
(OUT/'FOCUSED_ANALYSIS_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2));print(s31.to_string(index=False));print(pd.DataFrame(out).to_string(index=False))
