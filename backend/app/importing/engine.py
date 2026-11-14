"""Transactional, append-only provenance and conservative catalog merging."""
import hashlib
import base64
import json
from datetime import date
from sqlalchemy import select, text
from ..models import Computer, Manufacturer, Category, Configuration, Specification, Release, Sale, Review, Fact, Market, Source
from ..import_models import ImportJob, ImportRow, ImportClaim, ExternalIdentity, now
from ..admin import historical_date
from .normalize import Record, name_key, parse_payload, MAX_BYTES, MAX_ROWS
from .vocabulary import matching_specs, quantity_equal
from .identity import maker_key, computer_key
from .reconcile import reconciled_configuration, reconciled_release

TARGETS = {c.__name__: c for c in (Computer, Configuration, Specification, Release, Sale, Review, Fact)}
DATE_PRECISION = {'announcement_date': 'announcement_precision', 'release_date': 'release_precision',
                  'discontinuation_date': 'discontinuation_precision'}
BUNDLES = {'quantity': ('numeric_value', 'text_value', 'unit'),
           'price_bundle': ('price', 'currency', 'price_type'),
           'review_score': ('score', 'max_score'), 'sales_quantity': ('units_sold', 'estimated', 'metric_type')}


def serialize(value):
    return value.isoformat() if isinstance(value, date) else value


def identity_provider(provider, data):
    if provider in ('wikidata', 'retroflops'):
        return provider
    citation = data['source']
    namespace = citation.get('url') or (citation['title'] + '|' + (citation.get('author') or ''))
    return provider + ':' + hashlib.sha256(namespace.encode()).hexdigest()[:16]


def catalog_candidates(db, data, provider):
    if data.get('external_id'):
        identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.provider == identity_provider(provider, data),
                             ExternalIdentity.external_id == data['external_id']))
        if identity:
            # A stable identity also preserves an explicitly approved alias mapping.
            # Changed names/manufacturers still produce non-overwriting field conflicts.
            return [identity.computer_id], False
    makers = [m.id for m in db.scalars(select(Manufacturer)) if maker_key(m.name) == maker_key(data['manufacturer'])]
    candidates = [c.id for c in db.scalars(select(Computer).where(Computer.manufacturer_id.in_(makers)))
                  if computer_key(c.manufacturer.name, c.model_name) == computer_key(data['manufacturer'], data['model_name'])]
    return candidates, len(candidates) > 1


def stage(db, provider, filename, format, raw, records=None, options=None, retry_of=None):
    if len(raw) > MAX_BYTES:
        raise ValueError('Massimo 8 MB per importazione')
    if records is None:
        _, records = parse_payload(raw, format)
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_ROWS or not all(isinstance(r, dict) for r in records):
        raise ValueError('Serve un elenco di 1–1000 record adattati')
    # JSON allows exponent literals that Python may overflow to Infinity;
    # reject these before storing raw rows in PostgreSQL's strict JSON type.
    json.dumps(records, allow_nan=False)
    options = dict(options or {})
    options.pop('raw_payload_encoding', None)
    try:
        original_text = raw.decode('utf-8')
    except UnicodeDecodeError:
        if provider != '1000bit' or format not in ('html', 'htm'):
            raise ValueError('Il dataset richiede UTF-8.')
        original_text = base64.b64encode(raw).decode('ascii')
        options['raw_payload_encoding'] = 'base64'
    job = ImportJob(provider=provider, filename=filename, format=format,
                    checksum=hashlib.sha256(raw).hexdigest(), raw_payload=original_text,
                    request_options=options, retry_of=retry_of)
    db.add(job)
    db.flush()
    for position, original in enumerate(records, 1):
        row = ImportRow(job_id=job.id, position=position, raw=original)
        try:
            if isinstance(original.get('error'), str) and original['error']:
                raise ValueError(original['error'])
            data = Record.model_validate(original).model_dump(mode='json', exclude_none=True)
            candidates, ambiguous = catalog_candidates(db, data, provider)
            row.normalized = data
            row.candidates = candidates
            row.status = 'ambiguous' if ambiguous else 'ready'
            row.computer_id = candidates[0] if len(candidates) == 1 and not ambiguous else None
        except (ValueError, TypeError) as exc:
            row.status, row.error = 'invalid', str(exc)[:5000]
        db.add(row)
    db.commit()
    return job


def original_bytes(job):
    if job.request_options.get('raw_payload_encoding') == 'base64':
        return base64.b64decode(job.raw_payload, validate=True)
    return job.raw_payload.encode('utf-8')


