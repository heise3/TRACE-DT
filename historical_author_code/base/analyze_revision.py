"""Review-directed descriptive analyses. No outcome labels or biological tests."""
from pathlib import Path
import sys, json, hashlib, itertools, math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'source'
OT=SOURCE/'03_open_targets_case_study'
DATA=OT/'provenance_only_derived_matrices/ot26_06'
OUT=HERE/'analysis'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(OT/'platform_workflows/src'))
sys.path.insert(0,str(SOURCE/'02_software'))
from trace_dt.scoring_reference import harmonic_normalized, average_percentile

def write(df,name):
    df.to_csv(OUT/name,sep='\t',index=False,float_format='%.17g')

f=pd.read_parquet(DATA/'formal_operator_input.parquet')
base=pd.read_parquet(DATA/'t0_legal_unit_baseline_metrics.parquet')
membership=pd.read_csv(OT/'necessary_membership/R26_TARGET_NECESSARY_MEMBERSHIP.tsv',sep='\t')
membership=membership.rename(columns={'context_id':'candidate_id','candidate_id':'targetId'})
features=base[['candidate_id','context_name','diseaseId','targetId','pair_key','associationScore','ancestry_collapsed_artifact_count','t0_primary_hard_positive','any_missing_ancestry']].merge(membership,on=['candidate_id','targetId'],how='inner',validate='one_to_one')
assert len(features)==107497
features['cohort']=np.select([features.necessary_selection_count==32,features.deterministic_selection_count==32,features.possible_selection_count==32,features.possible_selection_count>0],['necessary_32','deterministic_32_not_necessary','possible_32_not_deterministic','other_possible_any'],default='never_possible')
assert features.cohort.value_counts()['necessary_32']==90
assert features.cohort.value_counts()['deterministic_32_not_necessary']==43
g=f.groupby('pair_key',sort=False)
counts=g.size().rename('retained_positive_rows').reset_index()
units=f.drop_duplicates(['pair_key','datasourceId','canonical_key'])
source_counts=units.groupby(['pair_key','datasourceId'],sort=False).size().rename('units')
lineage_counts=units.groupby(['pair_key','ancestry_group_id'],sort=False).size().rename('units')
source_metrics=source_counts.groupby(level=0).agg(['size','sum','max'])
source_metrics.columns=['datasource_count','canonical_units','max_source_units']
source_metrics['source_unit_hhi']=(source_counts/source_counts.groupby(level=0).transform('sum')).pow(2).groupby(level=0).sum()
source_metrics['max_source_unit_fraction']=source_metrics.max_source_units/source_metrics.canonical_units
source_metrics['datasource_all_singletons']=source_metrics.max_source_units==1
lineage_metrics=lineage_counts.groupby(level=0).agg(['size','max'])
lineage_metrics.columns=['lineage_count','max_lineage_units']
lineage_metrics['lineage_all_singletons']=lineage_metrics.max_lineage_units==1
features=features.merge(counts,on='pair_key',validate='one_to_one').merge(source_metrics,on='pair_key',validate='one_to_one').merge(lineage_metrics,on='pair_key',validate='one_to_one')
features['retained_row_singleton']=features.retained_positive_rows==1
features['only_europepmc']=features.pair_key.isin(units.loc[units.datasourceId=='europepmc','pair_key']) & (features.datasource_count==1)
b01=pd.read_parquet(OT/'secondary_results/b01_ablation/frozen_outputs/R17_B01_COMPONENT_ABLATION_SCORES.parquet')
b01=b01.loc[b01.pair_key.isin(features.pair_key)].sort_values(['candidate_id','B01_EXACT_REPLAY','targetId'],ascending=[True,False,True])
b01['baseline_id_rank']=b01.groupby('candidate_id').cumcount()+1
b01['baseline_score_percentile']=b01.groupby('candidate_id')['B01_EXACT_REPLAY'].rank(method='average',pct=True)
b01['baseline_rank_band']=pd.cut(b01.baseline_id_rank,[0,50,200,1000,np.inf],labels=['1-50','51-200','201-1000','1001+'])
features=features.merge(b01[['pair_key','B01_EXACT_REPLAY','baseline_id_rank','baseline_score_percentile','baseline_rank_band']],on='pair_key',validate='one_to_one')
write(features,'Table_S17_Evidence_Features.tsv')
summ=[]
for cohort,df in features.groupby('cohort',sort=False):
    row={'cohort':cohort,'n':len(df)}
    for col in ['retained_positive_rows','canonical_units','datasource_count','lineage_count','ancestry_collapsed_artifact_count','max_source_unit_fraction','source_unit_hhi','baseline_id_rank']:
        for key,q in [('q25',.25),('median',.5),('q75',.75)]:row[f'{col}_{key}']=df[col].quantile(q)
    for col in ['retained_row_singleton','datasource_all_singletons','lineage_all_singletons','only_europepmc']:
        row[col+'_n']=int(df[col].sum());row[col+'_fraction']=float(df[col].mean())
    summ.append(row)
