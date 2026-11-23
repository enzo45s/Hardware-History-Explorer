"""Offline, explicit IBM PS/2 renaming and researched PS/1 / notebook import."""
import argparse
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
from sqlalchemy import select
from ..admin import catalog_lock
from ..models import Computer, Manufacturer, Specification, spec_source
from ..import_models import CatalogReconciliation
from ..catalog_identity import replaceable
from .ibm_ps_names import FAMILIES, commercial_name
from .identity import computer_key, maker_key
from .normalize import Record
from .vocabulary import spec_values
from .dec_research import verified_spec, verified_field
from .catalog_aliases import remember
from . import reconcile
from .engine import stage, apply_job, source

PACKAGE=Path(__file__).parent/'data/ibm-ps-research-v1.json'
ENTITY='ibm_ps_research'


def load():
    raw=PACKAGE.read_bytes();data=json.loads(raw)
    for row in data['records']:
        Record.model_validate(row)
        if row['manufacturer']!='IBM':raise ValueError('Produttore inatteso nel pacchetto IBM.')
        if not row.get('description'):raise ValueError('Descrizione IBM mancante.')
        for cfg in row['configurations']:
            for spec in cfg['specifications']:
                if not spec.get('source',{}).get('url') or not spec.get('evidence'):
                    raise ValueError('Specifica IBM senza fonte o evidenza.')
    return data,hashlib.sha256(raw).hexdigest()


def groups(db,data):
    makers=[m for m in db.scalars(select(Manufacturer)) if maker_key(m.name)=='ibm']
    if len(makers)>1:raise ValueError('Produttore IBM ambiguo: risolvere prima il doppione.')
    computers=list(db.scalars(select(Computer).where(Computer.manufacturer_id.in_([m.id for m in makers]))))
    result={row['model_name']:[] for row in data['records']}
    for c in computers:
        name=commercial_name(c.model_name)
        if name in result:result[name].append(c);continue
        for target in result:
            if computer_key('IBM',target)==computer_key(c.manufacturer.name,c.model_name):
                result[target].append(c);break
    return result


def preview(db):
    data,checksum=load();index=groups(db,data)
    known={c.id for cs in index.values() for c in cs}
    unmapped=[c.model_name for c in db.scalars(select(Computer).join(Manufacturer))
        if maker_key(c.manufacturer.name)=='ibm' and c.id not in known and re.search(r'PS/2\s+\d{4}-',c.model_name,re.I)]
    return {'version':data['version'],'checksum':checksum,
        'rename':[{'id':c.id,'before':c.model_name,'after':name} for name,cs in index.items() for c in cs if c.model_name!=name],
        'consolidate':[{'model_name':name,'ids':[c.id for c in cs]} for name,cs in index.items() if len(cs)>1],
        'new_models':[name for name,cs in index.items() if not cs and name not in FAMILIES],
        'technical_assertions':sum(len(cfg['specifications']) for row in data['records'] for cfg in row['configurations']),
        'unmapped_machine_codes':unmapped,
        'notes':data['research_notes']}


def apply(db):
    try:return _apply(db)
    except Exception:
        db.rollback();raise


