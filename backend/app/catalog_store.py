"""Shared catalog resolver and maintenance of legacy or physically clean data.

The queue is maintained by database triggers, not frontend behavior. API
maintenance drains it before/after requests and at startup. CLI/SQL imports
remain safe: a dirty snapshot is never returned as current, even before drain.
After physical cleanup the primary tables are authoritative, snapshot copies
stay empty, and maintenance normalizes only the changed primary rows.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from sqlalchemy import select, delete, func, inspect, text
from sqlalchemy.orm import Session, object_session, selectinload
from .models import (Computer, Configuration, Specification, Release, CatalogSnapshot,
                     CatalogMetric, CatalogDirty, catalog_metric_assertions, catalog_metric_sources)
from .catalog_schema import VERSION, ensure_schema
from .catalog_memory import memory_specifications, comparisons, view
from .catalog_display import configuration_displays, specification_display
from .importing.vocabulary import spec_values, normalize_spec
from .source_policy import is_internal_source
from .technical_display import technical_sheets
from .release_display import release_summaries
from .variant_context import annotate

EAGER = (selectinload(Computer.manufacturer),
         selectinload(Computer.configurations).selectinload(Configuration.specifications).selectinload(Specification.sources),
         selectinload(Computer.releases).selectinload(Release.market),
         selectinload(Computer.releases).selectinload(Release.sources))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def datefmt(value, precision):
    return value.isoformat()[:{'year': 4, 'month': 7}.get(precision, 10)] if value else None


def source_data(source):
    return {'id': source.id, 'title': source.title, 'url': source.url, 'author': source.author,
            'publisher': source.publisher, 'source_type': source.source_type,
            'publication_date': source.publication_date.isoformat() if source.publication_date else None,
            'access_date': source.access_date.isoformat() if source.access_date else None}


def sources(items):
    return [source_data(s) for s in sorted(items, key=lambda s: s.id) if not is_internal_source(s)]


def specification_data(spec):
    normalized = normalize_spec(spec_values(spec))
    result = {'id': spec.id, **spec_values(spec), 'normalized': normalized,
            'display': specification_display(normalized), 'sources': sources(spec.sources)}
    details = spec.catalog_details or {}
    if details.get('clean'):
        result['catalog_clean'] = True
        if normalized['component_type'] == 'RAM':
            from .catalog_memory import entry, memory_text
            item = entry({**normalized, **result['display']})
            entries=[item] if item and details['resolution_state'] != 'unknown' else []
            result.update(catalog_metric=details['metric'], resolution_state=details['resolution_state'],
                          memory_values=entries,
                          memory_notes=details.get('notes', []), specification_ids=[spec.id])
            result['normalized']={**normalized,'numeric_value':None,'text_value':memory_text(entries) or 'Non documentata','unit':None}
    return result


def raw_payload(computer):
    displays = configuration_displays(computer.configurations, computer.model_name)
    payload = {'configurations': [{'id': c.id, 'variant_name': c.variant_name,
                  'description': c.description, **displays[c.id], **(c.catalog_details or {}),
                  'specifications': [specification_data(s) for s in sorted(c.specifications, key=lambda s: s.id)]}
                  for c in sorted(computer.configurations, key=lambda c: c.id)],
               'releases': [{'id': r.id, 'market': r.market.name,
                  'release_date': datefmt(r.release_date, r.release_precision),
                  'discontinuation_date': datefmt(r.discontinuation_date, r.discontinuation_precision),
                  'price': r.price, 'currency': r.currency, 'price_type': r.price_type, 'sources': sources(r.sources), **(r.catalog_details or {})}
                  for r in sorted(computer.releases, key=lambda r: r.id)]}
    annotate(computer, payload)
    from .commercial_dates import annotate as date_context
    date_context(computer,payload)
    db = object_session(computer)
    if db is not None:
        from .models import spec_source
        payload['provenance'] = [dict(row._mapping) for row in db.execute(select(spec_source)
            .join(Specification, Specification.id == spec_source.c.target_id)
            .join(Configuration, Configuration.id == Specification.configuration_id)
            .where(Configuration.computer_id == computer.id)
            .order_by(spec_source.c.target_id, spec_source.c.source_id))]
    return payload


def consolidate(payload, model_name):
    sheets = technical_sheets(payload['configurations'], model_name)
    for sheet in sheets:
        sheet['specifications'] = memory_specifications(sheet['specifications'])
        for spec in sheet['specifications']:
            ids = set(spec.get('specification_ids', [spec['id']]))
            states = {row['verification_status'] for row in payload.get('provenance', []) if row['target_id'] in ids}
            spec['verification_status'] = ('disputed' if states & {'conflict', 'rejected'} else
                'verified' if states == {'verified'} else 'pending')
    return {'configurations': sheets, 'releases': release_summaries(payload['releases']),
            'comparison': {'all': comparisons(sheets),
                'configurations': {str(c['id']): comparisons([c]) for c in sheets}}}


def fingerprint(computer, payload):
    return digest({'version': VERSION, 'model_name': computer.model_name,
                   'manufacturer': computer.manufacturer.name, 'raw': payload})


def resolved(computer, payload=None):
    """Reads never write; a changed/old/missing snapshot uses the same resolver."""
    payload = raw_payload(computer) if payload is None else payload
    checksum = fingerprint(computer, payload)
    db = object_session(computer)
    if db is not None:
        from .catalog_cleanup import physical_mode
        if physical_mode(db):
            return consolidate(payload, computer.model_name), {'version': VERSION, 'input_sha256': checksum,
                'persisted': True, 'storage': 'primary_tables', 'rebuilt_at': None}
    snapshot = None
    if db is not None and inspect(db.connection()).has_table('catalog_snapshots'):
        # Check the fingerprint as well as the queue: snapshots restored from
        # older versions or external tools without triggers cannot go stale.
        snapshot = db.get(CatalogSnapshot, computer.id)
    current = snapshot is not None and snapshot.version == VERSION and snapshot.input_sha256 == checksum
    data = deepcopy(snapshot.payload) if current else consolidate(payload, computer.model_name)
    return data, {'version': VERSION, 'input_sha256': checksum, 'persisted': current,
                  'rebuilt_at': snapshot.rebuilt_at.isoformat() if current else None}


def persist(db, computer, *, force=False):
    raw = raw_payload(computer); checksum = fingerprint(computer, raw)
    old = db.get(CatalogSnapshot, computer.id)
    if not force and old is not None and old.version == VERSION and old.input_sha256 == checksum:
        return False
    data = consolidate(raw, computer.model_name)
    if old is None:
        old = CatalogSnapshot(computer_id=computer.id)
        db.add(old)
    old.version, old.input_sha256, old.payload = VERSION, checksum, data
    old.rebuilt_at = datetime.now(timezone.utc)
    db.flush()
    db.execute(delete(CatalogMetric).where(CatalogMetric.computer_id == computer.id))
    metrics, assertions, source_links = [], [], []
    # Include internal provenance in the relational links, without publishing
    # excluded bibliography entries in reader payloads.
    from .models import spec_source
    provenance = {}
    for sid, srcid in db.execute(select(spec_source.c.target_id, spec_source.c.source_id)
            .join(Specification, Specification.id == spec_source.c.target_id)
            .join(Configuration, Configuration.id == Specification.configuration_id)
            .where(Configuration.computer_id == computer.id)):
        provenance.setdefault(sid, set()).add(srcid)
    for cfg in data['configurations']:
        for index, spec in enumerate(cfg['specifications']):
            values = view(spec)
            metric = spec.get('catalog_metric') or values['component_type'] + '.' + values['property_name']
            key = digest([computer.id, cfg['id'], metric, index])
            quantities = spec.get('memory_values', spec.get('display_values', []))
            number, unit = values.get('numeric_value'), values.get('unit')
            # One exact scalar can be queried numerically. A range/list or
            # named bank never masquerades as one installed total.
            if 'memory_values' in spec:
                if len(quantities) == 1 and quantities[0]['number'] is not None and not quantities[0]['role'] and not quantities[0]['qualifier']:
                    number, unit = quantities[0]['number'], quantities[0]['unit'] or None
                    if quantities[0]['bytes'] is not None:
                        number, unit = Decimal(str(quantities[0]['bytes'])) / Decimal(1024), 'KiB'
                else:
                    number, unit = None, None
            metrics.append({'key': key, 'computer_id': computer.id, 'sheet_id': cfg['id'], 'metric': metric,
                'component_type': values['component_type'], 'component_name': values.get('component_name'),
                'property_name': values['property_name'], 'numeric_value': Decimal(str(number)) if number is not None else None,
                'text_value': values.get('text_value'), 'unit': unit,
                'resolution_state': spec.get('resolution_state', 'reported'), 'verification_status': spec['verification_status'], 'quantities': quantities,
                'notes': spec.get('memory_notes', []), 'configuration_ids': cfg.get('configuration_ids', [cfg['id']])})
            ids = set(spec.get('specification_ids', [spec['id']]))
            assertions.extend({'metric_key': key, 'specification_id': sid} for sid in sorted(ids))
            source_links.extend({'metric_key': key, 'source_id': srcid} for srcid in sorted({source for sid in ids for source in provenance.get(sid, set())}))
    if metrics:
        db.execute(CatalogMetric.__table__.insert(), metrics)
    if assertions:
        db.execute(catalog_metric_assertions.insert(), assertions)
    if source_links:
        db.execute(catalog_metric_sources.insert(), source_links)
    return True


def refresh_pending(db, *, commit=True, force=False, locked=False):
    """Drain atomically in lock order shared with catalog edits/imports.

    Queue generations and row locks ensure a concurrent writer's invalidation
    cannot be lost. A failed rebuild leaves both the old data and queue intact.
    """
    if db.scalar(select(CatalogDirty.computer_id).limit(1)) is None:
        return {'updated': 0, 'processed': 0}
    from .catalog_cleanup import physical_mode, refresh_clean
    if physical_mode(db):
        return refresh_clean(db, commit=commit, locked=locked)
    from .admin import catalog_lock
    if not locked:
        catalog_lock(db)
    updated = processed = 0
    while True:
        stmt = select(CatalogDirty).order_by(CatalogDirty.computer_id).limit(100)
        if db.bind.dialect.name == 'postgresql':
            stmt = stmt.with_for_update()
        pending = list(db.scalars(stmt))
        if not pending:
            break
        ids = [row.computer_id for row in pending]
        computers = list(db.scalars(select(Computer).where(Computer.id.in_(ids)).options(*EAGER).execution_options(populate_existing=True)))
        for computer in computers:
            updated += persist(db, computer, force=force)
        for row in pending:
            db.execute(delete(CatalogDirty).where(CatalogDirty.computer_id == row.computer_id, CatalogDirty.generation == row.generation))
        processed += len(pending)
    if commit:
        db.commit()
    return {'updated': updated, 'processed': processed}


def status(db):
    from .catalog_cleanup import physical_mode
    count = db.scalar(select(func.count()).select_from(Computer))
    if physical_mode(db):
        return {'version': VERSION, 'computers': count, 'snapshots': count,
            'metrics': db.scalar(select(func.count()).select_from(Specification)),
            'pending': db.scalar(select(func.count()).select_from(CatalogDirty)), 'storage': 'primary_tables'}
    return {'version': VERSION, 'computers': count,
            'snapshots': db.scalar(select(func.count()).select_from(CatalogSnapshot)),
            'metrics': db.scalar(select(func.count()).select_from(CatalogMetric)),
            'pending': db.scalar(select(func.count()).select_from(CatalogDirty))}


def rebuild(db):
    # Operational repair as well as backfill: do not trust derived rows that an
    # external tool might have changed independently of their original inputs.
    from .admin import catalog_lock
    catalog_lock(db)
    db.execute(text('''INSERT INTO catalog_dirty(computer_id,generation)
        SELECT id,1 FROM computers WHERE true ON CONFLICT(computer_id)
        DO UPDATE SET generation=catalog_dirty.generation+1'''))
    return refresh_pending(db, force=True, locked=True)
