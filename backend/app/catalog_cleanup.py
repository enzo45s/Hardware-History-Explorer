"""Physical, audited normalization of the primary catalog (not another copy).

preview/apply operate on the original tables. Only compatible profiles and
complementary releases are combined; substantial variants stay separate.
Removed representations and old identifiers are archived in reconciliation
history, and reimports follow redirects instead of recreating retired rows.
"""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import json
import logging
import re
from pathlib import Path
from sqlalchemy import select, delete, update, func
from sqlalchemy.orm import Session
from .models import (Computer, Configuration, Specification, Release, Market,
    CatalogSnapshot, CatalogDirty, spec_source, release_source)
from .import_models import CatalogReconciliation, ComputerAlias, ImportClaim, ArchiveReset
from .admin import historical_date, catalog_lock

VERSION = 'hhe-physical-catalog-v1'
logger = logging.getLogger('uvicorn.error')
SPEC_FIELDS = ('component_type','component_name','property_name','numeric_value','text_value','unit')


def serial(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def physical_mode(db):
    if db.info.get('hhe_physical_mode'):return True
    enabled=db.scalar(select(CatalogReconciliation.id).where(CatalogReconciliation.entity == 'physical_cleanup').limit(1)) is not None
    if enabled:db.info['hhe_physical_mode']=True
    return enabled


def lock_primary_rows(db, ids=None):
    if db.bind.dialect.name!='postgresql':return
    computers=select(Computer.id)
    if ids is not None:computers=computers.where(Computer.id.in_(ids))
    identifiers=list(db.scalars(computers.order_by(Computer.id).with_for_update()))
    configs=list(db.scalars(select(Configuration.id).where(Configuration.computer_id.in_(identifiers)).order_by(Configuration.id).with_for_update()))
    specs=list(db.scalars(select(Specification.id).where(Specification.configuration_id.in_(configs)).order_by(Specification.id).with_for_update()))
    releases=list(db.scalars(select(Release.id).where(Release.computer_id.in_(identifiers)).order_by(Release.id).with_for_update()))
    for table,targets in ((spec_source,specs),(release_source,releases)):
        db.execute(select(table).where(table.c.target_id.in_(targets)).order_by(table.c.target_id,table.c.source_id).with_for_update()).all()


def native_text(entries):
    """Keep precise internal units in compound values, never relabel KiB as KB."""
    from .catalog_memory import number_text
    result = []
    for v in entries:
        if v['number'] is None:
            text = v['text']
            if v['unit'] and not re.search(r'\b(?:B|KiB|MiB|GiB|KB|MB|GB|Kb|Mb|Gb)\b', text):
                text += ' ' + v['unit']
        else:
            number, unit = v['number'], v['unit']
            if v['bytes'] is not None:
                number, unit = float(Decimal(str(v['bytes'])) / Decimal(1024)), 'KiB'
            text = number_text(number) + (' ' + unit if unit else '')
        label = ' · '.join(p for p in (v['role'],v['qualifier']) if p)
        result.append((label + ': ' if label else '') + text)
    return ' / '.join(dict.fromkeys(result))


def spec_values(row):
    view = row.get('normalized', row)
    fields = {k: view.get(k) for k in SPEC_FIELDS}
    details = {'clean': True}
    if fields['component_type'] == 'CPU' and (fields['component_name'] or '').lower() in ('cpu','maincpu','main-cpu'):
        fields['component_name'] = None
    if row.get('catalog_metric'):
        details.update(metric=row['catalog_metric'], resolution_state=row['resolution_state'], notes=row['memory_notes'])
        entries = row['memory_values']
        scalar = entries[0] if len(entries) == 1 else None
        if scalar and scalar['number'] is not None and not scalar['role'] and not scalar['qualifier']:
            number, unit = scalar['number'], scalar['unit'] or None
            if scalar['bytes'] is not None:
                number, unit = float(Decimal(str(scalar['bytes'])) / Decimal(1024)), 'KiB'
            fields.update(numeric_value=number,text_value=None,unit=unit)
        else:
            fields.update(numeric_value=None,text_value=native_text(entries) or 'Non documentata',unit=None)
    return {**fields,'catalog_details':details}


def snapshot(db, computer):
    tables = ((Configuration, Configuration.computer_id == computer.id),
              (Specification, Specification.configuration_id.in_([c.id for c in computer.configurations])),
              (Release, Release.computer_id == computer.id),
              (ComputerAlias, ComputerAlias.computer_id == computer.id))
    result = {}
    for model, cond in tables:
        result[model.__tablename__] = [{k:serial(v) for k,v in row._mapping.items()}
            for row in db.execute(select(model.__table__).where(cond).order_by(model.id))]
    for table, ids in ((spec_source,[s['id'] for s in result['specifications']]),
                       (release_source,[r['id'] for r in result['releases']])):
        result[table.name] = [dict(row._mapping) for row in db.execute(select(table).where(table.c.target_id.in_(ids)).order_by(table.c.target_id,table.c.source_id))]
    return result


def computer_plan(db, computer):
    from .catalog_store import raw_payload, consolidate, digest
    original = snapshot(db,computer)
    raw = raw_payload(computer)
    data = consolidate(raw, computer.model_name)
    configs, specs, releases = [], [], []
    used = set()
    for cfg in data['configurations']:
        details = {'catalog_clean':True, 'display_name':cfg['display_name'],
            'configuration_ids':cfg.get('configuration_ids',[cfg['id']])}
        for key in ('model_variant','regional_variants'):
            if cfg.get(key):details[key]=cfg[key]
        configs.append({'id':cfg['id'],'variant_name':cfg['display_name'][:140],
            'description':cfg.get('display_description') or None,'catalog_details':details,
            'original_ids':cfg.get('configuration_ids',[cfg['id']])})
        for i,row in enumerate(cfg['specifications']):
            originals = row.get('specification_ids',[row['id']])
            if not originals:
                continue  # An unknown primary RAM value is absence, not a new fact.
            candidates = [sid for sid in originals if sid not in used]
            target = row['id'] if isinstance(row['id'],int) and row['id'] in candidates else min(candidates) if candidates else None
            if target is None:
                raise ValueError('Una specifica sostiene più campi incompatibili: revisione necessaria.')
            used.add(target)
            specs.append({'id':target,'configuration_id':cfg['id'],**spec_values(row),'original_ids':originals})
    # Display names need not have been SQL-unique. Identify distinct hardware
    # with actual technical attributes rather than silently dropping a variant.
    from collections import defaultdict
    names=defaultdict(list)
    for cfg in configs:names[cfg['variant_name']].append(cfg)
    for name,group in names.items():
        if len(group)<2:continue
        candidates={cfg['id']:[s for s in specs if s['configuration_id']==cfg['id'] and s['component_type'] in ('CPU','ROM','Storage','Tastiera')] for cfg in group}
        labels=[]
        for cfg in group:
            labels.append(' · '.join(s['component_type']+' '+str(s['numeric_value'] if s['numeric_value'] is not None else s['text_value'])+(' '+s['unit'] if s['unit'] else '') for s in candidates[cfg['id']]))
        for index,cfg in enumerate(group,1):
            label=labels[index-1] if len(set(labels))==len(labels) and labels[index-1] else 'variante '+str(index)
            suffix=' · '+label
            cfg['variant_name']=name[:max(1,140-len(suffix))]+suffix[:139]
            cfg['catalog_details']['display_name']=cfg['variant_name']
    used_releases = set()
    for row in data['releases']:
        candidates = [rid for rid in row['release_ids'] if rid not in used_releases]
        if not candidates:
            raise ValueError('Una commercializzazione appartiene a più offerte: revisione necessaria.')
        target = row['id'] if row['id'] in candidates else min(candidates)
        used_releases.add(target)
        details = {'catalog_clean':True}
        for key in ('model_variant','display_model_variant','date_scope','date_evidence','reference_dates','reference_note','commercialization_notes','date_manual'):
            if row.get(key):details[key]=row[key]
        if row.get('field_sources',{}).get('release_date'):
            details['date_sources']=row['field_sources']['release_date']
        releases.append({'id':target,'market':row['market'],
            **{k:row.get(k) for k in ('release_date','discontinuation_date','price','currency','price_type')},
            'catalog_details':details,'original_ids':row['release_ids']})
    # The comparison projection is the contract: do not delete regional clock
    # evidence merely because public television refresh fields are hidden.
    retained = {sid for row in specs for sid in row['original_ids']}
    archived_only = [s['id'] for s in original['specifications'] if s['id'] not in retained]
    before_configs = [{k:r[k] for k in ('id','variant_name','description','catalog_details')} for r in original['configurations']]
    after_configs = [{k:r[k] for k in ('id','variant_name','description','catalog_details')} for r in configs]
    before_specs = [{k:r[k] for k in ('id','configuration_id',*SPEC_FIELDS,'catalog_details')} for r in original['specifications']]
    after_specs = [{k:r[k] for k in ('id','configuration_id',*SPEC_FIELDS,'catalog_details')} for r in specs]
    # Release dates have explicit precision in storage, represented by strings
    # of corresponding length here. Include scopes and market names in equality.
    # Compare with stored values, not enriched date context generated for a
    # read. A missing stored date must remain a real physical update.
    from .catalog_store import datefmt
    old_releases = [{'id':r.id,'market':r.market.name,
        'release_date':datefmt(r.release_date,r.release_precision),
        'discontinuation_date':datefmt(r.discontinuation_date,r.discontinuation_precision),
        'price':r.price,'currency':r.currency,'price_type':r.price_type,**(r.catalog_details or {})} for r in sorted(computer.releases,key=lambda r:r.id)]
    new_releases = [{'id':r['id'], **{k:r[k] for k in ('market','release_date','discontinuation_date','price','currency','price_type')},**r['catalog_details']} for r in releases]
    dirty = (sorted(before_configs,key=lambda r:r['id']) != sorted(after_configs,key=lambda r:r['id']) or
             sorted(before_specs,key=lambda r:r['id']) != sorted(after_specs,key=lambda r:r['id']) or old_releases != new_releases)
    return {'computer_id':computer.id,'model':computer.model_name,'token':digest(original),
        'changed':dirty,'configurations':configs,'specifications':specs,'releases':releases,
        'archive_only_specification_ids':archived_only,'original':original}


def prepare(db, ids=None):
    from .catalog_store import EAGER,digest
    stmt=select(Computer).order_by(Computer.id).options(*EAGER)
    if ids is not None:stmt=stmt.where(Computer.id.in_(ids))
    rows=[computer_plan(db,c) for c in db.scalars(stmt)]
    changes=[row for row in rows if row['changed']]
    from .catalog_schema import VERSION as rules_version
    import hashlib
    rules=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {'version':VERSION,'token':digest([rules_version,rules,[(r['computer_id'],r['token']) for r in rows]]),
        'summary':{'computers':len(rows),'affected_computers':len(changes),
            'configurations_removed':sum(len(r['original']['configurations'])-len(r['configurations']) for r in changes),
            'specifications_removed':sum(len(r['original']['specifications'])-len(r['specifications']) for r in changes),
            'releases_removed':sum(len(r['original']['releases'])-len(r['releases']) for r in changes)},
        'changes':changes}


def merged_links(rows, originals, target):
    by_source={}
    for row in rows:
        if row['target_id'] not in originals:continue
        by_source.setdefault(row['source_id'],[]).append(row)
    result=[]
    for sid, links in by_source.items():
        statuses={r['verification_status'] for r in links}
        evidence=list(dict.fromkeys(r['evidence'] for r in links if r['evidence']))
        result.append({'source_id':sid,'target_id':target,'evidence':'\n\n'.join(evidence) or None,
            'verification_status':next(iter(statuses)) if len(statuses)==1 else 'pending'})
    return result


def replace_links(db, table, original, target, links):
    before=sorted((r for r in original if r['target_id']==target),key=lambda r:r['source_id'])
    if before==sorted(links,key=lambda r:r['source_id']):return
    db.execute(delete(table).where(table.c.target_id==target))
    if links:db.execute(table.insert(),links)


def write_computer(db, plan):
    cid=plan['computer_id'];original=plan['original']
    cfg_map={old:r['id'] for r in plan['configurations'] for old in r['original_ids']}
    spec_map={old:r['id'] for r in plan['specifications'] for old in r['original_ids']}
    release_map={old:r['id'] for r in plan['releases'] for old in r['original_ids']}
    # Historical claims are retained. Record their old targets before updating
    # live pointers; stale acceptance is still blocked by the import reviewer.
    claim_targets=[]
    for entity,mapping in (('Configuration',cfg_map),('Specification',spec_map),('Release',release_map)):
        for claim in db.scalars(select(ImportClaim).where(ImportClaim.computer_id==cid,ImportClaim.entity==entity,ImportClaim.target_id.in_(list(mapping)))):
            new=mapping[claim.target_id]
            if new!=claim.target_id:
                claim_targets.append({'id':claim.id,'entity':entity,'target_id':claim.target_id})
                claim.target_id=new
    old_configs={r['id']:r for r in original['configurations']}
    rename=any(old_configs[r['id']]['variant_name']!=r['variant_name'] for r in plan['configurations'])
    if rename:
        for cfg in original['configurations']:
            db.execute(update(Configuration).where(Configuration.id==cfg['id']).values(variant_name=f'__physical_{cid}_{cfg["id"]}'))
    for row in plan['configurations']:
        fields={k:row[k] for k in ('variant_name','description','catalog_details')}
        if rename or any(old_configs[row['id']][k]!=v for k,v in fields.items()):
            db.execute(update(Configuration).where(Configuration.id==row['id']).values(**fields))
    old_specs={r['id']:r for r in original['specifications']}
    for row in plan['specifications']:
        fields={k:row[k] for k in ('configuration_id',*SPEC_FIELDS,'catalog_details')}
        if any(old_specs[row['id']][k]!=v for k,v in fields.items()):
            db.execute(update(Specification).where(Specification.id==row['id']).values(**fields))
        links=merged_links(original['specification_sources'],row['original_ids'],row['id'])
        replace_links(db,spec_source,original['specification_sources'],row['id'],links)
    removed_specs=set(old_specs)-{r['id'] for r in plan['specifications']}
    removed_configs=set(old_configs)-{r['id'] for r in plan['configurations']}
    if removed_specs:db.execute(delete(Specification).where(Specification.id.in_(removed_specs)))
    if removed_configs:db.execute(delete(Configuration).where(Configuration.id.in_(removed_configs)))
    release_fingerprints={}
    old_releases={r['id']:r for r in original['releases']}
    from .catalog_store import digest
    for row in plan['releases']:
        market=db.scalar(select(Market).where(Market.name==row['market']))
        if market is None:
            market=Market(name=row['market']);db.add(market);db.flush()
        fields={k:row[k] for k in ('price','currency','price_type','catalog_details')};fields['market_id']=market.id
        for name in ('release','discontinuation'):
            fields[name+'_date'],fields[name+'_precision']=historical_date(row[name+'_date'])
        release_fingerprints[row['id']]=digest({k:serial(v) for k,v in fields.items() if k!='catalog_details'})
        if any(old_releases[row['id']][k]!=serial(v) for k,v in fields.items()):
            db.execute(update(Release).where(Release.id==row['id']).values(**fields))
        links=merged_links(original['release_sources'],row['original_ids'],row['id'])
        existing={r['source_id'] for r in links}
        allowed={r['source_id'] for r in original['release_sources']}
        for sid in row['catalog_details'].get('date_sources',[]):
            if sid in allowed and sid not in existing:
                links.append({'source_id':sid,'target_id':row['id'],'verification_status':'pending',
                    'evidence':'Fonte del contesto cronologico del modello; non prova autonoma del prezzo o della disponibilità nel mercato.'})
        replace_links(db,release_source,original['release_sources'],row['id'],links)
    removed_releases=set(old_releases)-{r['id'] for r in plan['releases']}
    if removed_releases:db.execute(delete(Release).where(Release.id.in_(removed_releases)))
    for alias in db.scalars(select(ComputerAlias).where(ComputerAlias.computer_id==cid)):
        value=deepcopy(alias.original)
        for key,mapping in (('configurations',cfg_map),('releases',release_map)):
            value[key]=list(dict.fromkeys(mapping.get(i,i) for i in value.get(key,[])))
        if alias.original!=value:alias.original=value
    db.flush()
    from .catalog_store import digest
    fingerprints={r['id']:digest({k:r[k] for k in SPEC_FIELDS}) for r in plan['specifications']}
    return {'computer_id':cid,'original':original,'claim_targets':claim_targets,'target_fingerprints':fingerprints,'release_fingerprints':release_fingerprints,
        'redirects':{'Configuration':cfg_map,'Specification':spec_map,'Release':release_map}}


def apply(db, plan, *, commit=True, locked=False, enable=True):
    if not locked:catalog_lock(db)
    lock_primary_rows(db)
    current=prepare(db)
    if plan.get('version')!=VERSION or plan.get('token')!=current['token']:
        raise ValueError('Il catalogo è cambiato: prepara una nuova anteprima della pulizia.')
    archives=[write_computer(db,row) for row in current['changes']]
    if archives or (enable and not physical_mode(db)):
        audit=CatalogReconciliation(entity='physical_cleanup',source_id=0,target_id=0,
            note='Pulizia fisica delle tabelle principali; originali accorpati conservati solo nell’audit.',
            snapshot={'version':VERSION,'token':current['token'],'summary':current['summary'],'computers':archives})
        db.add(audit);db.flush();aid=audit.id
    else:aid=None
    db.execute(delete(CatalogSnapshot));db.execute(delete(CatalogDirty))
    if enable:
        from .catalog_schema import VERSION as rules_version
        marker=db.scalar(select(CatalogReconciliation).where(CatalogReconciliation.entity=='catalog_rules').order_by(CatalogReconciliation.id.desc()).limit(1))
        if marker is None or marker.snapshot.get('version')!=rules_version:
            db.add(CatalogReconciliation(entity='catalog_rules',source_id=0,target_id=0,
                note='Pulizia fisica completata con le regole correnti.',snapshot={'version':rules_version}))
    if commit:db.commit()
    return {**current['summary'],'audit_id':aid,'storage':'primary_tables'}


def refresh_clean(db, *,commit=True,locked=False):
    if not locked:catalog_lock(db)
    query=select(CatalogDirty.computer_id).order_by(CatalogDirty.computer_id)
    if db.bind.dialect.name=='postgresql':query=query.with_for_update()
    ids=list(db.scalars(query))
    lock_primary_rows(db,ids)
    from .catalog_store import EAGER
    archives=[]
    # Re-queueing caused by our own writes is cleared in this same transaction.
    logger.info('Normalizzazione catalogo: avvio su %s sistemi.',len(ids))
    for index,c in enumerate(db.scalars(select(Computer).where(Computer.id.in_(ids)).options(*EAGER).execution_options(populate_existing=True)),1):
        row=computer_plan(db,c)
        if row['changed']:archives.append(write_computer(db,row))
        if index%50==0 or index==len(ids):
            logger.info('Normalizzazione catalogo: elaborati %s/%s; modificati %s. Transazione in corso.',index,len(ids),len(archives))
    if archives:
        db.add(CatalogReconciliation(entity='physical_cleanup',source_id=0,target_id=0,
            note='Pulizia incrementale dei dati modificati.',snapshot={'version':VERSION,'computers':archives}))
    db.execute(delete(CatalogDirty).where(CatalogDirty.computer_id.in_(ids)))
    if commit:
        db.commit()
        logger.info('Normalizzazione catalogo: completata e salvata (%s sistemi).',len(ids))
    return {'updated':len(archives),'processed':len(ids)}


def history(db, cid):
    cutoff=db.scalar(select(ArchiveReset.reconciliation_cutoff).order_by(ArchiveReset.id.desc()).limit(1)) or 0
    latest=db.scalar(select(func.max(CatalogReconciliation.id)).where(CatalogReconciliation.entity=='physical_cleanup')) or 0
    marker=(cutoff,latest)
    cached=db.info.get('hhe_physical_history')
    if cached is None or cached[0]!=marker:
        index={}
        for audit in db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity=='physical_cleanup',CatalogReconciliation.id>cutoff).order_by(CatalogReconciliation.id.desc())):
            for row in audit.snapshot.get('computers',[]):index.setdefault(row['computer_id'],[]).append(row)
        cached=(marker,index);db.info['hhe_physical_history']=cached
    yield from cached[1].get(cid,[])