def _apply(db):
    catalog_lock(db);data,checksum=load()
    if any(a.snapshot.get('checksum')==checksum for a in db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity==ENTITY))):
        from .ibm_ps_dates import apply as apply_dates
        dates=apply_dates(db,commit=False,locked=True)
        db.commit()
        return {'already_applied':True,'created':0,'updated':0,'dates':dates}
    index=groups(db,data);report={'version':data['version'],'created':0,'updated':0,'renamed':0,'merged':0,
        'corrected':0,'descriptions_updated':0,'curated_descriptions_preserved':0,'protected':[],'skipped':[]}
    changes=[];names=[];attributions=[];eligible={};equal_configs=[]
    # Correct only exact imported originals. Verified/manual values remain facts
    # to review; they are never replaced merely because a package has a value.
    for cs in index.values():
        for c in cs:
            eligible[c.id]=replaceable(c.model_name,c.manufacturer.name,c.description) and not verified_field(db,c.id,'description')
            for rule in data['corrections']:
                if c.model_name!=rule['model_name']:continue
                matches=[s for cfg in c.configurations for s in cfg.specifications if spec_values(s)==rule['before']]
                if len(matches)!=1:continue
                spec=matches[0]
                if verified_spec(db,spec):
                    report['protected'].append({'id':c.id,'property':spec.property_name});continue
                changes.append({'computer_id':c.id,'specification_id':spec.id,'before':spec_values(spec),
                    'catalog_details':spec.catalog_details,'source_links':[dict(r._mapping) for r in db.execute(select(spec_source).where(spec_source.c.target_id==spec.id))],
                    'after':rule['after'],'source':rule['source'],'evidence':rule['evidence']})
                for field,value in rule['after'].items():setattr(spec,field,value)
                spec.catalog_details={}
                citation=source(db,rule['source'])
                if citation not in spec.sources:spec.sources.append(citation)
                report['corrected']+=1
    # Code aliases are genuine scoped former identities, unlike spelling-only
    # aliases. Their original configurations remain available to old reimports.
    for name,cs in index.items():
        for c in cs:
            if name not in FAMILIES:continue  # Keep an existing notebook's commercial brand.
            if c.model_name==name:continue
            old=c.model_name
            code=next((code for code in FAMILIES.get(name,()) if code.casefold() in old.casefold()),None)
            if code:
                remember(db,c,c.id)
                if name=='PS/2 Model 80' and len(c.configurations)==1:c.configurations[0].variant_name=code
            names.append({'id':c.id,'before':old,'after':name,'description':c.description})
            c.model_name=name;report['renamed']+=1
        db.flush()
        if len(cs)>1:
            # Prefer the already curated commercial card, then a stable ID.
            target=min(cs,key=lambda c:(eligible[c.id],c.id))
            for old in cs:
                if old is target:continue
                _,_,_,plan=reconcile.prepare(db,'computer',old.id,target.id,variants=True)
                reconcile.apply(db,'computer',old.id,target.id,plan['token'],
                    'Accorpamento richiesto dei codici IBM nello stesso modello commerciale; allestimenti e originali conservati.',commit=False,variants=True)
                report['merged']+=1
            index[name]=[target]
    # The existing 30-286 and its H31 card contain identical hardware after
    # exact sourced corrections. Remove only their artificial alias scopes;
    # different/manual hardware values must keep their configurations.
    for c in index.get('PS/2 Model 30-286',[]):
        if len(c.configurations)==2:
            fingerprints=[sorted(json.dumps(spec_values(s),sort_keys=True) for s in cfg.specifications) for cfg in c.configurations]
            if fingerprints[0]==fingerprints[1]:
                for cfg,label in zip(c.configurations,('Base','Standard')):
                    equal_configs.append({'id':cfg.id,'name':cfg.variant_name,'details':cfg.catalog_details})
                    cfg.variant_name=label
                    cfg.catalog_details={'catalog_clean':True,'display_name':label,'configuration_ids':[cfg.id]}
    db.flush()
    from ..catalog_store import refresh_pending
    refresh_pending(db,commit=False,locked=True)
    db.expire_all()
    index=groups(db,data)
    records=[];targets={}
    for incoming in data['records']:
        row=deepcopy(incoming);name=row['model_name'];cs=index[name]
        if not cs and name in FAMILIES:
            report['skipped'].append(name);continue  # Do not recreate deleted legacy cards.
        if cs:
            c=cs[0];targets[name]=c.id
            row['manufacturer']=c.manufacturer.name
            row['model_name']=c.model_name
            row.pop('releases',None);row.pop('categories',None)
            if len(row['configurations'])==1:
                if len(c.configurations)>1:raise ValueError('Configurazioni IBM multiple non riconosciute: '+name)
                if c.configurations:row['configurations'][0]['variant_name']=c.configurations[0].variant_name
        records.append(row)
    job=stage(db,'manual',PACKAGE.name,'json',PACKAGE.read_bytes(),records=records,options={'upload':True,'ibm_ps_research':data['version']},commit=False)
    apply_job(db,job.id,commit=False)
    bad=[(row.normalized['model_name'],row.status,row.error) for row in job.rows if row.status not in ('imported','updated','unchanged')]
    if bad:raise ValueError('Importazione IBM annullata: '+repr(bad))
    for row in job.rows:
        c=db.get(Computer,row.computer_id);incoming=row.normalized['description']
        existing=c.id in targets.values()
        report['updated' if existing else 'created']+=1
        if c.description!=incoming and eligible.get(c.id):
            c.description=incoming
            for claim in row.claims:
                if claim.entity=='Computer' and claim.field=='description':claim.status='pending'
            report['descriptions_updated']+=1
        elif not existing:report['descriptions_updated']+=1
        elif c.description!=incoming:report['curated_descriptions_preserved']+=1
        if c.description==incoming and 'wikipedia.org/' in row.normalized['source']['url']:
            citation=row.normalized['source']
            attributions.append({'computer_id':c.id,'description_sha256':hashlib.sha256(incoming.encode()).hexdigest(),
                'title':citation['title'],'url':citation['url'],'license_url':'https://creativecommons.org/licenses/by-sa/4.0/','method':'sintesi italiana documentata'})
    report['import_job_id']=job.id
    db.add(CatalogReconciliation(entity=ENTITY,source_id=0,target_id=0,note='Ricerca e nomi commerciali IBM PS; applicazione esplicita, nessuna verifica storica automatica.',
        snapshot={**report,'checksum':checksum,'changes':changes,'names':names,'equal_configurations':equal_configs,'description_attributions':attributions}))
    db.flush()
    from .ibm_ps_dates import apply as apply_dates
    report['dates']=apply_dates(db,commit=False,locked=True)
    refresh_pending(db,commit=False,locked=True);db.commit()
    db.info.pop('retained_description_attributions',None)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    parser.add_argument('--dates-only',action='store_true',help='Aggiorna soltanto la cronologia delle schede già presenti.')
    args=parser.parse_args()
    from ..main import SessionLocal
    with SessionLocal() as db:
        if args.dates_only:
            from .ibm_ps_dates import apply as apply_dates, preview as preview_dates
            result=apply_dates(db) if args.apply else preview_dates(db)
        else:result=apply(db) if args.apply else preview(db)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