write(pd.DataFrame(summ),'Table_S18_Cohort_Summary.tsv')
strata=features.groupby(['candidate_id','context_name','baseline_rank_band','cohort'],observed=True).agg(n=('pair_key','size'),row_singleton_n=('retained_row_singleton','sum'),median_retained_rows=('retained_positive_rows','median'),median_datasources=('datasource_count','median'),median_lineages=('lineage_count','median')).reset_index()
strata['row_singleton_fraction']=strata.row_singleton_n/strata.n
write(strata,'Table_S19_Context_Rank_Strata.tsv')
write(units.groupby(['datasourceId']).agg(retained_rows=('score','size'),unique_pair_keys=('pair_key','nunique'),unique_canonical_keys=('canonical_key','nunique'),unique_lineages=('ancestry_group_id','nunique')).reset_index(),'Table_S20_Source_Unit_Geometry.tsv')

cases=pd.read_csv(OT/'secondary_results/cases/R26_DETERMINISTIC_MAIN_CASES.tsv',sep='\t')
keys=set(cases.pair_key)
case_records=f[f.pair_key.isin(keys)].copy()
write(case_records,'Table_S21_Case_Record_Chain.tsv')
mapping=pd.read_parquet(DATA/'source_unit_provenance_mapping.parquet')
mapping=mapping[mapping.r04_canonical_key.isin(case_records.canonical_key)]
write(mapping,'Table_S22_Case_Provenance_Mapping.tsv')
dag=pd.read_parquet(DATA/'source_provenance_dag.parquet')
nodes=set(mapping.source_unit_node_id)
# Follow incoming ancestry only: do not expand shared release/study roots to
# unrelated downstream source units elsewhere in the complete database.
frontier=set(nodes);parts=[]
while frontier:
    picked=dag[dag.child_node_id.isin(frontier)]
    parts.append(picked)
    frontier=set(picked.parent_node_id)-nodes
    nodes.update(frontier)
edges=pd.concat(parts).drop_duplicates() if parts else dag.iloc[:0]
write(edges,'Table_S23_Case_Provenance_Edges.tsv')
del dag

matrix=pd.read_parquet(DATA/'legal_unit_operator_status_matrix.parquet')
cell_rows=[]; competitors=[]
ppp=matrix[(matrix.candidate_id=='CCTX001') & (matrix.targetId=='ENSG00000011485')].sort_values('operator_code')
write(ppp,'Table_S24_PPP5C_All32.tsv')
for code in ['01000','01001']:
    cell=matrix[(matrix.candidate_id=='CCTX001') & (matrix.operator_code==code) & (matrix.operator_status=='SCORED')].sort_values(['operator_score','targetId'],ascending=[False,True])
    target=cell[cell.targetId=='ENSG00000011485'].iloc[0]
    cut=cell.iloc[49]
    cell_rows.append({'code':code,'PPP5C_score':target.operator_score,'PPP5C_rank':target.operator_rank,'cutoff_score':cut.operator_score,'cutoff_target':cut.targetId,'targets_strictly_above_PPP5C':int((cell.operator_score>target.operator_score).sum()),'selected':bool(target.selected_top50)})
    picked=cell[(cell.operator_rank.between(45,55))|(cell.targetId=='ENSG00000011485')].copy()
    competitors.append(picked)
