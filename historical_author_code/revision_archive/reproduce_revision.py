from pathlib import Path
import sys,csv,json,hashlib,platform,time
import pandas as pd
import argparse,zipfile,io
parser=argparse.ArgumentParser(description="Reproduce the official-score sensitivity and independent cutoff baseline from the frozen archive")
parser.add_argument('--original-archive',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True)
args=parser.parse_args()
ROOT=args.output_dir.resolve()
if ROOT.exists() and any(ROOT.iterdir()):raise SystemExit('Use a new or empty output directory')
ROOT.mkdir(parents=True,exist_ok=True)
expected='df8ff4e84a6aef9f5e9f1c15524c60b04c553b345b901ab697dc177c678de141'
if hashlib.sha256(args.original_archive.read_bytes()).hexdigest()!=expected:raise SystemExit('Frozen source archive hash mismatch')
STAGE=ROOT/'source'
needed=['source/02_software/trace_rank_audit.py','source/03_open_targets_case_study/derived_input/open_targets_26_06_scores.tsv','source/03_open_targets_case_study/secondary_results/b01_ablation/frozen_outputs/R17_B01_COMPONENT_ABLATION_SCORES.parquet','source/03_open_targets_case_study/secondary_results/b01_ablation/frozen_outputs/R17_B01_COMPONENT_ABLATION_TOP50.tsv']
with zipfile.ZipFile(args.original_archive) as outer:
 for name in ['Table_S17_Evidence_Features.tsv','Table_S3_Context_Identifier_Contract_23.tsv']:
  p=ROOT/'working/frozen/tables'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(outer.read('tables/'+name))
 with zipfile.ZipFile(io.BytesIO(outer.read('source_archives/TRACE_DT_R33_FULL_CODE_AND_DERIVED_DATA.zip'))) as inner:
  for name in needed:
   p=STAGE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(inner.read(name))
sys.path.insert(0,str(STAGE/'source/02_software'))
import trace_rank_audit as engine
OUT=ROOT/'analysis'; OUT.mkdir(exist_ok=True)
SOURCE=STAGE/'source/03_open_targets_case_study'
fp=ROOT/'working/frozen/tables/Table_S17_Evidence_Features.tsv'
features=pd.read_csv(fp,sep='\t',dtype={'candidate_id':str,'targetId':str},float_precision='round_trip')
scores_path=SOURCE/'secondary_results/b01_ablation/frozen_outputs/R17_B01_COMPONENT_ABLATION_SCORES.parquet'
df=pd.read_parquet(scores_path)
print('columns',df.columns.tolist(),flush=True)
cols=['candidate_id','targetId','retained_positive_rows','datasource_count','only_europepmc','retained_row_singleton']
assert not features.duplicated(['candidate_id','targetId']).any()
merged=df.merge(features[cols],on=['candidate_id','targetId'],how='left',validate='one_to_one',indicator=True)
unmatched_all=int(merged['_merge'].ne('both').sum())
labels=pd.read_csv(ROOT/'working/frozen/tables/Table_S3_Context_Identifier_Contract_23.tsv',sep='\t').set_index('candidate_id')['open_targets_disease_name'].to_dict()
def boolean(s):return s.astype(str).str.lower().isin(['true','1'])
base=merged[boolean(merged.t0_hard_negative)&~boolean(merged.common_baseline_abstention)].copy()
assert base['_merge'].eq('both').all(), base.loc[base['_merge'].ne('both'), ['candidate_id','targetId']].head().to_dict()

def plain_membership(scoremap,budget):
    # Independent rank interval implementation: a candidate is possible if
    # its best rank <= B, necessary if its worst rank <= B.
    grouped={}
    for key,value in scoremap.items(): grouped.setdefault(value,[]).append(key)
    N=set();P=set();D=set(); preceding=0
    for value,keys in sorted(grouped.items(),reverse=True):
        best=preceding+1;worst=preceding+len(keys)
        if worst<=budget:N.update(keys)
        if best<=budget:P.update(keys)
        if preceding<budget:D.update(sorted(keys)[:budget-preceding])
        preceding=worst
    return N,P,D
