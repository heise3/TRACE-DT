"""Cached-score eligibility sensitivity; descriptive, no new biological inference.

Runs current capacity engine membership on both cached regimes. Restricted
parity is a hard gate before unrestricted outputs. Missing scores are never
replaced with zero. Per-cell membership is nullable for non-evaluable states.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys, time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4]
FEATURE_NUMERIC=['retained_positive_rows','canonical_units','datasource_count','lineage_count',
    'ancestry_collapsed_artifact_count','max_source_unit_fraction','source_unit_hhi','baseline_id_rank']
FEATURE_BOOLEAN=['retained_row_singleton','datasource_all_singletons','lineage_all_singletons','only_europepmc',
    'row_singleton_and_only_europepmc']
EXCLUSIVE=['necessary_32','deterministic_32_not_necessary','possible_32_not_deterministic','other_possible_any','never_possible']
SUMMARY_COUNTS=['evaluable_specifications','deterministic_selection_count','necessary_selection_count',
    'possible_selection_count','expected_selection_count_uniform_tie']

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def require(ok,msg):
    if not bool(ok):raise AssertionError(msg)
def emit(df,p):
    df.to_csv(p,sep='\t',index=False,float_format='%.17g',lineterminator='\n')
def json_clean(v):
    if isinstance(v,dict):return {str(k):json_clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [json_clean(x) for x in v]
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
    if isinstance(v,np.bool_):return bool(v)
    return v
def put_json(v,p):p.write_text(json.dumps(json_clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def readtsv(p):return pd.read_csv(p,sep='\t',float_precision='round_trip')
def log(msg):print(msg,flush=True)
def engine_load(p):
    spec=importlib.util.spec_from_file_location('trace_rank_audit_r38',p)
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
    require(m.__version__=='1.2.1','Engine must be current V1.2.1')
    return m
def small_tests(engine):
    fits=engine.build_cell('test','fits',{'a':1.,'b':1.,'c':.5},2)
    require(fits.necessary==frozenset({'a','b'}),'Filled boundary block must be necessary')
    singleton=engine.build_cell('test','one',{'a':1.,'b':.6,'c':.2},2)
    require(singleton.necessary==singleton.possible==singleton.deterministic,'Singleton boundary is non-set-valued')
    exchangeable=engine.build_cell('test','partial',{'a':1.,'b':.5,'c':.5},2)
    require(exchangeable.necessary==frozenset({'a'}) and exchangeable.possible==frozenset({'a','b','c'}),'Partial tie block contract')
    require(exchangeable.deterministic==frozenset({'a','b'}),'Identifier-ordered realization')
    return {'engine':'1.2.1','filled_block_necessary':'PASS','singleton_boundary_necessary':'PASS',
        'partial_tie_N_ID_P':'PASS','identifier_realization':'PASS','tie_tolerance':0.0,'budget':50}

def evidence_geometry(formal):
    # These expressions preserve analyze_revision.py lines 29-44 verbatim in
    # scientific meaning. No lineage imputation or new independence definition.
    g=formal.groupby('pair_key',sort=False)
    counts=g.size().rename('retained_positive_rows').reset_index()
    units=formal.drop_duplicates(['pair_key','datasourceId','canonical_key'])
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
    # Left joins retain the declared full universe if a frozen geometry field
    # is unavailable. Its missingness is retained, never replaced with zero.
    geometry=counts.merge(source_metrics,on='pair_key',how='left',validate='one_to_one').merge(lineage_metrics,on='pair_key',how='left',validate='one_to_one')
    geometry['retained_row_singleton']=geometry.retained_positive_rows==1
    geometry['only_europepmc']=geometry.pair_key.isin(units.loc[units.datasourceId=='europepmc','pair_key']) & (geometry.datasource_count==1)
    geometry['row_singleton_and_only_europepmc']=geometry.retained_row_singleton & geometry.only_europepmc
    return geometry

def retained_digest(frame):
    frame=frame.sort_values('targetId',kind='stable')
    h=hashlib.sha256()
    h.update('\n'.join(frame.targetId).encode());h.update('\n'.join(frame.operator_status.astype(str)).encode())
    scored=frame.loc[frame.operator_status=='SCORED','operator_score'].to_numpy(dtype='<f8')
    h.update(scored.tobytes())
    return {'rows':len(frame),'scored':len(scored),'sha256':h.hexdigest()}

def audit_mode(path,mode,base,registry,engine,out,old_digests=None):
    cols=['candidate_id','targetId','operator_code','realization_id','operator_status','operator_score','operator_rank','selected_top50']
    matrix=pd.read_parquet(path,columns=cols)
    require(len(matrix)==len(base)*32,'Full matrix target × 32 size')
    for col in ['candidate_id','operator_code','realization_id','operator_status']:matrix[col]=matrix[col].astype('category')
    require(not matrix.duplicated(['candidate_id','targetId','operator_code']).any(),'No duplicate input cell candidate')
    require(matrix.loc[matrix.operator_status!='SCORED','operator_score'].isna().all(),'Non-SCORED scores must remain missing')
    pools={cid:dict(zip(g.targetId,g.index)) for cid,g in base.groupby('candidate_id',sort=False)}
    primary={cid:set(g.loc[g.t0_primary_hard_positive,'targetId']) for cid,g in base.groupby('candidate_id',sort=False)}
    counters={x:np.zeros(len(base),dtype=np.int16) for x in SUMMARY_COUNTS[:-1]}
    expected=np.zeros(len(base),dtype=float)
    cell_rows=[];digests={};cells_done=0;scored_total=0;not_scored_total=0;fullblock_cells=0
    writer=None;parquet_path=out/f'{mode.upper()}_SPEC_MEMBERSHIP.parquet'
    try:
        for (cid,code),full in matrix.groupby(['candidate_id','operator_code'],observed=True,sort=True):
            cid=str(cid);code=str(code);full=full.sort_values('targetId',kind='stable').reset_index(drop=True)
            require(len(full)==len(pools[cid]),'Full context target universe in each specification')
            meta=registry.loc[code];rid=str(meta.realization_id)
            require(full.realization_id.astype(str).eq(rid).all(),'Registry realization identifier parity')
            scored_mask=full.operator_status.eq('SCORED').to_numpy();scored=full.loc[scored_mask]
            values=scored.operator_score.to_numpy()
            require(np.isfinite(values).all() and np.all((values>0)&(values<=1)),'SCORED finite positive values in [0,1]')
            require(not scored.targetId.duplicated().any(),'Unique scored targets')
            cell=engine.build_cell(cid,rid,dict(zip(scored.targetId,values)),50,0.)
            require(len(cell.deterministic)==50 and cell.necessary<=cell.deterministic<=cell.possible,'Capacity N ⊆ ID ⊆ P')
            ordered=scored.sort_values(['operator_score','targetId'],ascending=[False,True],kind='stable')
            require(np.array_equal(ordered.operator_rank.to_numpy(),np.arange(1,len(ordered)+1)),'Cached rank parity')
            ids=scored.targetId.to_numpy();ix=np.array([pools[cid][t] for t in ids],dtype=np.int64)
            flags={'deterministic_selection_count':np.fromiter((t in cell.deterministic for t in ids),bool,len(ids)),
                'necessary_selection_count':np.fromiter((t in cell.necessary for t in ids),bool,len(ids)),
                'possible_selection_count':np.fromiter((t in cell.possible for t in ids),bool,len(ids))}
            require(np.array_equal(flags['deterministic_selection_count'],scored.selected_top50.to_numpy(bool)),'Cached selected_top50 parity')
            probs=np.fromiter((1. if t in cell.strict_above else cell.tie_probability if t in cell.tied else 0. for t in ids),float,len(ids))
            np.add.at(counters['evaluable_specifications'],ix,1)
            for name,arr in flags.items():np.add.at(counters[name],ix,arr.astype(np.int16))
            np.add.at(expected,ix,probs)
            nonprimary=full.loc[~full.targetId.isin(primary[cid])]
            digest=retained_digest(nonprimary);key=f'{cid}/{code}';digests[key]=digest
            if old_digests is not None:require(digest==old_digests[key],'Eligibility-only unchanged nonprimary scores/statuses')
            cell_rows.append({'candidate_id':cid,'realization_id':rid,'operator_code':code,'candidate_n':len(cell.scored),
                'budget':50,'cutoff_score':cell.cutoff_score,'necessary_n':len(cell.necessary),'ID_n':50,
                'tie_block_n':len(cell.tied),'remaining_tie_seats':cell.remaining_seats,'possible_n':len(cell.possible),
                'boundary_set_valued':int(len(cell.tied)>cell.remaining_seats)})
            fullblock_cells+=int(cell.remaining_seats==len(cell.tied))
            chunk=pd.DataFrame({'candidate_id':cid,'targetId':full.targetId,'realization_id':rid,'operator_code':code,
                'operator_status':full.operator_status.astype(str),'operator_score':full.operator_score,'operator_rank':full.operator_rank,
                'evaluable':scored_mask,'original_primary_hard_positive':full.targetId.isin(primary[cid])})
            for name,arr in flags.items():
                dest={'deterministic_selection_count':'ID_selected','necessary_selection_count':'necessary_selected','possible_selection_count':'possible_selected'}[name]
                nullable=pd.array([pd.NA]*len(full),dtype='boolean');nullable[scored_mask]=arr;chunk[dest]=nullable
            prob=np.full(len(full),np.nan);prob[scored_mask]=probs;chunk['uniform_tie_selection_probability']=prob
            require(chunk.loc[~chunk.evaluable,['operator_score','ID_selected','necessary_selected','possible_selected','uniform_tie_selection_probability']].isna().all().all(),'No zero imputation in non-evaluable rows')
            table=pa.Table.from_pandas(chunk,preserve_index=False)
            if writer is None:writer=pq.ParquetWriter(parquet_path,table.schema,compression='zstd')
            writer.write_table(table)
            scored_total+=len(scored);not_scored_total+=len(full)-len(scored);cells_done+=1
            if cells_done%128==0:log(f'{mode}: {cells_done}/736 capacity cells verified')
    finally:
        if writer is not None:writer.close()
    require(cells_done==736,'736 cells')
    summary=base[['candidate_id','context_name','diseaseId','targetId','pair_key']].copy()
    for name,arr in counters.items():summary[name]=arr
    summary['expected_selection_count_uniform_tie']=expected
    require((summary.necessary_selection_count<=summary.deterministic_selection_count).all(),'Target N≤ID')
    require((summary.deterministic_selection_count<=summary.possible_selection_count).all(),'Target ID≤P')
    require((summary.possible_selection_count<=summary.evaluable_specifications).all(),'Selection counts ≤ evaluable specs')
    emit(summary,out/f'{mode.upper()}_TARGET_MEMBERSHIP.tsv');summary.to_parquet(out/f'{mode.upper()}_TARGET_MEMBERSHIP.parquet',index=False,compression='zstd')
    cells=pd.DataFrame(cell_rows);emit(cells,out/f'{mode.upper()}_CELL_CONTRACT.tsv')
    receipt={'matrix_rows':len(matrix),'scored_rows':scored_total,'non_evaluable_rows':not_scored_total,'target_context_pairs':len(base),
        'evaluable_target_context_pairs':int((summary.evaluable_specifications>0).sum()),'cells':cells_done,'non_set_valued_cells':fullblock_cells,
        'native_score_missingness_preserved':True,'non_evaluable_membership_flags_are_null':True,'cached_rank_and_ID_full_parity':True,
        'nonprimary_score_status_digest_parity':True if old_digests is not None else None,
        'all32_N_ID_P':[int((summary[c]==32).sum()) for c in ['necessary_selection_count','deterministic_selection_count','possible_selection_count']]}
    del matrix
    return summary,cells,digests,receipt

def features_for(summary,base,geometry,b01,mode):
    # The S17 analysis population is pairs present in scored membership input.
    summary=summary.loc[summary.evaluable_specifications>0].copy()
    identities=['candidate_id','context_name','diseaseId','targetId','pair_key','associationScore','ancestry_collapsed_artifact_count','t0_primary_hard_positive','any_missing_ancestry']
    features=base[identities].merge(summary[['pair_key']+SUMMARY_COUNTS],on='pair_key',validate='one_to_one')
    features['cohort']=np.select([features.necessary_selection_count==32,features.deterministic_selection_count==32,features.possible_selection_count==32,features.possible_selection_count>0],EXCLUSIVE[:-1],default=EXCLUSIVE[-1])
    features=features.merge(geometry,on='pair_key',how='left',validate='one_to_one')
    require(features.retained_positive_rows.notna().all(),'Every analysis pair retains canonical evidence input')
    rank=b01.loc[b01.pair_key.isin(features.pair_key)].sort_values(['candidate_id','B01_EXACT_REPLAY','targetId'],ascending=[True,False,True]).copy()
    require(rank.B01_EXACT_REPLAY.notna().all(),'Released B01 frozen scores cover population')
    rank['baseline_id_rank']=rank.groupby('candidate_id').cumcount()+1
    rank['baseline_score_percentile']=rank.groupby('candidate_id')['B01_EXACT_REPLAY'].rank(method='average',pct=True)
    rank['baseline_rank_band']=pd.cut(rank.baseline_id_rank,[0,50,200,1000,np.inf],labels=['1-50','51-200','201-1000','1001+'])
    features=features.merge(rank[['pair_key','B01_EXACT_REPLAY','baseline_id_rank','baseline_score_percentile','baseline_rank_band']],on='pair_key',validate='one_to_one')
    features['analysis_eligibility_regime']=mode
    return features

def one_summary(features,cohort,family):
    row={'cohort':cohort,'cohort_family':family,'n':len(features)}
    for col in FEATURE_NUMERIC:
        for key,q in [('q25',.25),('median',.5),('q75',.75)]:row[f'{col}_{key}']=features[col].quantile(q) if len(features) else np.nan
    for col in FEATURE_BOOLEAN:
        row[col+'_n']=int(features[col].sum())
        row[col+'_fraction']=float(features[col].mean()) if len(features) else np.nan
        row[col+'_observed_n']=int(features[col].notna().sum())
    return row
def cohort_tables(features):
    rows=[one_summary(features.loc[features.cohort==cohort],cohort,'exclusive') for cohort in EXCLUSIVE]
    rows.append(one_summary(features,'all_evaluable_pairs','total'))
    for label,col in [('necessary_all32','necessary_selection_count'),('ID_all32','deterministic_selection_count'),('possible_all32','possible_selection_count')]:
        rows.append(one_summary(features.loc[features[col]==32],label,'nonexclusive_all32'))
    return pd.DataFrame(rows)

def compare_frame(actual,expected,key,cols):
    a=actual.set_index(key).sort_index();e=expected.set_index(key).sort_index()
    require(a.index.equals(e.index),'Reference index parity')
    diffs={}
    for col in cols:
        if pd.api.types.is_numeric_dtype(e[col]):
            av=a[col].to_numpy(float);ev=e[col].to_numpy(float)
            require(np.array_equal(np.isnan(av),np.isnan(ev)),f'Reference missingness {col}')
            require(np.allclose(av,ev,rtol=1e-12,atol=1e-12,equal_nan=True),f'Reference numeric parity {col}')
            finite=np.isfinite(av)&np.isfinite(ev);diffs[col]=float(np.abs(av[finite]-ev[finite]).max(initial=0))
        else:
            require(a[col].astype(str).equals(e[col].astype(str)),f'Reference categorical parity {col}')
    return {'rows':len(e),'columns':cols,'maximum_absolute_differences':diffs,'verdict':'PASS'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-root',type=Path,default=ROOT/'work/bd_revision/source')
    p.add_argument('--reference-analysis',type=Path,default=ROOT/'work/bd_revision/analysis')
    p.add_argument('--feature-definition',type=Path,default=ROOT/'work/bd_revision/analyze_revision.py',help='Existing feature-definition implementation, hashed but never executed')
    p.add_argument('--output',type=Path,default=Path(__file__).parent/'results')
    args=p.parse_args();out=args.output.resolve()
    require(not out.exists() or not any(out.iterdir()),'Output must be absent or empty; do not overwrite earlier run')
    out.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();ot=args.source_root/'03_open_targets_case_study';data=ot/'provenance_only_derived_matrices/ot26_06'
    engine_path=args.source_root/'02_software/trace_rank_audit.py';engine=engine_load(engine_path)
    paths={'analysis_script':Path(__file__),'engine':engine_path,'feature_definition_implementation':args.feature_definition,
        'formal_input':data/'formal_operator_input.parquet','original_baseline':data/'t0_legal_unit_baseline_metrics.parquet',
        'restricted_status':data/'legal_unit_operator_status_matrix.parquet','unrestricted_status':ot/'secondary_results/eligibility/unrestricted_counterfactual/R17_UNRESTRICTED_STATUS_MATRIX.parquet',
        'unrestricted_receipt':ot/'secondary_results/eligibility/unrestricted_counterfactual/R17_UNRESTRICTED_RECEIPT.json',
        'unrestricted_tie_aware_receipt':ot/'secondary_results/eligibility/unrestricted_tie_aware/R17_TIE_AWARE_RECEIPT.json',
        'spec_registry':ot/'contracts/specification_realizations_32.tsv',
        'current_cell_contract':ot/'committed_engine_output/cell_contract.tsv',
        'current_membership_summary':ot/'necessary_membership/R26_TARGET_NECESSARY_MEMBERSHIP.tsv',
        'B01_scores':ot/'secondary_results/b01_ablation/frozen_outputs/R17_B01_COMPONENT_ABLATION_SCORES.parquet',
        'S17_reference':args.reference_analysis/'Table_S17_Evidence_Features.tsv','S18_reference':args.reference_analysis/'Table_S18_Cohort_Summary.tsv'}
    source_rows=[{'role':role,'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':sha(path)} for role,path in paths.items()]
    emit(pd.DataFrame(source_rows),out/'SOURCE_HASHES.tsv');hashes={r['role']:r['sha256'] for r in source_rows}
    frozen=json.loads(paths['unrestricted_receipt'].read_text())
    for role,name in [('formal_input','formal_operator_input.parquet'),('original_baseline','t0_legal_unit_baseline_metrics.parquet'),('restricted_status','legal_unit_operator_status_matrix.parquet')]:
        require(hashes[role]==frozen['input_sha256'][name],'Frozen unrestricted input SHA')
    require(hashes['unrestricted_status']==frozen['output_sha256']['R17_UNRESTRICTED_STATUS_MATRIX.parquet'],'Frozen unrestricted status SHA')
    tests=small_tests(engine)
    registry=readtsv(paths['spec_registry']);registry.operator_code=registry.operator_code.astype(int).map(lambda x:str(x).zfill(5));registry=registry.set_index('operator_code')
    require(len(registry)==32 and registry.budget_per_context.eq(50).all(),'32 declared B50 specs')
    base=pd.read_parquet(paths['original_baseline']).reset_index(drop=True)
    require(len(base)==118126 and base.pair_key.is_unique,'Frozen 118126 target-context universe')
    formal=pd.read_parquet(paths['formal_input']);require(len(formal)==1723709,'Frozen canonical row count')
    require(np.isfinite(formal.score).all() and formal.score.gt(0).all(),'Frozen canonical rows have finite positive scores')
    geometry=evidence_geometry(formal)
    require(set(geometry.pair_key)==set(base.pair_key),'Canonical geometry covers full declared universe')
    emit(geometry,out/'FULL_UNIVERSE_EVIDENCE_GEOMETRY.tsv');geometry.to_parquet(out/'FULL_UNIVERSE_EVIDENCE_GEOMETRY.parquet',index=False,compression='zstd')
    feature_geometry_QA={'canonical_rows':len(formal),'pairs':len(geometry),'definitions':'analyze_revision.py lines 29-44, no unit-definition changes',
        'missing_fields':geometry.isna().sum().to_dict(),'frozen_blank_ancestry_rows':int(formal.ancestry_group_id.eq('').sum()),
        'frozen_null_ancestry_rows':int(formal.ancestry_group_id.isna().sum()),'no_lineage_imputation':True}
    del formal
    b01=pd.read_parquet(paths['B01_scores'],columns=['pair_key','candidate_id','targetId','B01_EXACT_REPLAY'])
    log('Restricted capacity reconstruction and hard parity gate')
    rs,rc,digests,rr=audit_mode(paths['restricted_status'],'restricted',base,registry,engine,out)
    require(rr['all32_N_ID_P']==[90,133,532],'Restricted headline 90/133/532')
    reference=readtsv(paths['current_membership_summary']).rename(columns={'context_id':'candidate_id','candidate_id':'targetId'})
    rsm=rs.loc[rs.evaluable_specifications>0]
    membership_parity=compare_frame(rsm,reference,['candidate_id','targetId'],SUMMARY_COUNTS)
    refcells=readtsv(paths['current_cell_contract']).rename(columns={'context_id':'candidate_id','specification_id':'realization_id'})
    cell_parity=compare_frame(rc,refcells,['candidate_id','realization_id'],['candidate_n','budget','cutoff_score','necessary_n','tie_block_n','remaining_tie_seats','possible_n','boundary_set_valued'])
    rf=features_for(rs,base,geometry,b01,'restricted');require(len(rf)==107497,'Restricted S17 analysis population')
    ref17=readtsv(paths['S17_reference']);feature_parity=compare_frame(rf,ref17,'pair_key',[c for c in ref17.columns if c!='pair_key'])
    rco=cohort_tables(rf);ref18=readtsv(paths['S18_reference'])
    s18_parity=compare_frame(rco.loc[rco.cohort_family=='exclusive'],ref18,'cohort',[c for c in ref18.columns if c!='cohort'])
    require(rf.cohort.value_counts().to_dict()=={'never_possible':97166,'other_possible_any':9799,'possible_32_not_deterministic':399,'necessary_32':90,'deterministic_32_not_necessary':43},'Restricted exclusive cohort parity')
    gate={'verdict':'PASS','headline':rr,'current_target_membership_parity':membership_parity,'current_cell_contract_parity':cell_parity,'S17_all_fields_parity':feature_parity,'S18_all_fields_parity':s18_parity,'tests':tests}
    put_json(gate,out/'RESTRICTED_PARITY_GATE.json')
    emit(rf,out/'RESTRICTED_EVIDENCE_FEATURES.tsv');rf.to_parquet(out/'RESTRICTED_EVIDENCE_FEATURES.parquet',index=False,compression='zstd')
    emit(rco,out/'RESTRICTED_COHORT_SUMMARY.tsv')
    log('Restricted PASS; only now reconstructing unrestricted capacity memberships')
    us,uc,ud,ur=audit_mode(paths['unrestricted_status'],'unrestricted',base,registry,engine,out,digests)
    uf=features_for(us,base,geometry,b01,'unrestricted');require(len(uf)==118126,'Unrestricted features cover all 118126 pairs')
    uco=cohort_tables(uf)
    emit(uf,out/'UNRESTRICTED_EVIDENCE_FEATURES.tsv');uf.to_parquet(out/'UNRESTRICTED_EVIDENCE_FEATURES.parquet',index=False,compression='zstd')
    emit(uco,out/'UNRESTRICTED_COHORT_SUMMARY.tsv')
    comparison=rco.merge(uco,on=['cohort','cohort_family'],suffixes=('_restricted','_unrestricted'),validate='one_to_one')
    for field in ['n']+[x+'_n' for x in FEATURE_BOOLEAN]+[x+'_fraction' for x in FEATURE_BOOLEAN]:
        comparison[field+'_change_unrestricted_minus_restricted']=comparison[field+'_unrestricted']-comparison[field+'_restricted']
    emit(comparison,out/'COHORT_REGIME_COMPARISON.tsv')
    # Separate original primary-high-positive status from relaxed eligibility.
    high=[]
    for mode,feat in [('restricted',rf),('unrestricted',uf)]:
        for label,mask in [('original_primary_high_positive',feat.t0_primary_hard_positive),('original_not_primary_high_positive',~feat.t0_primary_hard_positive)]:
            for name,membership_mask in [('all_evaluable_pairs',np.ones(len(feat),bool)),('necessary_all32',feat.necessary_selection_count==32),('ID_all32',feat.deterministic_selection_count==32),('possible_all32',feat.possible_selection_count==32)]:
                row=one_summary(feat.loc[mask & membership_mask],name,'original_primary_status_stratum');row.update(regime=mode,original_primary_status=label);high.append(row)
    emit(pd.DataFrame(high),out/'ORIGINAL_PRIMARY_STATUS_COHORTS.tsv')
    qa={'verdict':'PASS','completed_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-start,
        'engine_version':engine.__version__,'budget':50,'tie_tolerance':0.,'restricted_parity_gate':'RESTRICTED_PARITY_GATE.json',
        'restricted':rr,'unrestricted':ur,'feature_geometry':feature_geometry_QA,
        'full_universe_pairs':118126,'restricted_feature_pairs':len(rf),'unrestricted_feature_pairs':len(uf),
        'unrestricted_scores_reused_not_rescored':True,'nonprimary_scores_statuses_unchanged_all736cells':True,
        'original_primary_hard_positive_in_baseline':int(base.t0_primary_hard_positive.sum()),
        'no_legacy_guaranteed_fields_used':True,'no_zero_imputation':True,'no_inferential_statistics_or_biological_tests':True,
        'cohort_comparison':comparison[['cohort','cohort_family','n_restricted','n_unrestricted']+[x+'_fraction_'+r for x in ['retained_row_singleton','only_europepmc','row_singleton_and_only_europepmc'] for r in ['restricted','unrestricted']]].to_dict('records'),
        'source_hashes':hashes,
        'interpretation_boundaries':['Eligibility sensitivity on identical frozen positive canonical evidence; not a fresh raw release reconstruction.',
            'Original primary-high-positive flags are retained in feature tables and never overwritten by relaxed matrix flags.',
            'Source and lineage coding units are not independent biological studies; frozen missing ancestry is retained and flagged.',
            'B01 ID rank/percentile strata are calculated on each regime analysis population using the same frozen B01 score.',
            'Necessary is current V1.2.1 every-legal-capacity-realization semantics, including fully required boundary blocks.',
            'Only internal code/data/QA outputs: no author manuscript prose, paper figures, raw downloads or external publication.']}
    put_json(qa,out/'UNRESTRICTED_ANALYSIS_QA.json')
    brief=['# 内部验收说明（不是新论文段落）','',f'Restricted 全量 parity PASS：N/ID/P all32 = {rr["all32_N_ID_P"]}；S17 和 S18 全字段复算吻合。',
        f'Unrestricted 当前 capacity 合同重算：N/ID/P all32 = {ur["all32_N_ID_P"]}；features = {len(uf)} pairs。','',
        '取消的是原 target–context primary eligibility exclusion，正分 canonical records 未改变；非 primary-high-positive 的 scores/statuses 在全部 736 cells 完整 hash parity。',
        '具体方向由 COHORT_REGIME_COMPARISON.tsv 的真实值决定，不能继续无条件沿用 restricted 的 singleton/EuropePMC-only 百分比。',
        '原 primary 标记保留；non-evaluable 行 score、membership 和 probability 均为缺失，不是 0 或生物学阴性。',
        'lineage/source 是冻结编码几何，不是生物学独立重复。不存在下载、外发、原投稿包修改、新作者正文或新论文图。','',
        '复现：使用 Python + pandas/numpy/pyarrow，指定 --source-root、--reference-analysis、--feature-definition、--output（空或不存在目录）。脚本仅导入现行 engine 的 build_cell，不执行旧 analyze_revision.py。','',
        '## 原 cohort 结论的 eligibility 条件','',
        '| cohort | restricted n | unrestricted n | row singleton fraction R→U | EuropePMC-only fraction R→U | intersection fraction R→U |',
        '|---|---:|---:|---|---|---|']
    for row in comparison.itertuples(index=False):
        if row.cohort_family!='exclusive':continue
        brief.append(f'| {row.cohort} | {row.n_restricted} | {row.n_unrestricted} | {row.retained_row_singleton_fraction_restricted:.6f} → {row.retained_row_singleton_fraction_unrestricted:.6f} | {row.only_europepmc_fraction_restricted:.6f} → {row.only_europepmc_fraction_unrestricted:.6f} | {row.row_singleton_and_only_europepmc_fraction_restricted:.6f} → {row.row_singleton_and_only_europepmc_fraction_unrestricted:.6f} |')
    brief.extend(['','这张内部数字表用于核验结论的适用范围：改变 primary eligibility 可改变 shortlist cohort 的大小和构成。它不是新的生物学独立验证；作者需要依据实际 restricted/unrestricted 数字决定保留、收窄或删除原来的普遍性表述。'])
    (out/'INTERNAL_README_CN.md').write_text('\n'.join(brief)+'\n',encoding='utf-8')
    output_rows=[{'filename':str(x.relative_to(out)),'bytes':x.stat().st_size,'sha256':sha(x)} for x in sorted(out.iterdir()) if x.is_file()]
    emit(pd.DataFrame(output_rows),out/'OUTPUT_SHA256.tsv')
    log(json.dumps({'verdict':'PASS','restricted_all32':rr['all32_N_ID_P'],'unrestricted_all32':ur['all32_N_ID_P'],'output':str(out)},ensure_ascii=False))

if __name__=='__main__':main()
