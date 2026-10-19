"""Read-only spot checks against the official frozen 26.06 release. No full build claim."""
from pathlib import Path
from pip._vendor import requests
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,re
import pandas as pd
H=Path(__file__).resolve().parent;CACHE=H/'primary_sources';OUT=H/'analysis'
sources={
 'expression_atlas':('part-00000-9e9fa0b4-df98-4bd8-acc1-d3ff7635044d-c000.snappy.parquet','ENSG00000101951','MONDO_0007256'),
 'cancer_gene_census':('part-00000-5210a0cd-d578-43c6-8282-95c56ffb9331-c000.snappy.parquet','ENSG00000066468','MONDO_0005008')}
def fetch(item):
    ds,(filename,target,disease)=item
    url=f'https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.06/output/evidence_{ds}/{filename}'
    path=CACHE/f'official26_06_{ds}.parquet'
    if not path.exists():
        r=requests.get(url,timeout=120);r.raise_for_status();path.write_bytes(r.content)
    df=pd.read_parquet(path);sub=df[(df.targetId==target)&(df.diseaseId==disease)]
    assert len(sub)==1
    if ds=='expression_atlas':assert sub.iloc[0].studyId=='E-GEOD-55048' and abs(sub.iloc[0].score-.7722)<1e-15
    else:assert sub.iloc[0].studyId=='670' and sub.iloc[0].resourceScore>=.5
    print(ds,'matched exact row',sub.to_json(orient='records',default_handler=str))
    return dict(datasource=ds,url=url,file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),file_bytes=path.stat().st_size,target=target,requested_disease=disease,total_rows=len(df),target_rows=json.loads(sub.to_json(orient='records',default_handler=str)))
with ThreadPoolExecutor(max_workers=2) as ex:receipt=list(ex.map(fetch,sources.items()))
(OUT/'RAW_FIELD_SPOTCHECK.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