def redirect(db, cid, entity, identifier):
    result=identifier
    # Repeated cleanups may retire a previously surviving identifier.
    rows=list(history(db,cid))
    for row in reversed(rows):
        result=row['redirects'].get(entity,{}).get(str(result),row['redirects'].get(entity,{}).get(result,result))
    return result


def incoming_configuration(db,cid,name,alias=None):
    candidates=set()
    from .importing.normalize import name_key
    for row in history(db,cid):
        names={cfg['id']:cfg['variant_name'] for cfg in row['original']['configurations']}
        if alias:
            old=next((a for a in row['original']['computer_aliases'] if a['id']==alias.id),None)
            names={int(k):v for k,v in old['original'].get('configuration_names',{}).items()} if old else {}
        for identifier,value in names.items():
            if name_key(value)==name_key(name):candidates.add(redirect(db,cid,'Configuration',identifier))
    if len(candidates)>1:raise ValueError('Configurazione storica ambigua dopo la pulizia; seleziona la variante.')
    historical = db.get(Configuration,next(iter(candidates))) if candidates else None
    if historical is not None or alias:
        return historical
    # A canonical sheet may also be reserved by aliases of retired variants.
    # A new source using its current exact name must enrich that sheet instead
    # of attempting to insert another row with the same unique name. Former
    # variant names still follow their historical scopes above.
    return db.scalar(select(Configuration).where(Configuration.computer_id==cid,
                                                 Configuration.variant_name==name))


