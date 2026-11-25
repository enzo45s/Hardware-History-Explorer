"""Explicit, offline revision of the two existing cards requested by the user.

No computer creation, live downloads, startup hook or changes to existing offers.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..admin import catalog_lock
from ..models import Computer, Category, ComputerImage, spec_source
from ..import_models import CatalogReconciliation, ImportClaim
from ..catalog_identity import replaceable
from .identity import computer_key
from .normalize import Record, Spec, Citation
from .vocabulary import spec_values
from .engine import stage, apply_job, source, reference, serialize
from .dec_research import verified_spec, verified_field

PACKAGE = Path(__file__).parent / 'data/earthstation-mistrum-v1.json'
ENTITY = 'targeted_research'
TARGETS = {('Alloy', 'EarthStation-I'), ('Amaterske RADIO', 'Mistrum')}
FIELDS = ('component_type', 'component_name', 'property_name', 'numeric_value', 'text_value', 'unit')


def load(path=PACKAGE):
    raw = Path(path).read_bytes(); data = json.loads(raw)
    if {(r['manufacturer'], r['model_name']) for r in data['records']} != TARGETS or len(data['records']) != 2:
        raise ValueError('Il pacchetto deve riguardare soltanto EarthStation-I e Mistrum.')
    for row in data['records']:
        Record.model_validate(row)
        if len(row['configurations']) != 1 or any(row.get(k) for k in ('releases', 'sales', 'reviews', 'announcement_date')):
            raise ValueError('Il pacchetto non deve creare configurazioni multiple o offerte.')
        seen = set()
        for spec in row['configurations'][0]['specifications']:
            key = tuple(spec.get(k) for k in FIELDS[:3])
            if key in seen or not spec.get('source', {}).get('url') or not spec.get('evidence'):
                raise ValueError('Specifica duplicata o senza fonte/evidenza.')
            seen.add(key)
    for rule in data['corrections']:
        Spec.model_validate(rule['before']); Citation.model_validate(rule['source'])
        if rule['after'] is not None: Spec.model_validate(rule['after'])
        if not rule.get('evidence'): raise ValueError('Rettifica senza evidenza.')
    from ..main import ImageLinkInput
    for photos in data['photos'].values():
        for image in photos:
            if not image.get('permission_basis'): raise ValueError('Fotografia senza condizioni di utilizzo.')
            ImageLinkInput.model_validate({k: v for k, v in image.items() if k != 'permission_basis'})
    return data, hashlib.sha256(raw).hexdigest()


def prepare(db, path=PACKAGE):
    data, checksum = load(path); index = {}
    for c in db.scalars(select(Computer).options(selectinload(Computer.manufacturer))):
        index.setdefault(computer_key(c.manufacturer.name, c.model_name), []).append(c)
    selected = []; skipped = []
    for record in data['records']:
        matches = index.get(computer_key(record['manufacturer'], record['model_name']), [])
        if len(matches) != 1:
            skipped.append({'model_name': record['model_name'], 'reason': 'Scheda assente o ambigua; nessun calcolatore creato.'}); continue
        c = matches[0]
        if len(c.configurations) > 1:
            skipped.append({'model_name': record['model_name'], 'reason': 'Configurazioni sostanziali multiple: revisione manuale richiesta.'}); continue
        selected.append((record, c))
    return data, checksum, selected, skipped


def preview(db, path=PACKAGE):
    data, checksum, selected, skipped = prepare(db, path)
    return {'version': data['version'], 'checksum': checksum,
            'existing_models': [{'id': c.id, 'manufacturer': c.manufacturer.name, 'model_name': c.model_name} for _, c in selected],
            'technical_assertions': sum(len(r['configurations'][0]['specifications']) for r, _ in selected),
            'photos_proposed': sum(len(data['photos'][r['model_name']]) for r, _ in selected),
            'skipped': skipped, 'research': data['research']}


def apply(db, path=PACKAGE):
    try:
        return _apply(db, path)
    except Exception:
        db.rollback(); raise


def _apply(db, path):
    catalog_lock(db)
    data, checksum, selected, skipped = prepare(db, path)
    audits = db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity == ENTITY)).all()
    if any(a.snapshot.get('checksum') == checksum for a in audits):
        db.rollback(); return {'version': data['version'], 'already_applied': True, 'updated': 0}
    report = {'version': data['version'], 'checksum': checksum, 'updated': 0,
              'specifications_corrected': 0, 'specifications_retired': 0, 'descriptions_updated': 0,
              'curated_descriptions_preserved': 0, 'photos_added': 0, 'wrong_automatic_photos_removed': 0,
              'categories_corrected': 0, 'skipped': skipped, 'protected': []}
    if not selected:
        db.rollback(); return report
    changes = []; photo_changes = []; category_changes = []
    for record, c in selected:
        for rule in data['corrections']:
            if rule['model_name'] != record['model_name']: continue
            matches = [s for cfg in c.configurations for s in cfg.specifications if spec_values(s) == rule['before']]
            if len(matches) != 1: continue
            spec = matches[0]
            if verified_spec(db, spec):
                report['protected'].append({'model_name': c.model_name, 'property': spec.property_name}); continue
            changes.append({'computer_id': c.id, 'specification_id': spec.id, 'before': spec_values(spec),
                            'before_details': deepcopy(spec.catalog_details), 'before_sources':
                            [dict(v._mapping) for v in db.execute(select(spec_source).where(spec_source.c.target_id == spec.id))],
                            'after': rule['after'], 'source': rule['source'], 'evidence': rule['evidence']})
            citation = source(db, rule['source'])
            if citation not in c.sources: c.sources.append(citation)
            if rule['after'] is None:
                spec.configuration.specifications.remove(spec); report['specifications_retired'] += 1
            else:
                for field in FIELDS: setattr(spec, field, rule['after'].get(field))
                spec.catalog_details = {}
                if citation not in spec.sources: spec.sources.append(citation)
                report['specifications_corrected'] += 1
        for rule in data.get('category_corrections', []):
            if rule['model_name'] != record['model_name'] or sorted(cat.name for cat in c.categories) != sorted(rule['before']): continue
            if verified_field(db, c.id, 'category'):
                report['protected'].append({'model_name': c.model_name, 'property': 'Categoria'}); continue
            old = [cat.id for cat in c.categories]
            c.categories = [reference(db, Category, name) for name in rule['after']]
            category_changes.append({'computer_id': c.id, 'before': old, **rule})
            report['categories_corrected'] += 1
    db.flush()
    from ..catalog_store import refresh_pending
    refresh_pending(db, commit=False, locked=True)
    records = []; old_text = {}
    for record, c in selected:
        incoming = deepcopy(record)
        incoming.update(manufacturer=c.manufacturer.name, model_name=c.model_name)
        if c.configurations: incoming['configurations'][0]['variant_name'] = c.configurations[0].variant_name
        old_text[c.id] = c.description; records.append(incoming)
    job = stage(db, 'manual', Path(path).name, 'json', Path(path).read_bytes(), records=records,
                options={'upload': True, 'existing_only': True, 'targeted_research': data['version']}, commit=False)
    for row, (_, c) in zip(job.rows, selected):
        row.computer_id = c.id; row.candidates = [c.id]; row.status = 'ready'
    apply_job(db, job.id, commit=False)
    if any(row.status not in ('updated', 'unchanged') for row in job.rows):
        raise ValueError('Aggiornamento non completato integralmente; tutte le modifiche annullate.')
    for row, (record, c) in zip(job.rows, selected):
        # The original record, field claims and source links remain available.
        incoming = row.normalized['description']; before = old_text[c.id]
        if before != incoming:
            if replaceable(c.model_name, c.manufacturer.name, before) and not verified_field(db, c.id, 'description'):
                c.description = incoming
                for claim in row.claims:
                    if claim.entity == 'Computer' and claim.field == 'description': claim.status = 'pending'
                report['descriptions_updated'] += 1
            else: report['curated_descriptions_preserved'] += 1
        for item in [record, *record['facts'], *record['configurations'][0]['specifications']]:
            citation = source(db, item['source'])
            if citation not in c.sources: c.sources.append(citation)
        for change in category_changes:
            if change['computer_id'] != c.id: continue
            citation = source(db, change['source'])
            for category in c.categories:
                row.claims.append(ImportClaim(computer_id=c.id, source_id=citation.id, entity='Computer', target_id=c.id,
                    field='category', previous={'value': change['before']}, value={'value': category.id},
                    status='pending', estimated=False, evidence=change['evidence']))
        for image in list(c.images):
            if image.source_url not in data['wrong_automatic_photos'].get(record['model_name'], []): continue
            if not (image.caption or '').startswith('Scelta automatica Commons ·'): continue
            photo_changes.append({'computer_id': c.id, 'action': 'retire_unrelated_automatic_image',
                                  'before': {col.name: serialize(getattr(image, col.name)) for col in ComputerImage.__table__.columns}})
            if c.image_url == image.remote_url: c.image_url = None
            c.images.remove(image); report['wrong_automatic_photos_removed'] += 1
        manual_cover = any(i.is_primary and not (i.caption or '').startswith('Scelta automatica Commons ·') for i in c.images)
        for position, proposal in enumerate(data['photos'][record['model_name']]):
            image = next((i for i in c.images if i.remote_url == proposal['image_url']), None)
            if image is None:
                values = {k: v for k, v in proposal.items() if k not in ('image_url', 'permission_basis')}
                image = ComputerImage(remote_url=proposal['image_url'], **values,
                                      display_order=max((i.display_order for i in c.images), default=-1) + 1)
                c.images.append(image); report['photos_added'] += 1
                photo_changes.append({'computer_id': c.id, 'action': 'add', 'proposal': proposal})
            if position == 0 and not manual_cover:
                for other in c.images: other.is_primary = other is image
        report['updated'] += 1
    db.flush()
    report['import_job_id'] = job.id
    db.add(CatalogReconciliation(entity=ENTITY, source_id=0, target_id=0,
        note='EarthStation-I e Mistrum: ricerca documentata e fotografie attribuite; nessuna verifica storica automatica.',
        snapshot={**report, 'changes': changes, 'category_changes': category_changes,
                  'photo_changes': photo_changes, 'research': data['research']}))
    db.flush(); refresh_pending(db, commit=False, locked=True); db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Applica; senza opzione mostra solo un’anteprima.')
    args = parser.parse_args()
    from ..main import SessionLocal
    with SessionLocal() as db: result = apply(db) if args.apply else preview(db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
