"""Reviewed reconciliation of known aliases, preserving children and original audit."""
import hashlib
import json
from datetime import date, datetime
from collections import defaultdict
from sqlalchemy import select, text, func
from ..models import (Computer, Manufacturer, Configuration, Specification, Release, Sale, Review, Fact,
                      ComputerImage, Source, computer_source, computer_category, spec_source,
                      release_source, sale_source, review_source, fact_source)
from ..import_models import ImportRow, ImportClaim, ExternalIdentity, CatalogReconciliation, ArchiveReset
from .identity import computer_key, maker_key
from .normalize import name_key
from ..photo_jobs import PhotoItem


def value(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def rows(db, table, condition=None):
    query = select(table)
    if condition is not None:
        query = query.where(condition)
    return [{k: value(v) for k, v in row._mapping.items()} for row in db.execute(query.order_by(*table.primary_key.columns))]


def snapshot(db, entity, source, target):
    ids = [source.id, target.id]
    result = {entity: rows(db, type(source).__table__, type(source).id.in_(ids))}
    if entity == 'manufacturer':
        result['computers'] = rows(db, Computer.__table__, Computer.manufacturer_id.in_(ids))
        result['claims'] = [r for r in rows(db, ImportClaim.__table__, ImportClaim.field == 'manufacturer_id')
                            if any(r[key].get('value') in ids for key in ('value', 'previous'))]
        return result
    tables = ((Configuration, 'computer_id'), (Release, 'computer_id'), (Sale, 'computer_id'),
              (Review, 'computer_id'), (Fact, 'computer_id'), (ComputerImage, 'computer_id'),
              (ImportClaim, 'computer_id'), (ExternalIdentity, 'computer_id'))
    for model, field in tables:
        result[model.__tablename__] = rows(db, model.__table__, getattr(model, field).in_(ids))
    result['commons_photo_items'] = rows(db, PhotoItem.__table__, PhotoItem.computer_id.in_(ids))
    config_ids = [r['id'] for r in result['configurations']]
    result['specifications'] = rows(db, Specification.__table__, Specification.configuration_id.in_(config_ids))
    result['computer_categories'] = rows(db, computer_category, computer_category.c.computer_id.in_(ids))
    for table, child_ids in ((computer_source, ids), (spec_source, [r['id'] for r in result['specifications']]),
                             (release_source, [r['id'] for r in result['releases']]),
                             (sale_source, [r['id'] for r in result['sales']]),
                             (review_source, [r['id'] for r in result['reviews']]),
                             (fact_source, [r['id'] for r in result['facts']])):
        result[table.name] = rows(db, table, table.c.target_id.in_(child_ids))
    # Scan only small mapping fields; loading every raw/normalized row for
    # each pair makes large regional batches needlessly expensive.
    related_ids = [r.id for r in db.execute(select(ImportRow.id,ImportRow.computer_id,ImportRow.candidates))
                   if r.computer_id in ids or any(i in ids for i in r.candidates)]
    result['import_rows'] = rows(db,ImportRow.__table__,ImportRow.id.in_(related_ids))
    source_ids = {r['source_id'] for table in (computer_source, spec_source, release_source, sale_source, review_source, fact_source)
                  for r in result[table.name]}
    result['sources'] = rows(db, Source.__table__, Source.id.in_(source_ids))
    result['manufacturers'] = rows(db, Manufacturer.__table__, Manufacturer.id.in_([source.manufacturer_id, target.manufacturer_id]))
    return result


def prepare(db, entity, source_id, target_id, lock=False):
    if source_id == target_id:
        raise ValueError('Scegli due schede diverse')
    model = Computer if entity == 'computer' else Manufacturer
    query = select(model).where(model.id.in_([source_id, target_id])).order_by(model.id)
    if lock:
        if db.bind.dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
        query = query.with_for_update()
    items = {item.id: item for item in db.scalars(query)}
    if len(items) != 2:
        raise ValueError('Una delle schede non è più disponibile: aggiorna i duplicati')
    source, target = items[source_id], items[target_id]
    identity = (lambda c: computer_key(c.manufacturer.name, c.model_name)) if entity == 'computer' else (lambda m: maker_key(m.name))
    if identity(source) != identity(target):
        raise ValueError('Queste schede non sono alias riconosciuti dello stesso elemento. Famiglie e modelli specifici restano separati.')
    original = snapshot(db, entity, source, target)
    token = hashlib.sha256(json.dumps(original, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    fields = ('model_name', 'description', 'announcement_date', 'announcement_precision', 'image_url') if entity == 'computer' else ('name', 'country', 'founded', 'website')
    differences = [{'field': field, 'source': value(getattr(source, field)), 'target': value(getattr(target, field))}
                   for field in fields if getattr(source, field) != getattr(target, field)]
    counts = ({key: len(original[key]) for key in ('configurations', 'specifications', 'releases', 'computer_images', 'sources')}
              if entity == 'computer' else {'computers': len(original['computers'])})
    return source, target, original, {'entity': entity, 'source_id': source_id, 'target_id': target_id, 'token': token,
        'source_label': source.model_name if entity == 'computer' else source.name,
        'target_label': target.model_name if entity == 'computer' else target.name,
        'differences': differences, 'counts': counts}


def apply(db, entity, source_id, target_id, token, note, commit=True):
    source, target, original, preview = prepare(db, entity, source_id, target_id, lock=True)
    if token != preview['token']:
        raise ValueError('I dati sono cambiati: prepara una nuova anteprima di riconciliazione')
    if entity == 'computer':
        for field in ('description', 'announcement_date', 'image_url'):
            if getattr(target, field) is None:
                setattr(target, field, getattr(source, field))
                if field == 'announcement_date':
                    target.announcement_precision = source.announcement_precision
        if source.image_url and target.image_url != source.image_url:
            target.images.append(ComputerImage(remote_url=source.image_url, caption='Immagine della scheda riconciliata'))
        for category in source.categories:
            if category not in target.categories:
                target.categories.append(category)
        for citation in source.sources:
            if citation not in target.sources:
                target.sources.append(citation)
        names = {c.variant_name for c in target.configurations}
        for config in list(source.configurations):
            if config.variant_name in names:
                suffix = f' [scheda {source_id}, config {config.id}]'
                config.variant_name = config.variant_name[:140-len(suffix)] + suffix
                if config.variant_name in names:
                    raise ValueError('Nome di configurazione già presente: rinomina prima la configurazione')
            names.add(config.variant_name)
            config.computer = target
        primary = any(image.is_primary for image in target.images)
        for image in list(source.images):
            if primary:
                image.is_primary = False
            primary = primary or image.is_primary
            image.computer = target
        for relationship in ('releases', 'sales', 'reviews', 'facts'):
            for child in list(getattr(source, relationship)):
                child.computer = target
        for row in db.scalars(select(ImportRow).where(ImportRow.id.in_([r['id'] for r in original['import_rows']]))):
            if row.computer_id == source_id:
                row.computer_id = target_id
            if source_id in row.candidates:
                row.candidates = list(dict.fromkeys(target_id if i == source_id else i for i in row.candidates))
        for identity in db.scalars(select(ExternalIdentity).where(ExternalIdentity.computer_id == source_id)):
            identity.computer_id = target_id
        for item in db.scalars(select(PhotoItem).where(PhotoItem.computer_id == source_id)):
            item.computer_id = target_id
            if item.status == 'pending':
                item.model_name = target.model_name
                item.query = target.model_name.strip()[:90]
        for claim in db.scalars(select(ImportClaim).where(ImportClaim.computer_id == source_id)):
            claim.computer_id = target_id
            if claim.entity == 'Computer' and claim.target_id == source_id:
                claim.target_id = target_id
    else:
        for field in ('country', 'founded', 'website'):
            if getattr(target, field) is None:
                setattr(target, field, getattr(source, field))
        for computer in db.scalars(select(Computer).where(Computer.manufacturer_id == source_id)):
            computer.manufacturer = target
        for claim in db.scalars(select(ImportClaim).where(ImportClaim.field == 'manufacturer_id')):
            for field in ('value', 'previous'):
                bundle = getattr(claim, field)
                if bundle.get('value') == source_id:
                    setattr(claim, field, {**bundle, 'value': target_id})
    db.flush()
    if entity == 'computer':
        existing = {link['source_id'] for link in original['computer_sources'] if link['target_id'] == target_id}
        for link in original['computer_sources']:
            if link['target_id'] == source_id and link['source_id'] not in existing:
                db.execute(computer_source.update().where(computer_source.c.target_id == target_id,
                    computer_source.c.source_id == link['source_id']).values(evidence=link['evidence'],
                    verification_status=link['verification_status']))
    audit = CatalogReconciliation(entity=entity, source_id=source_id, target_id=target_id, note=note, snapshot=original)
    db.add(audit)
    db.delete(source)
    if commit: db.commit()
    else: db.flush()
    return {'reconciliation_id': audit.id, 'target_id': target_id, 'entity': entity}


def duplicate_groups(db):
    result = []
    for entity, model in (('computer', Computer), ('manufacturer', Manufacturer)):
        groups = defaultdict(list)
        for item in db.scalars(select(model).order_by(model.id)):
            key = computer_key(item.manufacturer.name, item.model_name) if entity == 'computer' else maker_key(item.name)
            groups[key].append({'id': item.id, 'label': f'{item.manufacturer.name} · {item.model_name}' if entity == 'computer' else item.name})
        result.extend({'entity': entity, 'items': items} for items in groups.values() if len(items) > 1)
    return result


def original_identity(db,provider,external_id):
    """Earliest pre-merge owner, cached per Session and invalidated by new audits/resets."""
    if not external_id:return None
    cutoff = db.scalar(select(ArchiveReset.reconciliation_cutoff).order_by(ArchiveReset.id.desc()).limit(1)) or 0
    latest=db.scalar(select(func.max(CatalogReconciliation.id))) or 0
    marker=(cutoff,latest)
    cached=db.info.get('hhe_original_identities')
    if not cached or cached[0]!=marker:
        index={}
        for audit in db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity=='computer',CatalogReconciliation.id>cutoff).order_by(CatalogReconciliation.id)):
            for identity in audit.snapshot.get('import_identities',[]):
                index.setdefault((identity['provider'],identity['external_id']),(identity['computer_id'],audit.snapshot))
        cached=(marker,index);db.info['hhe_original_identities']=cached
    return cached[1].get((provider,external_id))


def reconciled_configuration(db, computer_id, provider, external_id, variant_name):
    """Follow immutable original IDs, including configurations renamed on a collision."""
    origin=original_identity(db,provider,external_id)
    if not origin:return None
    owner,original=origin
    candidates=[cfg for cfg in original['configurations'] if cfg['computer_id']==owner and name_key(cfg['variant_name'])==name_key(variant_name)]
    if len(candidates)>1:raise ValueError('Configurazioni originali ambigue: controlla la riconciliazione')
    if candidates:
        config=db.get(Configuration,candidates[0]['id'])
        if config is None or config.computer_id!=computer_id:
            raise ValueError('Configurazione riconciliata non più disponibile: controlla scheda e corrispondenza')
        return config


def reconciled_release(db,computer_id,provider,external_id,market_id,release_date):
    origin=original_identity(db,provider,external_id)
    if not origin:return None
    owner,original=origin
    candidates=[r for r in original['releases'] if r['computer_id']==owner and r['market_id']==market_id and r['release_date']==release_date]
    if len(candidates)>1:raise ValueError('Commercializzazioni originali ambigue: controlla la riconciliazione')
    if candidates:
        release=db.get(Release,candidates[0]['id'])
        if release is None or release.computer_id!=computer_id:
            raise ValueError('Commercializzazione riconciliata non più disponibile: controlla scheda e corrispondenza')
        return release