def incoming_specification(db,cid,cfg,incoming):
    from .importing.vocabulary import normalize_spec
    from .catalog_display import specification_display
    values=normalize_spec(incoming);values.update(specification_display(values))
    if values['component_type']=='RAM':
        prop=values['property_name'].lower()
        capacity=('capacit' in prop or 'dotazion' in prop) and not any(p in prop for p in ('massim','minim','limite'))
        metric='ram.capacity' if capacity or 'annotazion' in prop else 'ram.options'
        matches=[s for s in cfg.specifications if (s.catalog_details or {}).get('metric')==metric]
        return matches[0] if len(matches)==1 else None
    from .importing.vocabulary import key
    def role(v):
        name=key(v or '')
        return '' if name in ('cpu','maincpu','main-cpu') else name
    matches=[s for s in cfg.specifications if (s.catalog_details or {}).get('clean')
        and key(s.component_type)==key(values['component_type']) and key(s.property_name)==key(values['property_name'])
        and role(s.component_name)==role(values.get('component_name'))]
    return matches[0] if len(matches)==1 else None


def promotes_reference(cfg,incoming):
    from .importing.vocabulary import normalize_spec
    from .catalog_display import specification_display
    values=normalize_spec(incoming);values.update(specification_display(values))
    if values['component_type']!='RAM':return False
    prop=values['property_name'].lower()
    capacity=('capacit' in prop or 'dotazion' in prop) and not any(p in prop for p in ('massim','minim','limite'))
    if not capacity:return False
    primary=next((s for s in cfg.specifications if (s.catalog_details or {}).get('metric')=='ram.capacity'),None)
    if primary is None:return False
    state=primary.catalog_details['resolution_state']
    return state=='unknown' or (state=='reference' and 'riferimento' not in prop)


