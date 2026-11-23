"""Reviewed offline company enrichment; missing fields only, transactional audit.

No live requests or LLM calls at startup. Reapplying a package is explicit so
manual corrections (including removal of a value) survive ordinary restarts.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import unicodedata
from sqlalchemy import select
from .models import Manufacturer,Source,manufacturer_source
from .import_models import CatalogReconciliation,ArchiveReset
from .manufacturer_profiles import PROFILE_FIELDS,DATE_FIELDS,date_label

PACKAGE=Path(__file__).parent/'importing/data/manufacturers-v1.json'
DESCRIPTION_FIELDS={'description','description_author','description_source_url','description_license_url'}
LOGO_FIELDS={'logo_url','logo_author','logo_license','logo_license_url','logo_source_url'}
ALLOWED=set(PROFILE_FIELDS)|set(DATE_FIELDS)|{'country','website'}
AUDIT_ENTITY='manufacturer_profile'

def key(name):return unicodedata.normalize('NFKC',' '.join(name.split())).casefold()

def load_package(path=PACKAGE):
    from .admin import ManufacturerInput
    from .importing.normalize import Citation
    raw=Path(path).read_bytes();data=json.loads(raw);seen=set()
    if not isinstance(data.get('version'),str) or not isinstance(data.get('records'),list):raise ValueError('Pacchetto produttori non valido.')
    date.fromisoformat(data['researched_on'])
    for record in data['records']:
        if not record.get('manufacturer_names'):raise ValueError('Identità del produttore mancante.')
        for name in record['manufacturer_names']:
            normalized=key(name)
            if normalized in seen:raise ValueError('Identità duplicata nel pacchetto produttori.')
            seen.add(normalized)
        fields=record.get('fields',{})
        if not set(fields)<=ALLOWED:raise ValueError('Campo aziendale non supportato.')
        validated=ManufacturerInput(name=record['manufacturer_names'][0],**fields)
        from .admin import apply_manufacturer
        apply_manufacturer(None,Manufacturer(name=record['manufacturer_names'][0]),validated)
        sources={source['url']:source for source in record.get('sources',[])}
        for source in sources.values():Citation.model_validate(source)
        for field,value in fields.items():
            if value is None or not isinstance(value,str) or not value.strip():raise ValueError('I dati mancanti non sono fatti da importare.')
            citations=record.get('field_sources',{}).get(field,[])
            if not citations or not set(citations)<=sources.keys():raise ValueError('Ogni campo richiede una fonte documentata.')
    return data,hashlib.sha256(raw).hexdigest()

def current(item,field):
    if field in DATE_FIELDS:return date_label(getattr(item,field),getattr(item,field+'_precision'))
    return getattr(item,field)

def changes(item,record):
    fields=record['fields'];result={}
    for field,value in fields.items():
        if field in DESCRIPTION_FIELDS-{'description'} and item.description and item.description!=fields.get('description'):continue
        if field in LOGO_FIELDS-{'logo_url'} and item.logo_url and item.logo_url!=fields.get('logo_url'):continue
        if current(item,field) is None or current(item,field)=='':result[field]=value
    return result

def apply_enrichment(db,*,path=PACKAGE,explicit=False,commit=True):
    from .admin import catalog_lock,ManufacturerInput,apply_manufacturer
    catalog_lock(db)
    package,checksum=load_package(path)
    cutoff=db.scalar(select(ArchiveReset.reconciliation_cutoff).order_by(ArchiveReset.id.desc()).limit(1)) or 0
    previous=db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity==AUDIT_ENTITY,CatalogReconciliation.id>cutoff)).all()
    report={'version':package['version'],'checksum':checksum,'updated':0,'matched':0,'fields_updated':{},'unmatched':[],
        'coverage':{},'conflicts':[],'research_notes':package.get('research_notes',[])}
    if not explicit and any(a.snapshot.get('checksum')==checksum for a in previous):
        report['already_applied']=True
        if commit:db.commit()
        return report
    records={key(n):r for r in package['records'] for n in r['manufacturer_names']}
    events=[];counts=Counter()
    for item in db.scalars(select(Manufacturer).order_by(Manufacturer.id)):
        record=records.get(key(item.name))
        if record is None:report['unmatched'].append({'id':item.id,'name':item.name});continue
        report['matched']+=1
        fields=changes(item,record)
        if not fields:continue
        before={field:current(item,field) for field in fields}
        # Date validation also considers existing values before touching rows.
        from fastapi import HTTPException
        try:apply_manufacturer(db,item,ManufacturerInput(name=item.name,**fields))
        except HTTPException as exc:
            if exc.status_code!=422:raise
            # A curated existing date may disagree with a missing counterpart.
            # Preserve it and skip the new chronology instead of blocking startup.
            dates={f:fields.pop(f) for f in DATE_FIELDS if f in fields}
            if not dates:raise
            report['conflicts'].append({'name':item.name,'fields':dates,'reason':exc.detail})
            before={f:before[f] for f in fields}
            if not fields:continue
            apply_manufacturer(db,item,ManufacturerInput(name=item.name,**fields))
        by_source={};links_before=[]
        for field in fields:
            for url in record['field_sources'][field]:by_source.setdefault(url,[]).append(field)
        for citation in record['sources']:
            if citation['url'] not in by_source:continue
            source=db.scalar(select(Source).where(Source.url==citation['url'],Source.title==citation['title']).order_by(Source.id))
            if source is None:
                source=Source(title=citation['title'],url=citation['url'],author=citation.get('author'),
                    publisher=citation.get('publisher'),source_type=citation.get('source_type','company_reference'),
                    access_date=date.fromisoformat(package['researched_on']))
                db.add(source);db.flush()
            link=db.execute(select(manufacturer_source).where(manufacturer_source.c.target_id==item.id,manufacturer_source.c.source_id==source.id)).first()
            evidence=json.dumps({'adapter':package['version'],'fields':by_source[citation['url']],
                'researched_on':package['researched_on']},ensure_ascii=False)
            if link is None:
                db.execute(manufacturer_source.insert().values(target_id=item.id,source_id=source.id,verification_status='pending',
                    evidence=evidence))
            else:
                previous_link=dict(link._mapping)
                links_before.append(previous_link)
                db.execute(manufacturer_source.update().where(manufacturer_source.c.target_id==item.id,manufacturer_source.c.source_id==source.id)
                    .values(evidence='\n\n'.join(v for v in [previous_link.get('evidence'),evidence] if v),verification_status='pending'))
        events.append({'manufacturer_id':item.id,'name':item.name,'before':before,'applied':fields,
            'field_sources':{f:record['field_sources'][f] for f in fields},'source_links_before':links_before,'research':record.get('research',{})})
        counts.update(fields.keys());report['updated']+=1
    db.flush()
    report['fields_updated']=dict(counts)
    companies=list(db.scalars(select(Manufacturer)))
    report['coverage']={f:sum(bool(current(m,f)) for m in companies) for f in ['description','logo_url','country','founded','ceased','website','founders','headquarters']}
    report['coverage']['total']=len(companies)
    db.add(CatalogReconciliation(entity=AUDIT_ENTITY,source_id=0,target_id=0,
        note='Arricchimento documentato dei produttori; soli campi mancanti, fonti pending.',
        snapshot={**report,'changes':events}))
    if commit:db.commit()
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path);parser.add_argument('--package',type=Path,default=PACKAGE)
    args=parser.parse_args()
    if args.report and args.report.exists():parser.error('Il resoconto esiste già: scegliere un nuovo nome.')
    from .main import engine
    from sqlalchemy.orm import Session
    with Session(engine) as db:report=apply_enrichment(db,path=args.package,explicit=True)
    output=json.dumps(report,ensure_ascii=False,indent=2)
    if args.report:
        with args.report.open('x',encoding='utf-8') as f:f.write(output+'\n')
    print(output)
def coverage_report(db):
    package,checksum=load_package()
    records={key(n):r for r in package['records'] for n in r['manufacturer_names']}
    rows=[]
    for item in db.scalars(select(Manufacturer).order_by(Manufacturer.name)):
        record=records.get(key(item.name))
        missing=[field for field in ['description','logo_url','country','founded','headquarters','founders','website'] if not current(item,field)]
        rows.append({'id':item.id,'name':item.name,'missing_fields':missing,
            'research':record.get('research',{}) if record else {'status':'not_in_package'},
            'sources':[s['url'] for s in record.get('sources',[])] if record else []})
    return {'version':package['version'],'checksum':checksum,'manufacturers':rows,
        'coverage':{field:sum(field not in row['missing_fields'] for row in rows) for field in ['description','logo_url','country','founded','headquarters','founders','website']},
        'total':len(rows),'research_notes':package.get('research_notes',[])}


def create_router(get_db):
    from fastapi import APIRouter,Depends
    from sqlalchemy.orm import Session
    router=APIRouter(prefix='/api/admin/manufacturers/enrichment',tags=['Profili produttori'])
    @router.get('/report')
    def report(db:Session=Depends(get_db)):return coverage_report(db)
    @router.post('/apply')
    def apply(db:Session=Depends(get_db)):return apply_enrichment(db,explicit=True)
    return router


if __name__=='__main__':main()