def reference(db, model, name):
    identity = maker_key if model is Manufacturer else name_key
    rows = [x for x in db.scalars(select(model)) if identity(x.name) == identity(name)]
    if len(rows) > 1:
        raise ValueError(f'Riferimento ambiguo: {name}')
    if rows:
        return rows[0]
    value = model(name=name)
    db.add(value)
    db.flush()
    return value


def source(db, citation):
    conditions = [Source.title == citation['title'], Source.url == citation.get('url')]
    if not citation.get('url'):
        conditions.extend([Source.author == citation.get('author'), Source.publisher == citation.get('publisher')])
    found = db.scalar(select(Source).where(*conditions).order_by(Source.id))
    if found:
        return found
    found = Source(**{k: v for k, v in citation.items() if k != 'license'})
    for field in ('access_date', 'publication_date'):
        if isinstance(getattr(found, field), str):
            setattr(found, field, date.fromisoformat(getattr(found, field)))
    found.access_date = found.access_date or date.today()
    db.add(found)
    db.flush()
    return found


def attribute(db, row, target, field, incoming, citation, evidence=None, estimated=False):
    """Keep differing values staged as claims; fill only genuinely missing fields."""
    if incoming is None:
        return False
    s = source(db, citation)
    linked = False
    if hasattr(target, 'sources') and s not in target.sources:
        target.sources.append(s)
        linked = True
    previous = serialize(getattr(target, field))
    value = incoming
    precision = None
    if field.endswith('_date') or field in ('period_start', 'period_end'):
        value, precision = historical_date(incoming)
        incoming = serialize(value)
    precision_field = DATE_PRECISION.get(field)
    old_precision = getattr(target, precision_field) if precision_field else None
    missing = previous is None or (field=='description' and isinstance(previous,str) and not previous.strip())
    conflict = not missing and (previous != incoming or (precision_field and old_precision != precision))
    changed = missing
    if changed:
        setattr(target, field, value)
        if precision_field:
            setattr(target, precision_field, precision)
    db.flush()
    db.add(ImportClaim(row_id=row.id, computer_id=row.computer_id, source_id=s.id,
        entity=type(target).__name__, target_id=target.id, field=field,
        value={'value': incoming, **({'precision': precision} if precision_field else {})},
        previous={'value': previous, **({'precision': old_precision} if precision_field else {})},
        status='conflict' if conflict else 'pending', estimated=estimated,
        evidence='\n'.join(x for x in (evidence, ('Licenza: ' + citation['license']) if citation.get('license') else None) if x) or None))
    return changed or linked


