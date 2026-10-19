from pathlib import Path
import json,hashlib,shutil,time,argparse
import numpy as np
import pandas as pd
from scipy.stats import kendalltau
ROOT=Path(__file__).resolve().parents[2];W=Path(__file__).parent
p=argparse.ArgumentParser()
p.add_argument('--source-root',type=Path,default=ROOT/'work/bd_revision/source')
p.add_argument('--membership-dir',type=Path,default=W/'agents/unrestricted/results')
p.add_argument('--repeat-dir',type=Path,default=W/'agents/unrestricted/results_run1')
p.add_argument('--output-dir',type=Path,default=W/'comparisons/results')
args=p.parse_args();OT=args.source_root/'03_open_targets_case_study'
U=args.membership_dir;OUT=args.output_dir;OUT.mkdir(parents=True,exist_ok=True)
def emit(df,n):df.to_csv(OUT/n,sep='\t',index=False,float_format='%.17g')
start=time.monotonic()
cc=pd.read_csv(U/'RESTRICTED_CELL_CONTRACT.tsv',sep='\t',dtype={'operator_code':str})
cc['O3']=cc.operator_code.str[2].astype(int)
strata=cc.groupby('O3').agg(cells=('candidate_id','size'),set_valued=('boundary_set_valued','sum'),multi_member_cutoff_blocks=('tie_block_n',lambda x:(x>1).sum())).reset_index()
strata['set_valued_fraction']=strata.set_valued/strata.cells;emit(strata,'O3_TIE_RATES.tsv')
assert strata.cells.tolist()==[368,368] and strata.set_valued.tolist()==[190,195]
pair=pd.read_csv(OT/'committed_engine_output/pairwise_audit.tsv',sep='\t',float_precision='round_trip')
matrix_path=OT/'provenance_only_derived_matrices/ot26_06/legal_unit_operator_status_matrix.parquet'
m=pd.read_parquet(matrix_path,columns=['candidate_id','targetId','realization_id','operator_code','operator_status','operator_score'])
finite=m.loc[m.operator_status=='SCORED'].copy();assert np.isfinite(finite.operator_score).all()
groups={(str(c),str(s)):g.set_index('targetId').operator_score.sort_index() for (c,s),g in finite.groupby(['candidate_id','realization_id'],observed=True)}
rows=[]
for i,r in enumerate(pair.itertuples(index=False)):
    a=groups[r.context_id,r.specification_a];b=groups[r.context_id,r.specification_b]
    shared=a.index.intersection(b.index);av=a.loc[shared];bv=b.loc[shared]
    topa=set(a.reset_index().sort_values(['operator_score','targetId'],ascending=[False,True]).head(50).targetId)
    topb=set(b.reset_index().sort_values(['operator_score','targetId'],ascending=[False,True]).head(50).targetId)
    inter=len(topa&topb);assert inter==r.intersection_deterministic
    tau=float(kendalltau(av,bv,variant='b').statistic)
    rows.append(dict(context_id=r.context_id,specification_a=r.specification_a,specification_b=r.specification_b,shared_finite_candidates=len(shared),top50_intersection=inter,top50_overlap_fraction=inter/50,deterministic_Jaccard=inter/(100-inter),Kendall_tau_b=tau,Kendall_status='FINITE' if np.isfinite(tau) else 'UNDEFINED_CONSTANT',Jaccard_minimum=r.intersection_minimum/(100-r.intersection_minimum),Jaccard_maximum=r.intersection_maximum/(100-r.intersection_maximum),substitution_lower_bound=r.substitution_lower_bound,substitution_upper_bound=r.substitution_upper_bound))
    if i%2000==0:print(i,flush=True)
res=pd.DataFrame(rows);assert len(res)==11408;emit(res,'REAL_LIST_MEASURE_COMPARISON.tsv')
feat=pd.read_parquet(U/'RESTRICTED_EVIDENCE_FEATURES.parquet')
stable=feat[feat.deterministic_selection_count>=26]
gap={'ID_selection_at_least_26':len(stable),'necessary_count_below_26':int((stable.necessary_selection_count<26).sum()),'necessary_count_below_32':int((stable.necessary_selection_count<32).sum()),'unit':'target-context pairs'}
(OUT/'FREQUENCY_26_GUARANTEE_GAP.json').write_text(json.dumps(gap,indent=2),encoding='utf-8')
# Same Jaccard, different range: pick min/max width for each integer intersection; deterministic tie-breaking of examples.
res['Jaccard_interval_width']=res.Jaccard_maximum-res.Jaccard_minimum
examples=[]
for inter,g in res.groupby('top50_intersection'):
    g=g.sort_values(['Jaccard_interval_width','context_id','specification_a','specification_b'])
    if g.iloc[-1].Jaccard_interval_width-g.iloc[0].Jaccard_interval_width>0:
        examples.extend([g.iloc[0].to_dict(),g.iloc[-1].to_dict()])
