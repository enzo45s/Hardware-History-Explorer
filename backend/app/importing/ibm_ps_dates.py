"""Sourced chronology supplement; never creates computers or new price offers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from sqlalchemy import select
from ..admin import catalog_lock, historical_date
from ..models import Computer, Manufacturer, Release, release_source, Market
from ..import_models import CatalogReconciliation, ImportClaim
from .identity import maker_key, computer_key
from .ibm_ps_names import commercial_name
from .normalize import Citation, Record
from .engine import stage, source, reference, attribute

PACKAGE=Path(__file__).parent/'data/ibm-ps-dates-v1.json'


def load(path=PACKAGE):
    raw=Path(path).read_bytes();data=json.loads(raw);seen=set()
    for row in data['records']:
        if row['model_name'] in seen:raise ValueError('Modello ripetuto nel supplemento cronologico.')
        seen.add(row['model_name']);Citation.model_validate(row['source'])
        historical_date(row['release_date'])
        if row.get('announcement_date'):historical_date(row['announcement_date'])
        if not row.get('evidence') or not row['source'].get('url'):raise ValueError('Data IBM senza fonte o evidenza.')
        for offer in row.get('offers',[]):
            historical_date(offer['release_date'])
            if not offer.get('evidence'):raise ValueError('Allestimento IBM senza evidenza cronologica.')
    return data,hashlib.sha256(raw).hexdigest()


def date_text(target,field):
    value=getattr(target,field);precision=getattr(target,field.replace('_date','_precision'))
    return value.isoformat()[:{'year':4,'month':7}.get(precision,10)] if value else None


def verified(db,entity,target_id,field):
    return db.scalar(select(ImportClaim.id).where(ImportClaim.entity==entity,
        ImportClaim.target_id==target_id,ImportClaim.field==field,ImportClaim.status=='verified').limit(1)) is not None


def plan(db,path=PACKAGE):
    data,checksum=load(path)
    makers=[m.id for m in db.scalars(select(Manufacturer)) if maker_key(m.name)=='ibm']
    if len(makers)>1:raise ValueError('Produttore IBM ambiguo: cronologia non modificata.')
    computers=list(db.scalars(select(Computer).where(Computer.manufacturer_id.in_(makers))))
    selected=[];skipped=[];preserved=[]
    for row in data['records']:
        matches=[c for c in computers if computer_key('IBM',row['model_name'])==computer_key('IBM',commercial_name(c.model_name) or c.model_name)]
        if len(matches)!=1:
            skipped.append({'model_name':row['model_name'],'reason':'Scheda assente o ambigua.'});continue
        c=matches[0];actions=[]
        if row.get('announcement_date') and c.announcement_date is None and not verified(db,'Computer',c.id,'announcement_date'):
            actions.append({'field':'announcement_date','value':row['announcement_date']})
        releases=list(c.releases)
        if not releases:actions.append({'field':'release_date','target':None,'value':row['release_date'],'evidence':row['evidence']})
        for release in releases:
            details=release.catalog_details or {};desired=row['release_date'];evidence=row['evidence']
            # Scope is explicit in the retained variant, never inferred from an amount.
            scope=details.get('model_variant') or details.get('display_model_variant') or ''
            matched=False
            for offer in row.get('offers',[]):
                if offer['machine_code'].casefold() in scope.casefold():
                    desired=offer['release_date'];evidence=offer['evidence'];matched=True;break
            if row.get('offers') and not matched:
                desired=desired[:4]  # Family year only when the actual allestimento is unknown.
            old=date_text(release,'release_date')
            protected=details.get('date_manual') or verified(db,'Release',release.id,'release_date')
            if old and db.scalar(select(release_source.c.source_id).where(release_source.c.target_id==release.id,
                    release_source.c.verification_status=='verified').limit(1)) is not None:protected=True
            if protected:
                preserved.append({'model_name':row['model_name'],'release_id':release.id,'date':old,'reason':'Data curata o verificata.'});continue
            if old and not (old==desired or desired.startswith(old+'-')):
                preserved.append({'model_name':row['model_name'],'release_id':release.id,'date':old,'reason':'Data esistente diversa o più precisa: conservata.'});continue
            if old==desired and details.get('date_evidence',{}).get('kind')!='reference':continue
            if release.discontinuation_date:
                day,precision=historical_date(desired)
                if day>release.discontinuation_date:
                    preserved.append({'model_name':row['model_name'],'release_id':release.id,'date':old,'reason':'Data successiva alla fine commercializzazione: revisione richiesta.'});continue
            actions.append({'field':'release_date','target':release,'value':desired,'evidence':evidence})
        if actions:selected.append({'row':row,'computer':c,'actions':actions})
    return data,checksum,selected,skipped,preserved


def preview(db,path=PACKAGE):
    data,checksum,selected,skipped,preserved=plan(db,path)
    return {'version':data['version'],'models_to_update':[i['row']['model_name'] for i in selected],
        'dates_to_update':sum(len(i['actions']) for i in selected),'skipped':skipped,'preserved':preserved,'notes':data['notes']}


def apply(db,*,commit=True,locked=False,path=PACKAGE):
    try:
        if not locked:catalog_lock(db)
        data,checksum,selected,skipped,preserved=plan(db,path)
        report={'version':data['version'],'models_updated':0,'announcement_dates':0,'release_dates':0,
            'release_rows_created':0,'skipped':skipped,'preserved':preserved}
        if not selected:
            report['already_applied']=True
            if commit:db.rollback()
            return report
        records=[]
        for item in selected:
            c=item['computer'];row=item['row']
            record={'manufacturer':c.manufacturer.name,'model_name':c.model_name,'source':row['source'],'evidence':row['evidence']}
            if row.get('announcement_date'):record['announcement_date']=row['announcement_date']
            Record.model_validate(record);records.append(record)
        job=stage(db,'manual','ibm-ps-dates-v1.json','json',Path(path).read_bytes(),records=records,
            options={'upload':True,'existing_only':True,'ibm_ps_dates':data['version']},commit=False)
        audit=[]
        for imported,item in zip(job.rows,selected):
            c=item['computer'];row=item['row'];imported.computer_id=c.id
            citation=source(db,row['source'])
            if citation not in c.sources:c.sources.append(citation)
            for action in item['actions']:
                if action['field']=='announcement_date':
                    attribute(db,imported,c,'announcement_date',action['value'],row['source'],row.get('announcement_evidence') or row['evidence'])
                    audit.append({'computer_id':c.id,'field':'announcement_date','before':None,'after':action['value'],
                        'source':row['source'],'evidence':row.get('announcement_evidence') or row['evidence']})
                    report['announcement_dates']+=1;continue
                target=action['target'];before=None
                if target is None:
                    target=Release(market=reference(db,Market,'Mercato non documentato'))
                    c.releases.append(target);db.flush();report['release_rows_created']+=1
                else:
                    before={'release_date':date_text(target,'release_date'),'catalog_details':deepcopy(target.catalog_details),
                        'source_links':[dict(v._mapping) for v in db.execute(select(release_source).where(release_source.c.target_id==target.id))]}
                previous={'value':target.release_date.isoformat() if target.release_date else None,'precision':target.release_precision}
                target.release_date,target.release_precision=historical_date(action['value'])
                if citation not in target.sources:target.sources.append(citation)
                details=deepcopy(target.catalog_details or {})
                details.update(date_scope='model',date_sources=[citation.id],date_evidence={'kind':'documented_launch','source_ids':[citation.id]})
                details.pop('reference_note',None)
                if before and before['release_date'] and (before['catalog_details'] or {}).get('date_evidence',{}).get('kind')=='reference':
                    details['reference_dates']=sorted(set(details.get('reference_dates',[]))|{before['release_date']})
                note=row.get('note')
                if target.price is not None:
                    note=' '.join(x for x in [note,'Data documentata del modello o allestimento; la fonte cronologica non prova la vendita a questo prezzo nel mercato indicato.'] if x)
                if note:details['commercialization_notes']=list(dict.fromkeys([*details.get('commercialization_notes',[]),note]))
                target.catalog_details=details
                imported.claims.append(ImportClaim(computer_id=c.id,source_id=citation.id,entity='Release',target_id=target.id,
                    field='release_date',value={'value':target.release_date.isoformat(),'precision':target.release_precision},
                    previous=previous,status='pending',estimated=False,evidence=action['evidence']+('\n'+note if note else '')))
                audit.append({'computer_id':c.id,'release_id':target.id,'before':before,'after':action['value'],
                    'source':row['source'],'evidence':action['evidence']})
                report['release_dates']+=1
            imported.status='updated';report['models_updated']+=1
        job.status='completed';report['import_job_id']=job.id
        db.add(CatalogReconciliation(entity='ibm_ps_dates',source_id=0,target_id=0,
            note='Cronologia IBM documentata, senza modificare importi, valute o mercati; asserzioni pending.',
            snapshot={**report,'checksum':checksum,'changes':audit}))
        db.flush()
        from ..catalog_store import refresh_pending
        refresh_pending(db,commit=False,locked=True)
        if commit:db.commit()
        return report
    except Exception:
        db.rollback();raise