def import_record(db, job, row):
    data = Record.model_validate(row.normalized).model_dump(mode='json', exclude_none=True)
    candidates, ambiguous = catalog_candidates(db, data, job.provider)
    c = db.get(Computer, row.computer_id) if row.computer_id else None
    if job.request_options.get('existing_only') and c is None:
        row.status, row.error = 'skipped', 'La scheda da arricchire è stata rimossa; nessun calcolatore creato.'
        return
    if c is None and ambiguous:
        row.status, row.candidates = 'ambiguous', candidates
        return
    if c is None and candidates:
        c = db.get(Computer, candidates[0])
    created = c is None
    maker = c.manufacturer if c is not None and maker_key(c.manufacturer.name) == maker_key(data['manufacturer']) else reference(db, Manufacturer, data['manufacturer'])
    if created:
        c = Computer(manufacturer=maker, model_name=data['model_name'])
        db.add(c)
        db.flush()
    row.computer_id = c.id
    changed = False
    root_source = data['source']
    root_estimate = data.get('estimated', False)

    def record_fields(target, values, fields, parent=None):
        nonlocal changed
        citation = values.get('source') or (parent or {}).get('source') or root_source
        estimate = values.get('estimated', False) or (parent or {}).get('estimated', False) or root_estimate
        evidence = values.get('evidence') or (parent or {}).get('evidence') or data.get('evidence')
        for field in fields:
            changed = attribute(db, row, target, field, values.get(field), citation, evidence, estimate) or changed

    def bundle(target, entry, field):
        nonlocal changed
        fields = BUNDLES[field]
        old = {key: getattr(target, key) for key in fields}
        value = {key: entry.get(key, old[key]) for key in fields}
        if all(v is None for v in value.values()):
            return
        conflict = any(old[key] is not None and old[key] != value[key] for key in fields)
        if not conflict:
            for key in fields:
                if old[key] is None and value[key] is not None:
                    setattr(target, key, value[key]); changed = True
        citation = entry.get('source') or root_source
        s = source(db, citation)
        if s not in target.sources:
            target.sources.append(s); changed = True
        db.add(ImportClaim(row_id=row.id, computer_id=c.id, source_id=s.id, entity=type(target).__name__, target_id=target.id,
            field=field, value=value, previous=old, status='conflict' if conflict else 'pending',
            estimated=entry.get('estimated', False) or root_estimate,
            evidence='\n'.join(x for x in (entry.get('evidence') or data.get('evidence'),
                 ('Licenza: ' + citation['license']) if citation.get('license') else None) if x) or None))

    model_name = c.model_name if computer_key(c.manufacturer.name, c.model_name) == computer_key(data['manufacturer'], data['model_name']) else data['model_name']
    record_fields(c, {**data, 'model_name': model_name, 'manufacturer_id': maker.id}, ('model_name', 'manufacturer_id', 'description', 'announcement_date'))
    for name in data.get('categories', []):
        cat = reference(db, Category, name)
        if cat not in c.categories:
            c.categories.append(cat)
            changed = True
        # Categories are sets, so a claim records the asserted membership.
        s = source(db, root_source)
        db.add(ImportClaim(row_id=row.id, computer_id=c.id, source_id=s.id, entity='Computer', target_id=c.id,
            field='category', value={'value': cat.id}, previous={'value': None}, status='pending', estimated=root_estimate,
            evidence=data.get('evidence')))
    for cfg in data.get('configurations', []):
        reconciled = reconciled_configuration(db, c.id, identity_provider(job.provider, data), data.get('external_id'), cfg['variant_name'])
        matches = [reconciled] if reconciled else [v for v in c.configurations if name_key(v.variant_name) == name_key(cfg['variant_name'])]
        if len(matches) > 1:
            raise ValueError('Configurazione ambigua')
        variant = matches[0] if matches else Configuration(variant_name=cfg['variant_name'])
        if not matches:
            c.configurations.append(variant)
            changed = True
        db.flush()
        record_fields(variant, {**cfg, 'variant_name': variant.variant_name} if reconciled else cfg, ('variant_name', 'description'))
        for spec in cfg.get('specifications', []):
            matches = matching_specs(variant.specifications, spec)
            if len(matches) > 1:
                raise ValueError('Specifiche ripetute: scegli configurazioni distinte prima di importare')
            if matches:
                target = matches[0]
                # Value and unit form one assertion: never fill a unit on a conflicting number.
                s_citation = spec.get('source') or cfg.get('source') or root_source
                s = source(db, s_citation)
                if s not in target.sources:
                    target.sources.append(s)
                    changed = True
                old = {k: getattr(target, k) for k in ('numeric_value', 'text_value', 'unit')}
                val = {k: spec.get(k) for k in old}
                db.add(ImportClaim(row_id=row.id, computer_id=c.id, source_id=s.id, entity='Specification', target_id=target.id,
                    field='quantity', value=val, previous=old, status='pending' if quantity_equal(target, val, old) else 'conflict',
                    estimated=spec.get('estimated', False) or cfg.get('estimated', False) or root_estimate,
                    evidence='\n'.join(x for x in (spec.get('evidence') or cfg.get('evidence') or data.get('evidence'),
                        ('Licenza: ' + s_citation['license']) if s_citation.get('license') else None) if x) or None))
            else:
                target = Specification(**{k: v for k, v in spec.items() if k not in ('source', 'evidence', 'estimated')})
                variant.specifications.append(target)
                changed = True
                db.flush()
                record_fields(target, spec, ('component_type', 'component_name', 'property_name', 'numeric_value', 'text_value', 'unit'), cfg)
    for collection, model, fields in (
        ('releases', Release, ('release_date', 'discontinuation_date', 'price', 'currency', 'price_type')),
        ('sales', Sale, ('period_start', 'period_end', 'units_sold', 'metric_type', 'estimated')),
        ('reviews', Review, ('publication', 'review_date', 'score', 'max_score', 'summary')),
        ('facts', Fact, ('fact_type', 'statement', 'reference_date')),
    ):
        for entry in data.get(collection, []):
            existing = list(getattr(c, collection))
            if model in (Release, Sale):
                market = reference(db, Market, entry['market'])
                existing = [r for r in existing if r.market_id == market.id]
                original_release = reconciled_release(db,c.id,identity_provider(job.provider,data),data.get('external_id'),
                    market.id,serialize(historical_date(entry.get('release_date'))[0])) if model is Release else None
                # An undated price must not inherit a launch date from another
                # source merely because the catalog has one release in this market.
                if model is Release and original_release is None and entry.get('price') is not None and not entry.get('release_date'):
                    existing = [r for r in existing if r.release_date is None]
                if model is Sale:
                    existing = [r for r in existing if serialize(r.period_start) == entry.get('period_start') and serialize(r.period_end) == entry.get('period_end') and r.metric_type == entry.get('metric_type', 'units_sold')]
                elif original_release is not None:
                    existing=[original_release]
                elif len(existing) > 1 or sum(name_key(r['market']) == name_key(entry['market']) for r in data.get('releases', [])) > 1:
                    existing = [r for r in existing if serialize(r.release_date) == serialize(historical_date(entry.get('release_date'))[0])]
            elif model is Review:
                existing = [r for r in existing if name_key(r.publication) == name_key(entry['publication']) and serialize(r.review_date) == entry.get('review_date')]
            else:
                existing = [r for r in existing if r.fact_type == entry['fact_type'] and r.statement == entry['statement']]
            if len(existing) > 1:
                raise ValueError(f'{collection}: corrispondenza ambigua')
            if existing:
                target = existing[0]
            else:
                initial = {k: entry[k] for k in fields if k in entry and not k.endswith('_date') and k not in ('period_start', 'period_end')}
                if model in (Release, Sale):
                    initial['market_id'] = market.id
                target = model(**initial)
                getattr(c, collection).append(target)
                changed = True
                db.flush()
            grouped = ('price_bundle' if model is Release else 'review_score' if model is Review else 'sales_quantity' if model is Sale else None)
            if grouped:
                bundle(target, entry, grouped)
            remaining_fields = tuple(k for k in fields if not grouped or k not in BUNDLES[grouped])
            if model in (Release, Sale):
                record_fields(target, {**entry, 'market_id': market.id}, ('market_id',))
            record_fields(target, entry, remaining_fields)
    if data.get('external_id'):
        namespace = identity_provider(job.provider, data)
        identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.provider == namespace, ExternalIdentity.external_id == data['external_id']))
        if identity and identity.computer_id != c.id:
            raise ValueError('Identità esterna già associata a un altro calcolatore')
        if not identity:
            db.add(ExternalIdentity(provider=namespace, external_id=data['external_id'], computer_id=c.id))
    row.status = 'imported' if created else 'updated' if changed else 'unchanged'


