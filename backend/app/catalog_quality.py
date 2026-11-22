"""RAM recovery and explicit consolidation of configuration-only product names."""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from .admin import Input, catalog_lock
from .models import Computer, Configuration, Specification
from .import_models import ImportJob, ImportRow, ComputerAlias, CatalogReconciliation
from .history_models import HistoryJob, HistoryItem
from .history_sources import model_key, replaceable
from .source_policy import is_internal_source
from .importing import reconcile
from .importing.catalog_aliases import remember, alias_for
from .importing.variant_names import variant_name
from .importing.identity import maker_key, provider_computer_key
from .importing.engine import stage, apply_job, identity_provider
from .importing.vocabulary import normalize_spec, spec_values
from .catalog_names import catalog_name

RAM_BUNDLE = Path(__file__).parent / 'importing/data/ram-reviewed-v1.json'
EAGER = (selectinload(Computer.manufacturer), selectinload(Computer.configurations).selectinload(Configuration.specifications))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def capacity(spec):
    values = normalize_spec(spec_values(spec)) if isinstance(spec, Specification) else normalize_spec(spec)
    name = values['property_name'].casefold()
    return (values['component_type'] == 'RAM' and 'capacit' in name
        and not any(word in name for word in ('massima', 'minima', 'limite', 'opzioni'))
        and (values.get('numeric_value') is not None or (values.get('text_value') or '').strip().casefold()
             not in ('', '?', 'unknown', 'n/a', 'non disponibile')))


def ram_preview(db):
    computers = db.scalars(select(Computer).options(*EAGER).order_by(Computer.id)).all()
    missing = {c.id: c for c in computers if not any(capacity(s) for cfg in c.configurations for s in cfg.specifications)}
    records, proposals = {}, []
    def offer(c, record, provider=None):
        for incoming in record.get('configurations', []):
            config = next((cfg for cfg in c.configurations if cfg.variant_name == incoming['variant_name']), None)
            if provider:
                original = reconcile.reconciled_configuration(db, c.id, identity_provider(provider, record), record.get('external_id'), incoming['variant_name'])
                if original:
                    config = original
                alias = alias_for(db, record['manufacturer'], record['model_name'], c.id)
                if alias and (config is None or config.id not in alias.original.get('configurations', [])):
                    continue
            if config and any(capacity(s) for s in config.specifications):
                continue
            specs = [s for s in incoming.get('specifications', []) if capacity(s)]
            if len(specs) != 1:
                continue
            for spec in specs:
                citation = spec.get('source') or incoming.get('source') or record['source']
                if not capacity(spec) or is_internal_source(citation):
                    continue
                if config:
                    from .unit_review import reviewed_import_target
                    if reviewed_import_target(db, config.specifications, spec, citation) is not None:
                        continue
                root = records.setdefault(c.id, {'manufacturer': c.manufacturer.name, 'model_name': c.model_name,
                    'source': citation, 'configurations': []})
                name = config.variant_name if config else incoming['variant_name']
                if any(cfg['variant_name'] == name for cfg in root['configurations']):
                    continue
                entry = {'variant_name': name, 'source': citation,
                         'specifications': [{**deepcopy(spec), 'source': citation}]}
                root['configurations'].append(entry)
                value = str(spec.get('numeric_value')) + ' ' + (spec.get('unit') or '') if spec.get('numeric_value') is not None else spec.get('text_value')
                proposals.append({'computer_id': c.id, 'model_name': c.model_name, 'configuration': entry['variant_name'],
                                  'value': value, 'source': citation})
    for record in json.loads(RAM_BUNDLE.read_text(encoding='utf-8'))['records']:
        for c in missing.values():
            if catalog_name(c.model_name) != c.model_name:
                continue  # A research alias does not attest a variant's RAM.
            if model_key(c.manufacturer.name, c.model_name) == model_key(record['manufacturer'], record['model_name']):
                offer(c, record)
    # Recover only already-applied records, never silently apply staged/failed uploads.
    if missing:
        approved = db.scalars(select(ImportRow).join(ImportJob).where(ImportRow.computer_id.in_(missing),
            ImportRow.status.in_(['imported', 'updated', 'unchanged']), ImportJob.status.in_(['completed', 'partial'])).order_by(ImportRow.id))
        for row in approved:
            if row.normalized:
                offer(missing[row.computer_id], row.normalized, db.get(ImportJob, row.job_id).provider)
    matrix = [(c.id, c.model_name, c.manufacturer_id,
        [(cfg.id, cfg.variant_name, [spec_values(s) for s in cfg.specifications if s.component_type == 'RAM']) for cfg in c.configurations]) for c in computers]
    unresolved = [c for cid, c in missing.items() if cid not in records]
    data = {'records': records, 'proposals': proposals, 'total': len(computers), 'without_ram': len(missing),
        'unresolved': len(unresolved), 'examples': [{'id': c.id, 'model_name': c.model_name, 'manufacturer': c.manufacturer.name} for c in unresolved[:100]]}
    data['token'] = digest({'matrix': matrix, 'records': records})
    return data