write(pd.DataFrame(cell_rows),'Table_S25_PPP5C_Cutoff_Comparison.tsv')
a=matrix[(matrix.candidate_id=='CCTX001')&(matrix.operator_code=='01000')&(matrix.operator_status=='SCORED')][['targetId','operator_score','operator_rank','selected_top50']]
b=matrix[(matrix.candidate_id=='CCTX001')&(matrix.operator_code=='01001')&(matrix.operator_status=='SCORED')][['targetId','operator_score','operator_rank','selected_top50']]
comp=a.merge(b,on='targetId',suffixes=('_O5_0','_O5_1'),validate='one_to_one')
comp['crossed_PPP5C_upward']=(comp.operator_score_O5_0<=float(cell_rows[0]['PPP5C_score']))&(comp.operator_score_O5_1>float(cell_rows[1]['PPP5C_score']))
comp=comp.merge(features[features.candidate_id=='CCTX001'].drop(columns=['candidate_id','context_name','diseaseId']),on='targetId',validate='one_to_one')
write(comp,'Table_S26_PPP5C_All_Competitors.tsv')
write(pd.concat(competitors),'Table_S27_PPP5C_Boundary_Neighbours.tsv')
selids=set(comp[comp.crossed_PPP5C_upward].targetId)
write(f[(f.diseaseId=='MONDO_0001187') & (f.targetId.isin(selids))],'Table_S28_PPP5C_Upward_Competitor_Records.tsv')

# Complete derived-evidence-to-score replay in one real cancer context, all 32 specs.
from trace_dt.scoring_reference import CanonicalRecord, score_context
cid='CCTX019'; did='MONDO_0002229'
fr=f[f.diseaseId==did]
records=[CanonicalRecord(row.targetId,row.datasourceId,row.canonical_key,row.ancestry_group_id or '',row.score) for row in fr.itertuples(index=False)]
targets=sorted(set(matrix.loc[matrix.candidate_id==cid,'targetId']))
excluded=set(base.loc[(base.candidate_id==cid)&base.t0_primary_hard_positive,'targetId'])
write(fr,'Table_S33_One_Context_Canonical_Input.tsv')
write(base[base.candidate_id==cid][['candidate_id','diseaseId','targetId','t0_primary_hard_positive','any_missing_ancestry']], 'Table_S34_One_Context_Eligibility_Input.tsv')
write(matrix[matrix.candidate_id==cid], 'Table_S35_One_Context_Expected_Output.tsv')
parity=[]
for i in range(32):
    code=format(i,'05b')
    actual=matrix[(matrix.candidate_id==cid)&(matrix.operator_code==code)].set_index('targetId')
    replay=score_context(target_ids=targets,records=records,primary_excluded_targets=excluded,operator_code=code)
    diffs=[];state_bad=rank_bad=selection_bad=0
    for r in replay:
        old=actual.loc[r.target_id]
        state_bad+=int(r.status!=old.operator_status)
        if r.score is not None:diffs.append(abs(r.score-old.operator_score))
        rank_bad+=int((r.rank or 0)!=(int(old.operator_rank) if pd.notna(old.operator_rank) else 0))
        selection_bad+=int(r.selected_top_k!=old.selected_top50)
    parity.append({'context_id':cid,'diseaseId':did,'code':code,'targets':len(targets),'retained_rows':len(fr),'max_score_abs_difference':max(diffs,default=0),'status_mismatches':state_bad,'rank_mismatches':rank_bad,'selection_mismatches':selection_bad,'reproduction_layer':'DERIVED_CANONICAL_RECORDS_NOT_RAW'})
write(pd.DataFrame(parity),'Table_S29_One_Context_Derived_Replay.tsv')
assert sum(r['status_mismatches']+r['selection_mismatches'] for r in parity)==0
assert max(r['max_score_abs_difference'] for r in parity)<1e-12

examples=[('O3',[.17,.63,.28,.91,.42],average_percentile([.17,.63,.28,.91,.42])),('O4',[.22,.57,.31,.81],harmonic_normalized([.22,.57,.31,.81])),('O5',[.72,.40,.81,.28],harmonic_normalized([.72,.40,.81,.28])),('tied_max_positive',[1,1,.2,.2],average_percentile([1,1,.2,.2]))]
write(pd.DataFrame([{'operation':n,'input':json.dumps(x),'result':json.dumps(y)} for n,x,y in examples]),'Table_S30_Teaching_Arithmetic.tsv')

