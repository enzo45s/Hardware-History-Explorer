"""Offline, transactional addition of General Processor and documented models.

The Modello T and MKIII share a card with two sourced configurations and scoped
aliases. The unrelated SUMUS G5 and Data General are never imported or merged.
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
from .identity import maker_key, computer_key, provider_computer_key
from .normalize import Record, Citation
from .engine import stage, apply_job, source, reference
from .dec_research import verified_field
from .catalog_aliases import alias_for, remember_input

PACKAGE = Path(__file__).parent / 'data/general-processor-v1.json'
ENTITY = 'gp_research'
MODELS = {'Child 8', 'Child Z', 'Modello T', 'GPS4', 'GPS5'}


def load(path=PACKAGE):
    raw = Path(path).read_bytes(); data = json.loads(raw)
    if len(data['records']) != 5 or {r['model_name'] for r in data['records']} != MODELS:
        raise ValueError('Elenco dei modelli General Processor inatteso.')
    for record in data['records']:
        Record.model_validate(record)
        if record['manufacturer'] != 'General Processor': raise ValueError('Produttore inatteso.')
        for cfg in record['configurations']:
            for spec in cfg['specifications']:
                if not spec.get('source', {}).get('url') or not spec.get('evidence'):
                    raise ValueError('Specifica senza fonte o evidenza.')
        if len(record['releases']) != len(data['release_notes'][record['model_name']]):
            raise ValueError('Commercializzazione priva di contesto.')
    p = data['manufacturer_profile']
    ManufacturerInput(name='General Processor', **p['fields'])
    urls = {s['url'] for s in p['sources']}
    for s in p['sources']: Citation.model_validate(s)
    if any(not p['field_sources'].get(k) or not set(p['field_sources'][k]) <= urls for k in p['fields']):
        raise ValueError('Campo aziendale senza fonte.')
    from ..main import ImageLinkInput
    for photos in data['photos'].values():
        for photo in photos:
            ImageLinkInput.model_validate(photo)
            if not photo.get('license_name') or not photo.get('source_url'):
                raise ValueError('Foto senza provenienza o condizioni di uso.')
    return data, hashlib.sha256(raw).hexdigest()


def target_name(name, maker):
    key = provider_computer_key('historical_prices', maker, name)[1]
    if key in {'modelt', 'modellot'}: return 'Modello T'
    for model in MODELS - {'Modello T'}:
        if computer_key(maker, name) == computer_key('General Processor', model): return model
    return None


def prepare(db, path=PACKAGE):
    data, checksum = load(path)
    # Also handle case differences, without treating Data General or generic GP as aliases.
    makers = [m for m in db.scalars(select(Manufacturer)) if maker_key(m.name) == 'general processor']
    if len(makers) > 1: raise ValueError('Produttore General Processor ambiguo: nessuna modifica applicata.')
    maker = makers[0] if makers else None
    index = {name: [] for name in MODELS}; legacy_mkiii = []
    for c in db.scalars(select(Computer).where(Computer.manufacturer_id.in_([m.id for m in makers]))
                        .options(selectinload(Computer.configurations))):
        model = target_name(c.model_name, c.manufacturer.name)
        if model: index[model].append(c)
        elif provider_computer_key('historical_prices', c.manufacturer.name, c.model_name)[1] in {'modeltmkiii', 'modellotmkiii'}:
            legacy_mkiii.append(c.id)
    selected = []; skipped = []
    for record in data['records']:
        name = record['model_name']; matches = index[name]
        if len(matches) > 1 or name == 'Modello T' and legacy_mkiii:
            skipped.append({'model_name': name, 'reason': 'Schede o MKIII separati già presenti: abbinamento da revisionare.'}); continue
        c = matches[0] if matches else None
        cfg_names = {cfg.variant_name for cfg in c.configurations} if c else set()
        known_t = ({'Modello T originale', 'Modello T MKIII'}, {'Model T', 'Modello T MKIII'}, {'Model T', 'Model T MKIII'})
        if c and ((name != 'Modello T' and len(cfg_names) > 1) or (name == 'Modello T' and len(cfg_names) > 1 and cfg_names not in known_t)):
            skipped.append({'model_name': name, 'reason': 'Configurazioni multiple non riconosciute: conservate.'}); continue
        selected.append((record, c))
    return data, checksum, maker, selected, skipped


def preview(db, path=PACKAGE):
    data, checksum, maker, selected, skipped = prepare(db, path)
    return {'version': data['version'], 'checksum': checksum, 'manufacturer_to_create': maker is None,
            'new_models': [r['model_name'] for r, c in selected if c is None],
            'existing_models': [r['model_name'] for r, c in selected if c is not None],
            'technical_assertions': sum(len(cfg['specifications']) for r, _ in selected for cfg in r['configurations']),
            'skipped': skipped, 'research': data['research']}


def apply(db, path=PACKAGE):
    try: return _apply(db, path)
    except Exception:
        db.rollback(); raise


def _apply(db, path):
    catalog_lock(db)
    data, checksum, maker, selected, skipped = prepare(db, path)
    if any(a.snapshot.get('checksum') == checksum for a in db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity == ENTITY))):
        db.rollback(); return {'version': data['version'], 'already_applied': True, 'created': 0, 'updated': 0}
    report = {'version': data['version'], 'checksum': checksum, 'manufacturer_created': maker is None,
              'created': 0, 'updated': 0, 'descriptions_updated': 0, 'curated_descriptions_preserved': 0,
              'photos_added': 0, 'releases_added': 0, 'skipped': skipped}
    if maker is None:
        maker = Manufacturer(name='General Processor'); db.add(maker); db.flush()
    profile = data['manufacturer_profile']; fields = profile_changes(maker, profile)
    before_profile = {k: current(maker, k) for k in fields}
    apply_manufacturer(db, maker, ManufacturerInput(name=maker.name, **fields))
    profile_sources = []
    for citation in profile['sources']:
        cited_fields = [k for k in fields if citation['url'] in profile['field_sources'][k]]
        if not cited_fields: continue
        s = source(db, citation)
        link = db.execute(select(manufacturer_source).where(manufacturer_source.c.target_id == maker.id,
                                                           manufacturer_source.c.source_id == s.id)).first()
        evidence = json.dumps({'adapter': data['version'], 'fields': cited_fields, 'research': profile['research']}, ensure_ascii=False)
        if link is None:
            db.execute(manufacturer_source.insert().values(target_id=maker.id, source_id=s.id,
                       verification_status='pending', evidence=evidence))
        profile_sources.append({'source_id': s.id, 'fields': cited_fields})
    report['manufacturer_fields_updated'] = list(fields)
    records = []; old = {}; names_before = []
    for record, c in selected:
        incoming = deepcopy(record); incoming['manufacturer'] = maker.name
        # Prices are installed as explicit sourced offers below, keeping separate
        # amounts/configurations from the same dated list. Generic ETL cannot infer that scope.
        incoming['releases'] = []
        if c:
            old[c.id] = {'description': c.description, 'has_releases': bool(c.releases),
                         'replaceable_description': replaceable(c.model_name, maker.name, c.description)}
            if record['model_name'] == 'Modello T':
                if c.model_name != 'Modello T':
                    names_before.append({'id': c.id, 'name': c.model_name}); c.model_name = 'Modello T'
                if len(c.configurations) == 1:
                    cfg = c.configurations[0]; cfg.variant_name = 'Modello T originale'
                    cfg.catalog_details = {'catalog_clean': True, 'display_name': cfg.variant_name, 'configuration_ids': [cfg.id]}
            elif c.configurations: incoming['configurations'][0]['variant_name'] = c.configurations[0].variant_name
            incoming['model_name'] = c.model_name
            if c.categories: incoming.pop('categories', None)
        records.append(incoming)
    if not records:
        db.rollback(); return report
    job = stage(db, 'manual', Path(path).name, 'json', Path(path).read_bytes(), records=records,
                options={'upload': True, 'general_processor_research': data['version']}, commit=False)
    for row, (_, c) in zip(job.rows, selected):
        if c: row.computer_id = c.id; row.candidates = [c.id]; row.status = 'ready'
    apply_job(db, job.id, commit=False)
    if any(row.status not in ('imported', 'updated', 'unchanged') for row in job.rows):
        raise ValueError('Ricerca GP non applicata integralmente; transazione annullata.')
    added_releases = []; aliases = []
    for row, (record, previous) in zip(job.rows, selected):
        c = db.get(Computer, row.computer_id); new = c.id not in old
        report['created' if new else 'updated'] += 1
        incoming = row.normalized['description']
        if new: report['descriptions_updated'] += 1
        elif c.description != incoming:
            if old[c.id]['replaceable_description'] and not verified_field(db, c.id, 'description'):
                c.description = incoming; report['descriptions_updated'] += 1
                for claim in row.claims:
                    if claim.entity == 'Computer' and claim.field == 'description': claim.status = 'pending'
            else: report['curated_descriptions_preserved'] += 1
        for item in [record, *record['facts'], *[s for cfg in record['configurations'] for s in cfg['specifications']]]:
            s = source(db, item['source'])
            if s not in c.sources: c.sources.append(s)
        # Existing documented or manual offers stay untouched. Populate empty cards only.
        if new or not old[c.id]['has_releases']:
            for entry, context in zip(record['releases'], data['release_notes'][record['model_name']]):
                s = source(db, entry['source']); day, precision = historical_date(entry['release_date'])
                release = Release(market=reference(db, Market, entry['market']), release_date=day, release_precision=precision,
                                  price=entry.get('price'), currency=entry.get('currency'), price_type=entry.get('price_type'), sources=[s])
                details = {'date_scope': 'reference' if context['date_kind'] == 'reference' else 'model',
                           'date_sources': [s.id], 'date_evidence': {'kind': context['date_kind'], 'source_ids': [s.id]},
                           'commercialization_notes': [context['note']] if context['note'] else []}
                if context['date_kind'] == 'reference': details['reference_note'] = context['note']
                if context['variant']: details['model_variant'] = context['variant']
                if context.get('price_reference'): details['price_reference_date'] = context['price_reference']
                release.catalog_details = details; c.releases.append(release); db.flush()
                row.claims.append(ImportClaim(computer_id=c.id, source_id=s.id, entity='Release', target_id=release.id,
                    field='release_date', value={'value': day.isoformat(), 'precision': precision},
                    previous={'value': None, 'precision': None}, status='pending', estimated=False,
                    evidence=entry['evidence']+' '+context['note']))
                if entry.get('price') is not None:
                    row.claims.append(ImportClaim(computer_id=c.id, source_id=s.id, entity='Release', target_id=release.id,
                        field='price_bundle', value={k:entry.get(k) for k in ('price', 'currency', 'price_type')},
                        previous={k:None for k in ('price', 'currency', 'price_type')}, status='pending', estimated=False,
                        evidence=entry['evidence']+' '+context['note']))
                added_releases.append({'id': release.id, 'computer_id': c.id, 'entry': entry, 'context': context})
                report['releases_added'] += 1
        manual_cover = any(i.is_primary for i in c.images)
        for i, photo in enumerate(data['photos'].get(record['model_name'], [])):
            if any(image.remote_url == photo['image_url'] for image in c.images): continue
            values = {k:v for k,v in photo.items() if k != 'image_url'}
            c.images.append(ComputerImage(remote_url=photo['image_url'], **values,
                            display_order=max((p.display_order for p in c.images), default=-1)+1,
                            is_primary=not manual_cover and i == 0)); report['photos_added'] += 1
        if record['model_name'] == 'Modello T':
            db.flush()
            for cfg_name, spellings in data['model_t_aliases'].items():
                cfg = next((cfg for cfg in c.configurations if cfg.variant_name == cfg_name), None)
                if cfg is None: raise ValueError('Configurazione Modello T non riconosciuta.')
                for spelling in spellings:
                    alias = alias_for(db, maker.name, spelling)
                    if alias and alias.computer_id != c.id: raise ValueError('Alias Modello T già associato a un’altra scheda.')
                    if alias is None: alias = remember_input(db, c, {'manufacturer': maker.name, 'model_name': spelling})
                    original = deepcopy(alias.original)
                    original.update(configurations=[cfg.id], configuration_names={str(cfg.id): 'Scheda tecnica'},
                                    description='Versione originale con 16 KB di base, espandibili a 32/48 KB.' if cfg_name == 'Modello T originale' else 'Versione MKIII con tastiera separata e 64 KB RAM.')
                    if cfg_name == 'Modello T MKIII':
                        original['releases'] = [r.id for r in c.releases if (r.catalog_details or {}).get('model_variant') == 'Modello T MKIII']
                    else:
                        # This spelling alias scopes only hardware. Assigning all
                        # base offers to it would erase T/05,T/08,T/10,T/20 labels.
                        original['releases'] = []
                    alias.original = original; aliases.append({'name': spelling, 'id': alias.id, 'configuration_id': cfg.id})
    db.flush(); report['import_job_id'] = job.id
    db.add(CatalogReconciliation(entity=ENTITY, source_id=0, target_id=0,
        note='General Processor: profilo, modelli e configurazioni documentati; nuove fonti e asserzioni pending.',
        snapshot={**report, 'manufacturer_id': maker.id, 'manufacturer_before': before_profile,
                  'manufacturer_applied': fields, 'manufacturer_field_sources': profile['field_sources'],
                  'manufacturer_sources': profile_sources, 'names_before': names_before, 'aliases': aliases,
                  'new_releases': added_releases, 'photos': data['photos'], 'research': data['research']}))
    from ..catalog_store import refresh_pending
    db.flush(); refresh_pending(db, commit=False, locked=True); db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Applica la ricerca; senza opzione mostra solo l’anteprima.')
    args = parser.parse_args()
    from ..main import SessionLocal
    with SessionLocal() as db: result = apply(db) if args.apply else preview(db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