def variant_preview(db):
    computers = db.scalars(select(Computer).options(*EAGER).order_by(Computer.id)).all()
    groups = defaultdict(list)
    descriptors = {}
    for c in computers:
        rule = variant_name(c.manufacturer.name, c.model_name)
        if rule:
            key = (maker_key(c.manufacturer.name), rule['name'].casefold())
            groups[key].append(c); descriptors[key] = rule
    for key, items in groups.items():
        for c in computers:
            if c not in items and maker_key(c.manufacturer.name) == key[0] and c.model_name.casefold() == key[1]:
                items.append(c)
    plans = []
    for key, items in groups.items():
        rule = descriptors[key]
        if len(items) == 1 and items[0].model_name == rule['name']:
            continue
        target = min(items, key=lambda c: (provider_computer_key('historical_prices', c.manufacturer.name, c.model_name) != provider_computer_key('historical_prices', c.manufacturer.name, rule['name']), c.id))
        sources = [c for c in items if c.id != target.id]
        originals = [reconcile.snapshot(db, 'computer', target, target)] + [reconcile.prepare(db, 'computer', c.id, target.id, variants=True)[2] for c in sources]
        plans.append({'target_id': target.id, 'name': rule['name'], 'manufacturer': target.manufacturer.name,
            'reason': rule['reason'], 'sources': [{'id': c.id, 'name': c.model_name} for c in sources],
            'variants': [c.model_name for c in items], 'token': digest(originals)})
    return {'groups': plans, 'removed': sum(len(g['sources']) for g in plans), 'renamed': len(plans),
            'token': digest(plans)}


class Token(Input):
    token: str = Field(pattern=r'^[a-f0-9]{64}$')


class Consolidate(Token):
    target_ids: list[int] = Field(min_length=1, max_length=100)


