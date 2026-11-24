"""Sourced offline addition of NewBrain, MPF-I and three Robotron computers.

Explicit apply only. Preserve curated records, reuse exact manufacturer/model
aliases and keep differently priced offers scoped instead of duplicating cards.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..admin import catalog_lock, ManufacturerInput, apply_manufacturer, historical_date
from ..models import Computer, Manufacturer, Release, Market, ComputerImage, manufacturer_source
from ..import_models import CatalogReconciliation, ImportClaim
from ..manufacturer_enrichment import changes as profile_changes, current
from ..catalog_identity import replaceable
from .identity import maker_key, computer_key
from .normalize import Record, Citation
from .engine import stage, apply_job, source, reference
from .dec_research import verified_field

PACKAGE = Path(__file__).parent / 'data/microcomputers-2026-11-v1.json'
ENTITY = 'micro_research'
MODELS = {('Grundy Business Systems', 'NewBrain'), ('Multitech', 'Micro-Professor I'),
          ('Robotron', 'KC 85/1'), ('Robotron', 'KC 87'), ('Robotron', 'A 5105')}


def load(path=PACKAGE):
    raw = Path(path).read_bytes(); data = json.loads(raw)
    if len(data['records']) != len(MODELS) or {(r['manufacturer'], r['model_name']) for r in data['records']} != MODELS:
        raise ValueError('Elenco dei modelli inatteso nel supplemento microcomputer.')
    from ..main import ImageLinkInput
    for r in data['records']:
        Record.model_validate(r)
        if len(r['configurations']) != 1 or len(r['releases']) != len(data['release_notes'][r['model_name']]):
            raise ValueError('Configurazione o commercializzazione priva di contesto.')
        for item in [r, *r['facts'], *r['releases'], *r['configurations'][0]['specifications']]:
            if not item.get('source', {}).get('url') or not item.get('evidence'):
                raise ValueError('Dato privo di fonte o evidenza.')
        for context in data['release_notes'][r['model_name']]: Citation.model_validate(context['date_source'])
        for photo in data['photos'][r['model_name']]:
            ImageLinkInput.model_validate(photo)
            if not photo.get('license_name') or not photo.get('source_url'):
                raise ValueError('Foto senza provenienza o licenza.')
    seen = set()
    for profile in data['manufacturer_profiles']:
        key = maker_key(profile['manufacturer_names'][0])
        if key in seen or key not in {maker_key(m) for m, _ in MODELS}: raise ValueError('Profilo inatteso o duplicato.')
        seen.add(key)
        apply_manufacturer(None, Manufacturer(name=profile['manufacturer_names'][0]),
                           ManufacturerInput(name=profile['manufacturer_names'][0], **profile['fields']))
        urls = {s['url'] for s in profile['sources']}
        for s in profile['sources']: Citation.model_validate(s)
        if any(not profile['field_sources'].get(k) or not set(profile['field_sources'][k]) <= urls for k in profile['fields']):
            raise ValueError('Campo aziendale senza fonte.')
    return data, hashlib.sha256(raw).hexdigest()


def prepare(db, path=PACKAGE):
    data, checksum = load(path); makers = {}
    for name in sorted({m for m, _ in MODELS}):
        matches = [m for m in db.scalars(select(Manufacturer)) if maker_key(m.name) == maker_key(name)]
        if len(matches) > 1: raise ValueError('Produttore ambiguo: ' + name + '. Nessuna modifica applicata.')
        makers[name] = matches[0] if matches else None
    selected = []; skipped = []
    for record in data['records']:
        maker = makers[record['manufacturer']]
        matches = [] if maker is None else [c for c in db.scalars(select(Computer).where(Computer.manufacturer_id == maker.id)
            .options(selectinload(Computer.configurations)))
            if computer_key(maker.name, c.model_name) == computer_key(record['manufacturer'], record['model_name'])]
        if len(matches) > 1 or matches and len(matches[0].configurations) > 1:
            skipped.append({'manufacturer': record['manufacturer'], 'model_name': record['model_name'],
                            'reason': 'Schede duplicate o configurazioni multiple: revisione necessaria.'}); continue
        selected.append((record, matches[0] if matches else None))
    return data, checksum, makers, selected, skipped


def preview(db, path=PACKAGE):
    data, checksum, makers, selected, skipped = prepare(db, path)
    return {'version': data['version'], 'checksum': checksum,
            'manufacturers_to_create': [n for n, m in makers.items() if m is None],
            'new_models': [r['model_name'] for r, c in selected if c is None],
            'existing_models': [r['model_name'] for r, c in selected if c is not None], 'skipped': skipped}


def apply(db, path=PACKAGE):
    try: return _apply(db, path)
    except Exception:
        db.rollback(); raise


def _apply(db, path):
    catalog_lock(db)
    data, checksum, makers, selected, skipped = prepare(db, path)
    if any(a.snapshot.get('checksum') == checksum for a in db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity == ENTITY))):
        db.rollback(); return {'version': data['version'], 'already_applied': True, 'created': 0, 'updated': 0}
    report = {'version': data['version'], 'checksum': checksum, 'created': 0, 'updated': 0,
              'manufacturers_created': [], 'manufacturer_fields_updated': {}, 'photos_added': 0,
              'releases_added': 0, 'descriptions_updated': 0, 'curated_descriptions_preserved': 0, 'skipped': skipped}
    profiles_before = []; releases_added = []; photos_added = []; old = {}; records = []
    selected_makers = {r['manufacturer'] for r, _ in selected}
    for name in sorted(selected_makers):
        if makers[name] is None:
            makers[name] = Manufacturer(name=name); db.add(makers[name]); db.flush()
            report['manufacturers_created'].append(name)
    for profile in data['manufacturer_profiles']:
        canonical = next(n for n in makers if maker_key(n) == maker_key(profile['manufacturer_names'][0]))
        if canonical not in selected_makers: continue
        maker = makers[canonical]; fields = profile_changes(maker, profile)
        before = {k: current(maker, k) for k in fields}
        apply_manufacturer(db, maker, ManufacturerInput(name=maker.name, **fields))
        for citation in profile['sources']:
            supported = [k for k in fields if citation['url'] in profile['field_sources'][k]]
            if not supported: continue
            s = source(db, citation)
            link = db.execute(select(manufacturer_source).where(manufacturer_source.c.target_id == maker.id,
                                                               manufacturer_source.c.source_id == s.id)).first()
            if link is None:
                db.execute(manufacturer_source.insert().values(target_id=maker.id, source_id=s.id, verification_status='pending',
                    evidence=json.dumps({'adapter': data['version'], 'fields': supported}, ensure_ascii=False)))
        profiles_before.append({'manufacturer_id': maker.id, 'before': before, 'applied': fields,
                                'field_sources': profile['field_sources'], 'research': profile['research']})
        report['manufacturer_fields_updated'][maker.name] = list(fields)
    for record, c in selected:
        incoming = deepcopy(record); incoming['manufacturer'] = makers[record['manufacturer']].name
        incoming['releases'] = []  # Install explicitly scoped dated offers below.
        if c:
            old[c.id] = {'has_releases': bool(c.releases), 'description': c.description,
                         'replaceable_description': replaceable(c.model_name, c.manufacturer.name, c.description)}
            incoming['model_name'] = c.model_name
            if c.configurations: incoming['configurations'][0]['variant_name'] = c.configurations[0].variant_name
            if c.categories: incoming.pop('categories', None)
        records.append(incoming)
    if not records:
        db.rollback(); return report
    job = stage(db, 'manual', Path(path).name, 'json', Path(path).read_bytes(), records=records,
                options={'upload': True, 'microcomputer_research': data['version']}, commit=False)
    for row, (_, c) in zip(job.rows, selected):
        if c: row.computer_id = c.id; row.candidates = [c.id]; row.status = 'ready'
    apply_job(db, job.id, commit=False)
    if any(r.status not in ('imported', 'updated', 'unchanged') for r in job.rows):
        raise ValueError('Supplemento non applicato integralmente; transazione annullata.')
    for row, (record, _) in zip(job.rows, selected):
        c = db.get(Computer, row.computer_id); new = c.id not in old
        report['created' if new else 'updated'] += 1
        if new: report['descriptions_updated'] += 1
        elif c.description != record['description']:
            if old[c.id]['replaceable_description'] and not verified_field(db, c.id, 'description'):
                c.description = record['description']; report['descriptions_updated'] += 1
                for claim in row.claims:
                    if claim.entity == 'Computer' and claim.field == 'description': claim.status = 'pending'
            else: report['curated_descriptions_preserved'] += 1
        for item in [record, *record['facts'], *record['configurations'][0]['specifications']]:
            s = source(db, item['source'])
            if s not in c.sources: c.sources.append(s)
        if new or not old[c.id]['has_releases']:
            for entry, context in zip(record['releases'], data['release_notes'][record['model_name']]):
                price_source = source(db, entry['source']); date_source = source(db, context['date_source'])
                citations = list({s.id: s for s in (price_source, date_source)}.values())
                day, precision = historical_date(entry['release_date'])
                details = {'date_scope': 'model', 'date_sources': [date_source.id],
                           'date_evidence': {'kind': context['date_kind'], 'source_ids': [date_source.id]},
                           'commercialization_notes': [context['note']]}
                if context['variant']: details['model_variant'] = context['variant']
                if context.get('price_reference_date'): details['price_reference_date'] = context['price_reference_date']
                release = Release(market=reference(db, Market, entry['market']), release_date=day, release_precision=precision,
                    price=entry.get('price'), currency=entry.get('currency'), price_type=entry.get('price_type'), sources=citations,
                    catalog_details=details)
                c.releases.append(release); db.flush()
                row.claims.append(ImportClaim(computer_id=c.id, source_id=date_source.id, entity='Release', target_id=release.id,
                    field='release_date', value={'value': day.isoformat(), 'precision': precision},
                    previous={'value': None, 'precision': None}, status='pending', estimated=False, evidence=context['note']))
                if entry.get('price') is not None:
                    row.claims.append(ImportClaim(computer_id=c.id, source_id=price_source.id, entity='Release', target_id=release.id,
                        field='price_bundle', value={k: entry.get(k) for k in ('price', 'currency', 'price_type')},
                        previous={k: None for k in ('price', 'currency', 'price_type')}, status='pending', estimated=False,
                        evidence=entry['evidence']+' '+context['note']))
                for s in citations:
                    if s not in c.sources: c.sources.append(s)
                releases_added.append(release.id); report['releases_added'] += 1
        primary = any(i.is_primary for i in c.images)
        for photo in data['photos'][record['model_name']]:
            if any(i.remote_url == photo['image_url'] for i in c.images): continue
            image = ComputerImage(remote_url=photo['image_url'], **{k: v for k, v in photo.items() if k != 'image_url'},
                display_order=max((i.display_order for i in c.images), default=-1)+1, is_primary=not primary)
            c.images.append(image); db.flush(); primary = True
            photos_added.append(image.id); report['photos_added'] += 1
    db.flush(); report['import_job_id'] = job.id
    db.add(CatalogReconciliation(entity=ENTITY, source_id=0, target_id=0,
        note='NewBrain, Micro-Professor I e Robotron: aggiunte documentate, asserzioni pending.',
        snapshot={**report, 'manufacturer_changes': profiles_before, 'computer_before': old,
                  'release_ids_added': releases_added, 'image_ids_added': photos_added, 'research': data['research']}))
    from ..catalog_store import refresh_pending
    db.flush(); refresh_pending(db, commit=False, locked=True); db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Applica il pacchetto; senza opzione mostra l’anteprima.')
    args = parser.parse_args()
    from ..main import SessionLocal
    with SessionLocal() as db: result = apply(db) if args.apply else preview(db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