def represented_quantity(db,target,incoming):
    """A reviewed part of a compound fact need not replace the complete fact."""
    from .catalog_store import digest
    from .importing.vocabulary import spec_values as values
    from .catalog_memory import entry
    cid=target.configuration.computer_id
    current=digest(values(target))
    def equivalent(old):
        left=entry({k:old.get(k) for k in ('numeric_value','text_value','unit')});right=entry(incoming)
        return left is not None and right is not None and left['identity']==right['identity']
    for row in history(db,cid):
        fingerprints=row.get('target_fingerprints',{})
        if fingerprints.get(str(target.id),fingerprints.get(target.id))!=current:continue
        for old in row['original']['specifications']:
            mapped=row['redirects']['Specification'].get(str(old['id']),row['redirects']['Specification'].get(old['id']))
            if (mapped==target.id or mapped is not None and redirect(db,cid,'Specification',old['id'])==target.id) and equivalent(old):return True
    return False


def represented_release_field(db,target,field,incoming):
    if field not in ('market_id','release_date','discontinuation_date'):return False
    from .catalog_store import digest
    fields=('market_id','release_date','release_precision','discontinuation_date','discontinuation_precision','price','currency','price_type')
    current=digest({k:serial(getattr(target,k)) for k in fields})
    events=list(history(db,target.computer_id))
    if not any(event.get('release_fingerprints',{}).get(str(target.id),event.get('release_fingerprints',{}).get(target.id))==current for event in events):return False
    for row in events:
        for old in row['original']['releases']:
            mapped=row['redirects']['Release'].get(str(old['id']),row['redirects']['Release'].get(old['id']))
            if mapped is None or mapped!=target.id and redirect(db,target.computer_id,'Release',old['id'])!=target.id:continue
            expected={'value':old[field]}
            if field.endswith('_date'):expected['precision']=old[field.replace('_date','_precision')]
            if incoming==expected:return True
    return False


def incoming_release(db,cid,market,entry):
    candidates=set()
    for row in history(db,cid):
        # Original markets can still be dictionary entries; active releases
        # are matched by the old documented combination, including price.
        for old in row['original']['releases']:
            if old['market_id']!=market.id:continue
            day,_=historical_date(entry.get('release_date'))
            if old['release_date']!=serial(day):continue
            if entry.get('price') is not None and (old['price'],old['currency'])!=(entry['price'],entry.get('currency')):continue
            candidates.add(redirect(db,cid,'Release',old['id']))
    return db.get(Release,min(candidates)) if len(candidates)==1 else None
