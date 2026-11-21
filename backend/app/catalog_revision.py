"""Preview and apply auditable, representation-only catalog revisions.

Run inside the API container: python -m app.catalog_revision preview --output
/tmp/hhe-revision.json, then apply --plan /tmp/hhe-revision.json.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, selectinload

from .models import (Computer, Manufacturer, Configuration, Specification, Release,
                     spec_source, Source)
from .import_models import CatalogReconciliation
from .importing.identity import maker_key
from .importing.vocabulary import spec_values
from .importing import reconcile
from .measurement_cleanup import normalize_measurement, split_cpu
from .catalog_display import specification_display
from .admin import catalog_lock

VERSION = 'hhe-catalog-revision-v1'


def serial(value):
    return value.isoformat() if isinstance(value, (datetime, date)) else value


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def role(value):
    value = (value or '').strip().casefold()
    return '' if value in ('maincpu', 'main-cpu', 'cpu') else value


def prepare(db):
    makers = db.scalars(select(Manufacturer).order_by(Manufacturer.id)).all()
    computers = db.execute(select(Computer.id, Computer.manufacturer_id, Computer.model_name).order_by(Computer.id)).all()
    configurations = db.scalars(select(Configuration).order_by(Configuration.id)).all()
    specifications = db.scalars(select(Specification).order_by(Specification.id)).all()
    links = [{k:serial(v) for k,v in r._mapping.items()} for r in db.execute(select(spec_source).order_by(spec_source.c.target_id, spec_source.c.source_id))]
    identity = [(m.id,m.name,m.country,serial(m.founded),m.website) for m in makers]
    matrix = [(s.id,s.configuration_id,spec_values(s)) for s in specifications]
    token = digest({'version':VERSION,'manufacturers':identity,'computers':[list(r) for r in computers],
                    'configurations':[(c.id,c.computer_id,c.variant_name) for c in configurations], 'specifications':matrix,'links':links})
    cfgs = {c.id:c for c in configurations}; names={r.id:r.model_name for r in computers}
    by_cfg = defaultdict(list); changes=[]; additions=[]; review=[]
    normalized = {s.id:normalize_measurement(spec_values(s)) for s in specifications}
    for s in specifications:by_cfg[s.configuration_id].append(s)
    for s in specifications:
        before = spec_values(s); after = normalized[s.id]
        display = specification_display(before)
        if s.component_type == 'CPU' and display['property_name'] == 'Modello':
            parts = split_cpu(s.text_value)
            if parts:
                model, quantity = parts
                candidates=[v for v in by_cfg[s.configuration_id] if v.id != s.id and v.component_type=='CPU'
                            and role(v.component_name)==role(s.component_name)
                            and specification_display(spec_values(v))['property_name'] == quantity['property_name']]
                fields=('numeric_value','text_value','unit')
                if len(candidates)>1 or (candidates and any(normalized[candidates[0].id].get(k)!=quantity.get(k) for k in fields)):
                    review.append({'id':s.id,'model':names[cfgs[s.configuration_id].computer_id], 'reason':'Frequenza incorporata diversa o ambigua rispetto alla frequenza già registrata.'})
                else:
                    after={**after,'text_value':model}
                    additions.append({'origin_id':s.id,'target_id':candidates[0].id if candidates else None,
                        'configuration_id':s.configuration_id, 'values':{'component_type':'CPU','component_name':s.component_name,**quantity}})
        if after != before:
            changes.append({'id':s.id,'computer_id':cfgs[s.configuration_id].computer_id,
                            'model':names[cfgs[s.configuration_id].computer_id], 'before':before,'after':after})
        # Do not "correct" historical KB/MB into binary prefixes without proof.
        if s.component_type in ('RAM','ROM','Memoria','Cache'):
            import re
            if s.unit in ('KB','kB','MB','GB','kb','Kb','mb','Mb','gb','Gb') or re.search(r'\d\s*[kKmMgG][bB]\b',s.text_value or ''):
                review.append({'id':s.id,'model':names[cfgs[s.configuration_id].computer_id],
                               'reason':'Prefisso storico o bit/byte ambiguo; quantità e scala conservate.'})
    groups=defaultdict(list)
    for m in makers:groups[maker_key(m.name)].append(m)
    merges=[]
    for key,items in groups.items():
        if len(items)<2:continue
        # Only explicitly registered aliases; conflicting manufacturer metadata
        # is reported rather than silently discarded.
        canonical = min(items,key=lambda m:(m.name.casefold()!=key,len(m.name),m.id))
        for source in items:
            if source.id==canonical.id:continue
            differences=[f for f in ('country','founded','website') if getattr(source,f) and getattr(canonical,f)
                         and getattr(source,f)!=getattr(canonical,f)]
            if differences:
                review.append({'manufacturer_id':source.id,'reason':'Metadati produttore discordanti: '+', '.join(differences)})
            else:merges.append({'source_id':source.id,'target_id':canonical.id,'source_name':source.name,'target_name':canonical.name})
    # Stored releases can carry different provenance/review decisions. Report
    # exact repeats, but keep every ID and claim; the reader already combines them.
    releases=db.scalars(select(Release).order_by(Release.id)).all(); release_groups=defaultdict(list)
    for r in releases:
        fields=(r.computer_id,r.market_id,serial(r.release_date),r.release_precision,serial(r.discontinuation_date),r.discontinuation_precision,r.price,r.currency,r.price_type)
        release_groups[fields].append(r.id)
    repeated=[g for g in release_groups.values() if len(g)>1]
    return {'version':VERSION,'token':token,
        'counts':{'computers':len(computers),'manufacturers':len(makers),'configurations':len(configurations),
                  'specifications':len(specifications),'sources':db.scalar(select(func.count()).select_from(Source)),
                  'releases':len(releases)},
        'summary':{'specifications_to_normalize':len(changes),'cpu_fields_to_split':len(additions),
                   'manufacturer_aliases_to_merge':len(merges),'items_requiring_review':len(review),
                   'repeated_release_groups_preserved':len(repeated)},
        'changes':changes,'cpu_frequencies':additions,'manufacturer_merges':merges,'review':review,
        'release_groups_preserved':repeated}


def apply(db, plan):
    catalog_lock(db)
    current=prepare(db)
    if plan.get('version')!=VERSION or plan.get('token')!=current['token']:
        raise ValueError('Il catalogo è cambiato o il piano è di un’altra versione: prepara una nuova anteprima.')
    # Never execute user-edited operations from the plan file. Recompute them
    # under the catalog lock and use only the matched snapshot token.
    if not (current['changes'] or current['cpu_frequencies'] or current['manufacturer_merges']):
        db.rollback();return {'updated':0,'created':0,'manufacturers_merged':0,'audit_id':None}
    before_links=[dict(r._mapping) for r in db.execute(select(spec_source).where(spec_source.c.target_id.in_([v['id'] for v in current['changes']])))]
    created=[];copied=[];maker_audits=[]
    for row in current['changes']:
        spec=db.get(Specification,row['id'])
        for field,value in row['after'].items():setattr(spec,field,value)
    for row in current['cpu_frequencies']:
        target=db.get(Specification,row['target_id']) if row['target_id'] else Specification(configuration_id=row['configuration_id'],**row['values'])
        if not row['target_id']:
            db.add(target);db.flush();created.append(target.id)
        existing=set(db.scalars(select(spec_source.c.source_id).where(spec_source.c.target_id==target.id)))
        for link in db.execute(select(spec_source).where(spec_source.c.target_id==row['origin_id'])):
            values=dict(link._mapping)
            if values['source_id'] not in existing:
                values['target_id']=target.id;db.execute(spec_source.insert().values(**values));copied.append(values)
    for row in current['manufacturer_merges']:
        _,_,_,preview=reconcile.prepare(db,'manufacturer',row['source_id'],row['target_id'])
        result=reconcile.apply(db,'manufacturer',row['source_id'],row['target_id'],preview['token'],
            'Alias esplicito del produttore; revisione '+VERSION,commit=False)
        maker_audits.append(result['reconciliation_id'])
    audit=CatalogReconciliation(entity='normalization',source_id=0,target_id=0,
        note='Normalizzazione documentata delle rappresentazioni, senza verifica storica automatica.',
        snapshot={'version':VERSION,'token':current['token'],'summary':current['summary'],'specifications':current['changes'],
                  'new_specification_ids':created,'previous_source_links':before_links,'copied_source_links':copied,
                  'manufacturer_reconciliation_ids':maker_audits})
    db.add(audit);db.flush();audit_id=audit.id;db.commit()
    return {'updated':len(current['changes']),'created':len(created),'manufacturers_merged':len(maker_audits),'audit_id':audit_id}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    preview=commands.add_parser('preview');preview.add_argument('--output',type=Path,required=True)
    execute=commands.add_parser('apply');execute.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args()
    url=os.getenv('DATABASE_URL')
    if not url:parser.error('DATABASE_URL deve indicare esplicitamente il database da esaminare.')
    engine=create_engine(url,pool_pre_ping=True)
    with Session(engine) as db:
        if args.command=='preview':
            plan=prepare(db)
            with args.output.open('x',encoding='utf-8') as f:json.dump(plan,f,ensure_ascii=False,indent=2)
            print(json.dumps({'file':str(args.output),**plan['summary']},ensure_ascii=False))
        else:
            try:print(json.dumps(apply(db,json.loads(args.plan.read_text(encoding='utf-8'))),ensure_ascii=False))
            except ValueError as e:db.rollback();raise SystemExit(str(e))
    engine.dispose()


if __name__=='__main__':main()
