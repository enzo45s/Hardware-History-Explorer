"""Explicit, offline import of the documented DEC research package.

Default is a read-only preview. --apply creates only the three requested
models, enriches existing DEC cards and retires exact unverified assertions.
No new admin panel, startup hook, queue or external request is introduced.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..admin import catalog_lock
from ..models import Computer, Configuration, Manufacturer, Category, spec_source
from ..import_models import CatalogReconciliation, ImportClaim
from ..catalog_identity import replaceable
from .identity import computer_key, maker_key
from .normalize import Record, Spec, Citation
from .engine import stage, apply_job, source as import_source, reference
from .vocabulary import spec_values

PACKAGE = Path(__file__).parent / 'data/dec-research-v1.json'
NEW_MODELS = {'VAX-11/780', 'VAX-11/750', 'GIGI'}
ENTITY = 'dec_research'
FIELDS = ('component_type','component_name','property_name','numeric_value','text_value','unit')


def load_package(path=PACKAGE):
    raw=Path(path).read_bytes(); data=json.loads(raw)
    if set(data['new_models'])!=NEW_MODELS:raise ValueError('Elenco dei nuovi modelli DEC non autorizzato.')
    seen=set()
    for record in data['records']:
        Record.model_validate(record)
        key=computer_key(record['manufacturer'],record['model_name'])
        if key[0]!='dec' or key in seen:raise ValueError('Identità del pacchetto DEC non valida o duplicata.')
        seen.add(key)
        if len(record['configurations'])!=1:raise ValueError('Configurazione documentale DEC non univoca.')
        keys=set()
        for spec in record['configurations'][0]['specifications']:
            if not spec.get('source',{}).get('url') or not spec.get('evidence'):raise ValueError('Specifica DEC priva di fonte o evidenza.')
            skey=tuple(spec.get(k) for k in FIELDS[:3])
            if skey in keys:raise ValueError('Specifica DEC duplicata nella stessa configurazione.')
            keys.add(skey)
    for correction in data['corrections']:
        Spec.model_validate(correction['before'])
        if correction['after'] is not None:Spec.model_validate(correction['after'])
        Citation.model_validate(correction['source'])
        if not correction.get('evidence'):raise ValueError('Correzione priva di evidenza.')
    for correction in data.get('category_corrections',[]):
        Citation.model_validate(correction['source'])
        if not correction.get('before') or not correction.get('after') or not correction.get('evidence'):
            raise ValueError('Rettifica categoria priva di evidenza o confronto puntuale.')
    return data,hashlib.sha256(raw).hexdigest()


def verified_spec(db,spec):
    return bool(db.scalar(select(spec_source.c.source_id).where(spec_source.c.target_id==spec.id,
        spec_source.c.verification_status=='verified').limit(1)) or
        db.scalar(select(ImportClaim.id).where(ImportClaim.entity=='Specification',ImportClaim.target_id==spec.id,
            ImportClaim.status=='verified').limit(1)))


def verified_field(db,computer_id,field):
    return db.scalar(select(ImportClaim.id).where(ImportClaim.entity=='Computer',
        ImportClaim.target_id==computer_id,ImportClaim.field==field,ImportClaim.status=='verified').limit(1)) is not None


def prepare(db,path=PACKAGE):
    data,checksum=load_package(path)
    makers=list(db.scalars(select(Manufacturer)))
    if sum(maker_key(m.name)=='dec' for m in makers)>1:raise ValueError('Produttore Digital/DEC ambiguo: risolvere gli alias prima dell’importazione.')
    index={}
    for c in db.scalars(select(Computer).options(selectinload(Computer.manufacturer),
            selectinload(Computer.configurations).selectinload(Configuration.specifications))):
        index.setdefault(computer_key(c.manufacturer.name,c.model_name),[]).append(c)
    selected=[]; skipped=[]; corrections=[]
    for row in data['records']:
        matches=index.get(computer_key(row['manufacturer'],row['model_name']),[])
        if len(matches)>1:
            skipped.append({'model_name':row['model_name'],'reason':'Abbinamento ambiguo.'});continue
        current=matches[0] if matches else None
        if current is None and row['model_name'] not in NEW_MODELS:
            skipped.append({'model_name':row['model_name'],'reason':'Scheda esistente assente: non viene ricreata.'});continue
        if current is not None and len(current.configurations)>1:
            skipped.append({'model_name':row['model_name'],'reason':'Configurazioni sostanziali multiple: revisione manuale richiesta.'});continue
        selected.append((row,current))
        if current is None:continue
        for rule in data['corrections']:
            if rule['model_name']!=row['model_name']:continue
            specs=[s for cfg in current.configurations for s in cfg.specifications if spec_values(s)==rule['before']]
            if len(specs)==1:
                spec=specs[0]
                corrections.append({'rule':rule,'spec':spec,'computer':current,'protected':verified_spec(db,spec)})
    return data,checksum,selected,skipped,corrections


def preview(db,path=PACKAGE):
    data,checksum,selected,skipped,corrections=prepare(db,path)
    return {'version':data['version'],'checksum':checksum,'existing_models':sum(c is not None for _,c in selected),
        'new_models':[r['model_name'] for r,c in selected if c is None],
        'technical_assertions':sum(len(r['configurations'][0]['specifications']) for r,_ in selected),
        'applicable_corrections':sum(not c['protected'] for c in corrections),
        'protected_corrections':sum(c['protected'] for c in corrections),'skipped':skipped,'notes':data['notes']}


def apply(db,path=PACKAGE):
    try:
        return _apply(db,path)
    except Exception:
        db.rollback()
        raise


def _apply(db,path):
    catalog_lock(db)
    data,checksum,selected,skipped,corrections=prepare(db,path)
    previous=db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity==ENTITY)).all()
    if any(a.snapshot.get('checksum')==checksum for a in previous):
        db.rollback();return {'version':data['version'],'already_applied':True,'created':0,'updated':0}
    report={'version':data['version'],'checksum':checksum,'created':0,'updated':0,'corrected_assertions':0,
        'retired_assertions':0,'descriptions_updated':0,'curated_descriptions_preserved':0,'skipped':skipped,
        'protected':[],'notes':data['notes']}
    audit=[];retired=[];attributions=[];category_changes=[]
    for record,c in selected:
        if c is None:continue
        for rule in data.get('category_corrections',[]):
            if record['model_name']!=rule['model_name'] or sorted(cat.name for cat in c.categories)!=sorted(rule['before']):continue
            if verified_field(db,c.id,'category'):
                report['protected'].append({'model_name':c.model_name,'property':'Categoria','reason':'Categoria già verificata: conservata.'});continue
            old_ids=[cat.id for cat in c.categories]
            c.categories=[reference(db,Category,name) for name in rule['after']]
            citation=import_source(db,rule['source'],accessed=False)
            if citation not in c.sources:c.sources.append(citation)
            category_changes.append({'computer_id':c.id,'before_ids':old_ids,**rule,'source_id':citation.id})
    for item in corrections:
        rule,spec,c=item['rule'],item['spec'],item['computer']
        if item['protected']:
            report['protected'].append({'model_name':rule['model_name'],'property':spec.property_name,'reason':'Dato già verificato: conservato.'});continue
        links=[dict(row._mapping) for row in db.execute(select(spec_source).where(spec_source.c.target_id==spec.id))]
        urls=[s.url for s in spec.sources if s.url]
        audit.append({'computer_id':c.id,'specification_id':spec.id,'before':spec_values(spec),
            'before_details':spec.catalog_details,'before_sources':links,'after':rule['after'],
            'source':rule['source'],'evidence':rule['evidence']})
        citation=import_source(db,rule['source'],accessed=False)
        if citation not in c.sources:c.sources.append(citation)
        if rule['after'] is None:
            retired.append({'computer_id':c.id,'before':rule['before'],'source_urls':urls})
            spec.configuration.specifications.remove(spec)
            report['retired_assertions']+=1
        else:
            for field in FIELDS:setattr(spec,field,rule['after'].get(field))
            spec.catalog_details={}
            if citation not in spec.sources:spec.sources.append(citation)
            report['corrected_assertions']+=1
    db.flush()
    records=[]; old_text={};new_keys=set()
    for row,c in selected:
        record=deepcopy(row)
        if c is not None:
            record.update(manufacturer=c.manufacturer.name,model_name=c.model_name)
            old_text[c.id]=c.description
            if c.configurations:record['configurations'][0]['variant_name']=c.configurations[0].variant_name
        else:new_keys.add(computer_key(record['manufacturer'],record['model_name']))
        records.append(record)
    if not records:
        db.rollback();return report
    raw=Path(path).read_bytes()
    job=stage(db,'manual','dec-research-v1.json','json',raw,records=records,
        options={'upload':True,'dec_research':data['version']},commit=False)
    apply_job(db,job.id,commit=False)
    failed=[{'model_name':r.normalized.get('model_name'),'status':r.status,'error':r.error}
            for r in job.rows if r.status in ('failed','ambiguous','invalid','ready')]
    if failed:
        raise ValueError('Pacchetto DEC non applicato integralmente; nessuna modifica salvata: '+json.dumps(failed,ensure_ascii=False))
    for row in job.rows:
        c=db.get(Computer,row.computer_id);key=computer_key(c.manufacturer.name,c.model_name)
        if key in new_keys:report['created']+=1
        else:report['updated']+=1
        before=old_text.get(c.id)
        incoming=row.normalized['description']
        for change in category_changes:
            if change['computer_id']==c.id:
                for cat in c.categories:
                    db.add(ImportClaim(row_id=row.id,computer_id=c.id,source_id=change['source_id'],entity='Computer',
                        target_id=c.id,field='category',value={'value':cat.id},previous={'value':change['before_ids']},
                        status='pending',estimated=False,evidence=change['evidence']))
        if c.id in old_text and before!=incoming:
            if replaceable(c.model_name,c.manufacturer.name,before) and not verified_field(db,c.id,'description'):
                c.description=incoming
                for claim in row.claims:
                    if claim.entity=='Computer' and claim.field=='description':claim.status='pending'
                report['descriptions_updated']+=1
            else:report['curated_descriptions_preserved']+=1
        elif key in new_keys:report['descriptions_updated']+=1
        if c.description==incoming and 'wikipedia.org/' in row.normalized['source']['url']:
            citation=row.normalized['source']
            attributions.append({'computer_id':c.id,'title':citation['title'],'url':citation['url'],
                'license_url':'https://creativecommons.org/licenses/by-sa/4.0/','method':'sintesi italiana documentata',
                'description_sha256':hashlib.sha256(incoming.encode()).hexdigest()})
    report['import_job_id']=job.id
    report['categories_corrected']=len(category_changes)
    db.flush()
    report['claims']=dict(Counter(claim.status for row in job.rows for claim in row.claims))
    db.add(CatalogReconciliation(entity=ENTITY,source_id=0,target_id=0,
        note='Ricerca DEC documentata; nuovi modelli richiesti, arricchimenti e rettifiche puntuali non verificate automaticamente.',
        snapshot={**report,'changes':audit,'category_changes':category_changes,'retired_assertions':retired,'description_attributions':attributions}))
    db.flush()
    from ..catalog_store import refresh_pending
    refresh_pending(db,commit=False,locked=True)
    db.commit()
    db.info.pop('retained_description_attributions',None)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Applica la ricerca; senza opzione mostra solo l’anteprima.')
    args=parser.parse_args()
    from ..main import engine
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        result=apply(db) if args.apply else preview(db)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
