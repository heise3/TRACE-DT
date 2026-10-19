"""MIT. Audit frozen released scores without high-confidence exclusions and replay DISEASES."""
from pathlib import Path
import argparse,sys,json,hashlib,itertools
import pandas as pd
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
R=Path(__file__).resolve().parents[1]
I=a.inputs or R/'working/audit_inputs'; O=a.output or R/'analysis';O.mkdir(exist_ok=True,parents=True)
sys.path.insert(0,str(I));import trace_rank_audit as e
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
df=pd.read_parquet(I/'official_scores.parquet');f=pd.read_parquet(I/'full_features.parquet')
assert not df.pair_key.duplicated().any() and not f.pair_key.duplicated().any()
x=df.merge(f[['pair_key','retained_positive_rows','datasource_count','only_europepmc']],on='pair_key',validate='one_to_one',how='left',indicator=True)
assert x['_merge'].eq('both').all()
assert x.associationScore.map(__import__('math').isfinite).all()
labels=pd.read_csv(I/'contexts.tsv',sep='\t').set_index('candidate_id').open_targets_disease_name.to_dict()
def base(s,B=50):
 groups={}
 for t,v in s.items():groups.setdefault(v,[]).append(t)
 N=set();P=set();D=set();n=0
 for v,ids in sorted(groups.items(),reverse=True):
  if n+len(ids)<=B:N.update(ids)
  if n<B:P.update(ids);D.update(sorted(ids)[:B-n])
  n+=len(ids)
 return N,P,D
def flag(s):return s.astype(str).str.lower().isin(['true','1'])
rows=[];members=[];pairrows=[];checks=[];cells={}
for ctx,g in x.groupby('candidate_id',sort=True):
 for pool,mask in [('unrestricted',g.index==g.index),('restricted',flag(g.t0_hard_negative)&~flag(g.common_baseline_abstention))]:
  for scorecol in ['associationScore','B01_EXACT_REPLAY']:
   for threshold in [1,2,3]:
    h=g[mask & g.retained_positive_rows.ge(threshold)]
    assert len(h)>=50
    scores=dict(zip(h.targetId,h[scorecol])); c=e.build_cell(ctx,f'{pool}_{scorecol}_{threshold}',scores,50)
    N,P,D=base(scores);assert (N,P,D)==(set(c.necessary),set(c.possible),set(c.deterministic))
    cells[(ctx,pool,scorecol,threshold)]=c
    checks.append(dict(context_id=ctx,pool=pool,score=scorecol,min_rows=threshold,baseline_match=True))
    rows.append(dict(context_id=ctx,context_name=labels[ctx],pool=pool,score=scorecol,min_rows=threshold,candidate_n=len(h),necessary_n=len(N),possible_n=len(P),selected_tie_n=50-len(N),possible_unchosen_n=len(P)-50,set_valued=int(len(N)<50),cutoff=c.cutoff_score))
    if pool=='unrestricted' and scorecol=='associationScore' and threshold==1:
     for t in h.itertuples():
      if t.targetId not in P:continue
      members.append(dict(context_id=ctx,context_name=labels[ctx],target_id=t.targetId,score=t.associationScore,state='necessary' if t.targetId in N else 'tie_chosen' if t.targetId in D else 'possible_unchosen',retained_positive_rows=t.retained_positive_rows,datasource_count=t.datasource_count,only_europepmc=t.only_europepmc))
 for pool in ['unrestricted','restricted']:
  for sc in ['associationScore','B01_EXACT_REPLAY']:
   for th in [2,3]:
    ca=cells[(ctx,pool,sc,1)];cb=cells[(ctx,pool,sc,th)];mi,ma=e.exact_intersection_bounds(ca,cb)
    pairrows.append(dict(context_id=ctx,comparison=f'{pool}_{sc}_min1_vs_min{th}',realized_substitution=1-len(ca.deterministic&cb.deterministic)/50,lower=1-ma/50,upper=1-mi/50))
 for name,ka,kb in [('unrestricted_vs_restricted_released',('unrestricted','associationScore',1),('restricted','associationScore',1)),('released_vs_reconstructed_unrestricted',('unrestricted','associationScore',1),('unrestricted','B01_EXACT_REPLAY',1)),('released_vs_reconstructed_restricted',('restricted','associationScore',1),('restricted','B01_EXACT_REPLAY',1))]:
  ca=cells[(ctx,*ka)];cb=cells[(ctx,*kb)];mi,ma=e.exact_intersection_bounds(ca,cb)
  if name.startswith('released_vs_reconstructed'):
   assert (ca.necessary,ca.possible,ca.deterministic)==(cb.necessary,cb.possible,cb.deterministic)
  pairrows.append(dict(context_id=ctx,comparison=name,realized_substitution=1-len(ca.deterministic&cb.deterministic)/50,lower=1-ma/50,upper=1-mi/50))
# Replay all DISEASES actual view comparisons, keeping absent views absent.
dcells={}
for (ctx,spec),scores in e.load_scores(I/'diseases_scores.tsv').items():
 c=e.build_cell(ctx,spec,scores,50);assert base(scores)==(set(c.necessary),set(c.possible),set(c.deterministic));dcells[(ctx,spec)]=c
 checks.append(dict(context_id=ctx,pool='DISEASES',score=spec,min_rows='',baseline_match=True))
dpairs=pd.read_csv(I/'diseases_pairs.tsv',sep='\t',float_precision='round_trip');widths=[]
for r in dpairs.itertuples():
 ca=dcells[(r.context_id,r.specification_a)];cb=dcells[(r.context_id,r.specification_b)];mi,ma=e.exact_intersection_bounds(ca,cb)
 assert mi==r.intersection_minimum and ma==r.intersection_maximum
 assert len(ca.deterministic&cb.deterministic)==r.intersection_deterministic
 widths.append((ma-mi)/50)
dpairs['bound_width']=widths
for name,data in [('Table_S50_Official_Unrestricted_Cells',rows),('Table_S51_Official_Unrestricted_Memberships',members),('Table_S52_Official_Pool_Comparisons',pairrows),('Table_S53_DISEASES_Real_View_Comparisons',dpairs),('Table_S54_Additional_Baseline_Checks',checks)]:
 pd.DataFrame(data).to_csv(O/(name+'.tsv'),sep='\t',index=False)
r=pd.DataFrame(rows);pr=pd.DataFrame(pairrows)
summary=[]
for (pool,sc,th),g in r.groupby(['pool','score','min_rows']):summary.append(dict(pool=pool,score=sc,min_rows=int(th),pairs=int(g.candidate_n.sum()),set_valued=int(g.set_valued.sum()),necessary=int(g.necessary_n.sum()),possible=int(g.possible_n.sum())))
qa=dict(input_hashes={p.name:sha(p) for p in I.iterdir() if p.is_file()},all_feature_joins='PASS',cells_checked=len(checks),official_summaries=summary,pair_summary=pr.groupby('comparison')[['realized_substitution','lower','upper']].mean().to_dict('index'),diseases=dict(cells=len(dcells),pairs=len(dpairs),nonzero_width=sum(v>0 for v in widths),max_width=max(widths),mean_width=sum(widths)/len(widths),means={k:float(dpairs[k].mean()) for k in ['substitution_deterministic','substitution_lower_bound','substitution_upper_bound']}))
(O/'Finalization_Analysis_QA.json').write_text(json.dumps(qa,indent=2));print(json.dumps({k:v for k,v in qa.items() if k!='input_hashes'},indent=2))