# RBO agreement-at-B and fixed-capacity intersection are the same expectation.
# Exhaustive RBO objective comparison is deliberately limited to transparent fixtures.
from trace_rank_audit import Cell, exact_intersection_bounds
def fixture_cell(groups,B,name):
    above=[]
    for group in groups:
        if len(above)+len(group)>=B:
            return Cell(name,name,frozenset(sum(groups,[])),frozenset(above),frozenset(group),frozenset(above+sorted(group)[:B-len(above)]),B-len(above),1.0)
        above.extend(group)
    raise ValueError('capacity exceeds pool')
def permutations(groups):
    return [sum((list(x) for x in combo),[]) for combo in itertools.product(*(list(itertools.permutations(g)) for g in groups))]
fixtures=[('asymmetric', [['a'],['b','c','d'],['e','f']], [['b'],['c','d','e','f'],['a']],2),('fully_tied',[['a','b','c','d']],[['a','b','c','d']],2),('unique_boundary_fits',[['a','b'],['c','d']],[['a','b'],['c','d']],2),('untied',[['a'],['b'],['c'],['d']],[['b'],['a'],['d'],['c']],2)]
fixture_rows=[];allocation_rows=[]
for name,ga,gb,B in fixtures:
    pa=permutations(ga);pb=permutations(gb);D=len(pa[0]);p=.9
    weights=np.array([(1-p)*p**(d-1) for d in range(1,D+1)])/(1-p**D)
    values=[]
    for ra,rb in itertools.product(pa,pb):
        agreements=np.array([len(set(ra[:d])&set(rb[:d]))/d for d in range(1,D+1)])
        vals={'fixture':name,'order_a':','.join(ra),'order_b':','.join(rb),'capacity':B,'intersection_at_B':int(agreements[B-1]*B),'substitution_at_B':1-agreements[B-1],'finite_depth_RBO':float(weights@agreements)}
        values.append(vals)
    v=pd.DataFrame(values);allocation_rows.extend(values)
    ma={u:sum(u in r[:B] for r in pa)/len(pa) for u in pa[0]}
    mb={u:sum(u in r[:B] for r in pb)/len(pb) for u in pb[0]}
    ip=sum(ma[u]*mb.get(u,0) for u in ma)
    assert abs(ip-v.intersection_at_B.mean())<1e-12
    lo,hi=exact_intersection_bounds(fixture_cell(ga,B,name+'a'),fixture_cell(gb,B,name+'b'))
    assert lo==v.intersection_at_B.min() and hi==v.intersection_at_B.max()
    fixture_rows.append({'fixture':name,'capacity':B,'depth':D,'p':p,'ranking_pairs':len(v),'F_deterministic':v.iloc[0].substitution_at_B,'F_lower_exhaustive':v.substitution_at_B.min(),'F_upper_exhaustive':v.substitution_at_B.max(),'F_expected_IP':1-ip/B,'RBO_agreement_at_B_expected':ip/B,'finite_depth_RBO_min':v.finite_depth_RBO.min(),'finite_depth_RBO_max':v.finite_depth_RBO.max(),'finite_depth_RBO_mean':v.finite_depth_RBO.mean(),'necessary_a':','.join(u for u,q in ma.items() if q==1),'possible_a':','.join(u for u,q in ma.items() if q>0),'necessary_b':','.join(u for u,q in mb.items() if q==1),'possible_b':','.join(u for u,q in mb.items() if q>0)})
write(pd.DataFrame(fixture_rows),'Table_S31_Tie_Method_Fixture_Comparison.tsv')
write(pd.DataFrame(allocation_rows),'Table_S32_Exhaustive_Ranking_Allocations.tsv')
summary={'n_scored_pairs':len(features),'cohorts':features.cohort.value_counts().to_dict(),'datasource_all_singleton_fraction':float(features.datasource_all_singletons.mean()),'lineage_all_singleton_fraction':float(features.lineage_all_singletons.mean()),'PPP5C_cutoffs':cell_rows,'competitors_crossing_PPP5C_upward':int(comp.crossed_PPP5C_upward.sum()),'derived_context_parity':parity,'teaching_arithmetic':examples}
(OUT/'ANALYSIS_RECEIPT.json').write_text(json.dumps(summary,indent=2,default=str),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='derived_context_parity'},indent=2,default=str))