def apply_job(db, job_id):
    # Serialize import writers across jobs on PostgreSQL; SQLite serializes the first write.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
    if job.status in ('completed', 'partial'):
        return job
    if job.status != 'ready':
        raise ValueError('Importazione non pronta: usa Riprova')
    job.status = 'running'
    db.flush()
    for row in job.rows:
        if row.status != 'ready':
            continue
        try:
            with db.begin_nested():
                import_record(db, job, row)
                db.flush()
        except Exception as exc:
            # Preserve a retryable row and all previously successful rows, without raw DB diagnostics.
            row.status = 'failed'
            row.error = str(exc)[:1000] if isinstance(exc, ValueError) else 'Errore di integrità: controlla dati e corrispondenze; riprova.'
    job.status = 'partial' if any(r.status in ('failed', 'invalid', 'ambiguous') for r in job.rows) else 'completed'
    db.commit()
    return job


def review_claim(db, claim, decision, note):
    if claim.status in ('verified', 'rejected'):
        raise ValueError('Decisione già registrata; crea una nuova importazione per una nuova revisione')
    model = TARGETS[claim.entity]
    target = db.scalar(select(model).where(model.id == claim.target_id).with_for_update())
    if target is None or claim.computer_id is None:
        raise ValueError('Elemento originale non più disponibile')
    if decision == 'accept':
        if claim.field == 'category':
            category = db.get(Category, claim.value['value'])
            if category is None:
                raise ValueError('Categoria non più disponibile')
            if category not in target.categories:
                target.categories.append(category)
        else:
            current = {k: getattr(target, k) for k in BUNDLES[claim.field]} if claim.field in BUNDLES else {'value': serialize(getattr(target, claim.field))}
            if claim.field in DATE_PRECISION:
                current['precision'] = getattr(target, DATE_PRECISION[claim.field])
            expected = claim.previous if claim.status == 'conflict' else claim.value
            same = quantity_equal(target, current, expected) if claim.field == 'quantity' else current == expected
            if not same:
                raise ValueError('Il dato è cambiato dopo l’importazione: riesamina con una nuova anteprima')
            if claim.field in BUNDLES:
                for field, value in claim.value.items():
                    setattr(target, field, value)
            else:
                value = claim.value['value']
                if claim.field.endswith('_date') or claim.field in ('period_start', 'period_end'):
                    value = date.fromisoformat(value) if value else None
                setattr(target, claim.field, value)
                if claim.field in DATE_PRECISION:
                    setattr(target, DATE_PRECISION[claim.field], claim.value.get('precision'))
        db.flush()
    claim.status = 'verified' if decision == 'accept' else 'rejected'
    claim.review_note, claim.reviewed_at = note, now()
    db.commit()