def create_quality_router(get_db):
    router = APIRouter(prefix='/api/admin/catalog-quality', tags=['RAM e configurazioni'])

    @router.get('/physical')
    def physical_preview(db: Session = Depends(get_db)):
        from .catalog_cleanup import prepare,physical_mode
        try:plan=prepare(db)
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc
        return {'token':plan['token'],'summary':plan['summary'],'enabled':physical_mode(db),
            'models':[{'id':r['computer_id'],'name':r['model']} for r in plan['changes']]}

    @router.post('/physical/apply')
    def physical_apply(data: Token,db: Session = Depends(get_db)):
        from .catalog_cleanup import prepare,apply
        catalog_lock(db)
        plan=prepare(db)
        if data.token!=plan['token']:
            raise HTTPException(409,'Il catalogo è cambiato: aggiorna l’anteprima della pulizia.')
        try:return apply(db,plan,locked=True)
        except ValueError as exc:
            db.rollback();raise HTTPException(409,str(exc)) from exc

    @router.get('/consolidated')
    def consolidated_status(db: Session = Depends(get_db)):
        from .catalog_store import status
        return status(db)

    @router.post('/consolidated/rebuild')
    def consolidated_rebuild(db: Session = Depends(get_db)):
        from .catalog_store import rebuild, status
        return {**rebuild(db), **status(db)}

    @router.get('/units')
    def units(db: Session = Depends(get_db)):
        from .unit_review import prepare
        plan = prepare(db)
        return {**{key: plan[key] for key in ('version', 'token', 'summary', 'remaining', 'unquantified', 'partially_quantified')},
                'changes': [{**{key: row[key] for key in ('id', 'model', 'action', 'before', 'after', 'interpretation')},
                    'sources': [proof['source'] for proof in row['proofs'] if not is_internal_source(proof['source'])]}
                    for row in plan['changes']]}

    @router.get('/units/report')
    def units_report(db: Session = Depends(get_db)):
        from fastapi.responses import Response
        from .unit_review import prepare
        return Response(json.dumps(prepare(db), ensure_ascii=False, indent=2), media_type='application/json',
                        headers={'Content-Disposition': 'attachment; filename="hhe-unita.json"'})

    @router.post('/units/apply')
    def units_apply(data: Token, db: Session = Depends(get_db)):
        from .unit_review import apply, VERSION
        try:
            return apply(db, {'version': VERSION, 'token': data.token})
        except ValueError as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc

    @router.get('/ram')
    def memory(db: Session = Depends(get_db)):
        result = ram_preview(db); result.pop('records')
        return result

    @router.post('/ram/apply')
    def memory_apply(data: Token, db: Session = Depends(get_db)):
        catalog_lock(db)
        plan = ram_preview(db)
        if plan['token'] != data.token:
            raise HTTPException(409, 'I dati RAM sono cambiati: aggiorna l’anteprima.')
        selected = list(plan['records'].items())[:200]
        if not selected:
            return {'updated': 0, 'remaining': 0}
        records = [record for _, record in selected]
        job = stage(db, 'manual', 'ram-documented.json', 'json', json.dumps(records, ensure_ascii=False).encode(),
            records=records, options={'upload': True, 'existing_only': True}, commit=False)
        for row, (cid, _) in zip(job.rows, selected):
            row.computer_id, row.candidates, row.status = cid, [cid], 'ready'
        apply_job(db, job.id, commit=False)
        if job.status != 'completed':
            db.rollback()
            raise HTTPException(409, 'RAM non applicata: controlla la corrispondenza delle configurazioni e aggiorna l’anteprima.')
        db.commit()
        return {'updated': len(selected), 'remaining': max(0, len(plan['records']) - len(selected)), 'job_id': job.id}

    @router.get('/variants')
    def variants(db: Session = Depends(get_db)):
        return variant_preview(db)

    @router.post('/variants/apply')
    def consolidate(data: Consolidate, db: Session = Depends(get_db)):
        catalog_lock(db)
        plan = variant_preview(db)
        if data.token != plan['token']:
            raise HTTPException(409, 'Le varianti sono cambiate: aggiorna l’anteprima prima di accorparle.')
        groups = [g for g in plan['groups'] if g['target_id'] in data.target_ids]
        if len(groups) != len(set(data.target_ids)):
            raise HTTPException(422, 'Gruppo non presente nell’anteprima.')
        audits = []
        try:
            for group in groups:
                target = db.get(Computer, group['target_id'])
                old_name = target.model_name
                generated = replaceable(old_name, target.manufacturer.name, target.description)
                canonical_key = provider_computer_key('historical_prices', target.manufacturer.name, group['name'])
                renamed = provider_computer_key('historical_prices', target.manufacturer.name, target.model_name) != canonical_key
                members = [target] + [db.get(Computer, item['id']) for item in group['sources']]
                for c in members:
                    if provider_computer_key('historical_prices', c.manufacturer.name, c.model_name) != canonical_key:
                        remember(db, c, target.id)
                if not group['sources']:
                    audit = CatalogReconciliation(entity='computer', source_id=target.id, target_id=target.id,
                        note='Pulizia del nome principale; attributi e identificativi originali conservati.',
                        snapshot={**reconcile.snapshot(db, 'computer', target, target),
                                  'variant_consolidation': {'name': group['name']}})
                    db.add(audit); db.flush(); audits.append(audit.id)
                for item in group['sources']:
                    preview = reconcile.prepare(db, 'computer', item['id'], target.id, variants=True)[3]
                    result = reconcile.apply(db, 'computer', item['id'], target.id, preview['token'],
                        'Accorpamento esplicito di varianti in configurazioni; sigle, RAM e dati originali conservati.', commit=False, variants=True)
                    audit = db.get(CatalogReconciliation, result['reconciliation_id'])
                    audit.snapshot = {**audit.snapshot, 'variant_consolidation': {'name': group['name']}}
                    audits.append(audit.id)
                target.model_name = group['name']
                if old_name != target.model_name and not group['sources'] and generated and target.description:
                    target.description = target.description.replace(old_name, target.model_name, 1)
                if renamed and group['sources']:
                    # Variant-specific prose remains available in the variant context.
                    target.description = f'{target.model_name} è un calcolatore di {target.manufacturer.name}.'
                    target.announcement_date, target.announcement_precision = None, None
                    context = json.loads(RAM_BUNDLE.read_text(encoding='utf-8')).get('contexts', {}).get(target.model_name)
                    if context:
                        target.description = None
                        record = {'manufacturer': target.manufacturer.name, 'model_name': target.model_name, **context}
                        job = stage(db, 'manual', 'product-context.json', 'json', json.dumps([record], ensure_ascii=False).encode(),
                            records=[record], options={'upload': True, 'existing_only': True}, commit=False)
                        job.rows[0].computer_id, job.rows[0].candidates = target.id, [target.id]
                        apply_job(db, job.id, commit=False)
                        if job.status != 'completed':
                            raise ValueError('Impossibile conservare il contesto storico del modello comune.')
                from .photo_jobs import PhotoItem
                from .commons import photo_query
                from .importing.bulk1000bit import BulkTarget
                for item in db.scalars(select(PhotoItem).where(PhotoItem.computer_id == target.id, PhotoItem.status == 'pending')):
                    item.model_name = target.model_name; item.query = photo_query(target.manufacturer.name, target.model_name)
                for item in db.scalars(select(BulkTarget).where(BulkTarget.computer_id == target.id)):
                    item.model_name, item.manufacturer = target.model_name, target.manufacturer.name
                for item in db.scalars(select(HistoryItem).where(HistoryItem.computer_id == target.id, HistoryItem.status == 'pending')):
                    item.status, item.error = 'changed', 'Variante accorpata; il modello comune viene ricercato separatamente.'
                active = db.scalar(select(HistoryJob).where(HistoryJob.active_key == 'italian').with_for_update())
                if active and replaceable(target.model_name, target.manufacturer.name, target.description):
                    position = (db.scalar(select(func.max(HistoryItem.position)).where(HistoryItem.job_id == active.id)) or 0) + 1
                    db.add(HistoryItem(job_id=active.id, position=position, computer_id=target.id,
                        model_name=target.model_name, manufacturer=target.manufacturer.name, previous=target.description))
            db.commit()
        except ValueError as exc:
            db.rollback(); raise HTTPException(409, str(exc)) from exc
        return {'removed': sum(len(g['sources']) for g in groups), 'renamed': len(groups), 'reconciliation_ids': audits}
    return router