emit(pd.DataFrame(examples),'MATCHED_JACCARD_DIFFERENT_UNCERTAINTY.tsv')
# Bladder B=50 report card: one fixed cell, mutually exclusive display categories.
members=pd.read_parquet(U/'RESTRICTED_SPEC_MEMBERSHIP.parquet')
print('membership fields',list(members),flush=True)
cards=members.loc[(members.candidate_id=='CCTX001')&members.operator_code.isin(['00000','01000','01001'])].copy()
cards['display_category']=np.select([~cards.evaluable,cards.necessary_selected.fillna(False),cards.ID_selected.fillna(False),cards.possible_selected.fillna(False)],['not_evaluable','forced','realized_tie_choice','permitted_not_realized'],default='outside_capacity')
cards=cards.merge(feat.loc[feat.candidate_id=='CCTX001',['targetId','retained_positive_rows','only_europepmc','necessary_selection_count','deterministic_selection_count','possible_selection_count']],on='targetId',how='left',validate='many_to_one')
emit(cards,'BLADDER_B50_REPORT_CARD_ALL_STATES.tsv')
emit(cards.loc[cards.possible_selected.fillna(False)],'BLADDER_B50_REPORT_CARD_SHORTLIST_UNION.tsv')
emit(cards.groupby(['operator_code','display_category']).size().rename('target_count').reset_index(),'BLADDER_B50_REPORT_CARD_COUNTS.tsv')
bladder=m.loc[m.candidate_id=='CCTX001'].copy()
emit(bladder,'BLADDER_ALL32_FROZEN_SCORES.tsv')
emit(feat.loc[feat.candidate_id=='CCTX001'],'BLADDER_ALL32_EVIDENCE_FEATURES.tsv')
# Four explicitly selected use-case pairs, selected by operator changes before RBO computation.
pairs=[('00000','00001','O5 with datasource grouping and raw scale'),('01000','01001','PPP5C unchanged-score competition'),('00010','01010','O2 grouping toggle with O4=1'),('00000','01001','Combined grouping and across-group change')]
export=[]
for code in sorted({v for a,b,_ in pairs for v in (a,b)}):
    g=bladder[(bladder.operator_code==code)&(bladder.operator_status=='SCORED')].sort_values(['operator_score','targetId'],ascending=[False,True])
    cutoff=g.iloc[49].operator_score;g=g[g.operator_score>=cutoff]
    export.append(g[['operator_code','targetId','operator_score']])
emit(pd.concat(export),'RBO_BLADDER_COMPLETE_BOUNDARY_PREFIXES.tsv')
emit(pd.DataFrame(pairs,columns=['code_a','code_b','selection_reason']),'RBO_PAIR_PLAN.tsv')
src=W/'comparisons/upstream';rd=W/'comparisons/rbo';rd.mkdir(exist_ok=True)
for p in src.glob('*.R'):shutil.copy2(p,rd/p.name)
# Two independent cached runs must produce identical deterministic output bytes.
run1=args.repeat_dir
repeat={p.name:hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256((run1/p.name).read_bytes()).hexdigest() for p in U.glob('*') if p.suffix in ['.tsv','.parquet'] and p.name not in ['OUTPUT_SHA256.tsv','SOURCE_HASHES.tsv']}
assert all(repeat.values())
qa={'status':'PASS','pairwise_comparisons':len(res),'deterministic_overlap_recomputed':True,'Kendall_missing_not_zero':True,'undefined_Kendall_rows':int(res.Kendall_tau_b.isna().sum()),'O3_counts':strata.to_dict('records'),'frequency26':gap,'unrestricted_repeat_byte_parity':repeat,'elapsed_seconds':time.monotonic()-start,'RBO_status':'SEPARATE_UPSTREAM_R_SCRIPT','RRA_note':'RRA aggregates ranked lists; Kendall tau-b was chosen as the requested alternative comparator.'}
(OUT/'COMPARISON_QA.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
print(json.dumps(qa,indent=2),flush=True)