checks=[];cells=[];members=[];composition=[]
orig_top=pd.read_csv(SOURCE/'secondary_results/b01_ablation/frozen_outputs/R17_B01_COMPONENT_ABLATION_TOP50.tsv',sep='\t')
orig_top=orig_top[orig_top.ablation_id.eq('B01_EXACT_REPLAY')]
for ctx,g in base.groupby('candidate_id',sort=True):
    original=None
    for threshold in [1,2,3]:
        h=g[g.retained_positive_rows.ge(threshold)]
        if len(h)<50:
            cells.append(dict(context_id=ctx,context_name=labels[ctx],min_rows=threshold,candidate_n=len(h),status='NON_EVALUABLE_BELOW_CAPACITY'))
            continue
        scoremap=dict(zip(h.targetId,h.B01_EXACT_REPLAY))
        c=engine.build_cell(ctx,'B01',scoremap,50)
        N,P,D=plain_membership(scoremap,50)
        assert (N,P,D)==(set(c.necessary),set(c.possible),set(c.deterministic))
        if threshold==1:
            original=c
            assert D==set(orig_top.loc[orig_top.candidate_id.eq(ctx),'targetId'])
        imin,imax=engine.exact_intersection_bounds(original,c)
        cells.append(dict(context_id=ctx,context_name=labels[ctx],min_rows=threshold,candidate_n=len(h),status='EVALUABLE',necessary_n=len(N),possible_n=len(P),tie_n=len(c.tied),remaining_seats=c.remaining_seats,cutoff=c.cutoff_score,set_valued=int(len(N)<50),id_overlap_original=len(D&original.deterministic),substitution_lower=1-imax/50,substitution_upper=1-imin/50))
        checks.append(dict(context_id=ctx,specification='official_min_rows_'+str(threshold),candidate_n=len(h),necessary_match=True,possible_match=True,realized_match=True))
        if threshold==1:
            for row in h.itertuples():
                t=row.targetId
                state='necessary' if t in N else 'tie_chosen' if t in D else 'possible_unchosen' if t in P else 'outside'
                members.append(dict(context_id=ctx,context_name=labels[ctx],target_id=t,score=row.B01_EXACT_REPLAY,state=state,retained_positive_rows=row.retained_positive_rows,datasource_count=row.datasource_count,only_europepmc=bool(row.only_europepmc),row_singleton=bool(row.retained_row_singleton)))
for (ctx,spec),scoremap in engine.load_scores(SOURCE/'derived_input/open_targets_26_06_scores.tsv').items():
    c=engine.build_cell(ctx,spec,scoremap,50)
    N,P,D=plain_membership(scoremap,50)
    assert (N,P,D)==(set(c.necessary),set(c.possible),set(c.deterministic))
    checks.append(dict(context_id=ctx,specification=spec,candidate_n=len(scoremap),necessary_match=True,possible_match=True,realized_match=True))
# Boundary-fits regression: all repeated cutoff candidates are necessary.
a={'a':2.,'b':1.,'c':1.,'d':0.}
assert plain_membership(a,3)[0]=={'a','b','c'}
pd.DataFrame(cells).to_csv(OUT/'Table_S46_Official_Score_Sensitivity.tsv',sep='\t',index=False)
m=pd.DataFrame(members)
m.to_csv(OUT/'Table_S47_Official_Score_Membership.tsv',sep='\t',index=False)
for state,h in m.groupby('state'):
 composition.append(dict(state=state,n=len(h),row_singleton=int(h.row_singleton.sum()),only_europepmc=int(h.only_europepmc.sum()),both=int((h.row_singleton & h.only_europepmc).sum()),median_rows=float(h.retained_positive_rows.median()),median_sources=float(h.datasource_count.median())))
pd.DataFrame(composition).to_csv(OUT/'Table_S48_Official_Evidence_Composition.tsv',sep='\t',index=False)
pd.DataFrame(checks).to_csv(OUT/'Table_S49_Cutoff_Baseline_Parity.tsv',sep='\t',index=False)
summary=[]
for th,h in pd.DataFrame(cells).groupby('min_rows'):
 ev=h[h.status.eq('EVALUABLE')]
 summary.append(dict(min_rows=int(th),contexts=len(h),evaluable=len(ev),set_valued=int(ev.set_valued.sum()),necessary_total=int(ev.necessary_n.sum()),possible_total=int(ev.possible_n.sum()),mean_id_substitution=float((1-ev.id_overlap_original/50).mean()),candidate_total=int(ev.candidate_n.sum())))
receipt=dict(source_sha256=hashlib.sha256(scores_path.read_bytes()).hexdigest(),feature_sha256=hashlib.sha256(fp.read_bytes()).hexdigest(),join_pairs=len(merged),unmatched_all_pairs=unmatched_all,unmatched_eligible_pairs=0,eligible_pairs=len(base),official_top50_parity=True,cutoff_baseline_cells=len(checks),stress_cells=736,official_cells=sum(1 for r in checks if r['specification'].startswith('official')),boundary_fits_check='PASS',summaries=summary,composition=composition,python=sys.version,platform=platform.platform(),license_scope='Existing generic engine MIT; historical database-specific workflows retain review-only terms')
(OUT/'Revision_Analysis_QA.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
