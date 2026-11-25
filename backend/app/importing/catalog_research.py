"""Explicit offline enrichment for NEC, NeXT, Kaypro, SGI, Daewoo and Fenner.

Preview by default. Only Sol-20 and Laser 500 may be created. Native rows,
prices, curated content and substantive configurations retain their identities.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, unquote

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from ..admin import catalog_lock, historical_date
from ..catalog_identity import replaceable
from ..import_models import CatalogReconciliation, ImportClaim
from ..models import (Computer, Manufacturer, Configuration, Specification, Fact,
                      Release, Market, Category, ComputerImage, spec_source)
from ..source_policy import is_mame_source
from .catalog_aliases import alias_for, remember
from .dec_research import verified_field, verified_spec
from .engine import stage, source, reference
from .identity import computer_key, maker_key
from .normalize import Record, Spec, Citation
from .vocabulary import matching_specs, quantity_equal, spec_values

PACKAGE = Path(__file__).parent / 'data/catalog-research-2026-11-v1.json'
ENTITY = 'catalog_research'
NEW = {('Processor Technology', 'Sol-20'), ('Video Technology', 'Laser 500')}
MAKERS = {'Daewoo', 'Fenner', 'H/H Microcomputers', 'Kaypro Corporation', 'Non-Linear Systems',
          'NEC', 'Next Software Inc', 'Silicon Graphics', 'Processor Technology', 'Video Technology'}


def load(path=PACKAGE):
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if set(data['new_models']) != {m for _, m in NEW}:
        raise ValueError('Nuovi modelli non autorizzati.')
    keys = set()
    for record in data['records']:
        Record.model_validate(record)
        key = (record['manufacturer'], record['model_name'])
        if record['manufacturer'] not in MAKERS or key in keys:
            raise ValueError('Modello duplicato o produttore fuori ambito.')
        keys.add(key)
        if len(record['configurations']) != 1:
            raise ValueError('Il supplemento richiede una sola configurazione documentale.')
        seen = set()
        for item in [record, *record.get('facts', []), *record.get('releases', []),
                     *record['configurations'][0]['specifications']]:
            Citation.model_validate(item['source'])
            if not item['source'].get('url') or not item.get('evidence'):
                raise ValueError('Dato privo di fonte o evidenza.')
        for spec in record['configurations'][0]['specifications']:
            key = tuple(spec.get(f) for f in ('component_type', 'component_name', 'property_name'))
            if key in seen: raise ValueError('Specifica duplicata.')
            seen.add(key)
    if not NEW <= keys: raise ValueError('Nuovi modelli mancanti.')
    for rule in data['corrections']:
        if (rule['manufacturer'], rule['model_name']) not in keys:
            raise ValueError('Rettifica fuori ambito.')
        Spec.model_validate(rule['before'])
        if rule['after'] is not None: Spec.model_validate(rule['after'])
        Citation.model_validate(rule['source'])
        if not rule.get('evidence'): raise ValueError('Rettifica priva di evidenza.')
    for rule in data['renames']:
        if (rule['manufacturer'], rule['model_name']) not in keys or not rule.get('new_name'):
            raise ValueError('Rinomina fuori ambito.')
        Citation.model_validate(rule['source'])
    from ..main import ImageLinkInput
    for key, photos in data['photos'].items():
        if tuple(key.split('|', 1)) not in keys: raise ValueError('Foto fuori ambito.')
        for photo in photos:
            if not photo.get('permission_basis') or not photo.get('author') or not photo.get('license_name'):
                raise ValueError('Foto priva di condizioni o attribuzione.')
            ImageLinkInput.model_validate({k: v for k, v in photo.items() if k != 'permission_basis'})
    for profile in data.get('manufacturer_profiles', []):
        if profile['name'] not in {m for m, _ in NEW}: raise ValueError('Profilo fuori ambito.')
        Citation.model_validate(profile['source'])
    return data, hashlib.sha256(raw).hexdigest()


def scoped_key(manufacturer, model):
    # Local, documented company aliases for the two additions. This does not
    # consolidate company records or alter matching of unrelated imports.
    key = computer_key(manufacturer, model)
    maker = maker_key(manufacturer)
    if maker in {'video technology', 'video technology ltd.', 'vtech'}:
        return ('video technology', key[1])
    if maker in {'processor technology', 'processor technology corp.', 'processor technology corp'}:
        return ('processor technology', key[1])
    return key


def configuration(computer):
    """Shared facts belong to an existing general sheet, never a CPU variant."""
    if len(computer.configurations) == 1: return computer.configurations[0]
    general = [cfg for cfg in computer.configurations if cfg.variant_name == 'Dati generali del sistema']
    return general[0] if len(general) == 1 else None


def legacy_spec(db, spec):
    # An exact value is insufficient: a human's unverified edit must survive too.
    if verified_spec(db, spec) or not spec.sources or not all(is_mame_source(s) for s in spec.sources):
        return False
    # A manual edit can leave an old bibliography link behind. When the legacy
    # quantity claims survive, require one to still support the current value.
    claims = [c for c in db.scalars(select(ImportClaim).where(ImportClaim.entity == 'Specification',
        ImportClaim.target_id == spec.id, ImportClaim.field == 'quantity', ImportClaim.status == 'pending'))
        if is_mame_source(c.source)]
    current = {k: getattr(spec, k) for k in ('numeric_value', 'text_value', 'unit')}
    return not claims or any(quantity_equal(spec, current, claim.value) for claim in claims)


def prepare(db, path=PACKAGE):
    data, checksum = load(path)
    computers = list(db.scalars(select(Computer).options(selectinload(Computer.manufacturer),
        selectinload(Computer.configurations).selectinload(Configuration.specifications))))
    index = {}
    for c in computers: index.setdefault(scoped_key(c.manufacturer.name, c.model_name), []).append(c)
    selected, skipped = [], []
    for record in data['records']:
        matches = list(index.get(scoped_key(record['manufacturer'], record['model_name']), []))
        alias = alias_for(db, record['manufacturer'], record['model_name'])
        if alias and all(c.id != alias.computer_id for c in matches): matches.append(db.get(Computer, alias.computer_id))
        if len(matches) > 1:
            skipped.append({'model_name': record['model_name'], 'reason': 'Identità ambigua; nessuna scheda unita.'}); continue
        current = matches[0] if matches else None
        if current is None and (record['manufacturer'], record['model_name']) not in NEW:
            skipped.append({'model_name': record['model_name'], 'reason': 'Scheda assente: non viene ricreata.'}); continue
        if current and current.configurations and configuration(current) is None:
            skipped.append({'model_name': record['model_name'], 'reason': 'Configurazioni multiple senza scheda generale univoca.'}); continue
        selected.append((record, current))
    return data, checksum, selected, skipped


def preview(db, path=PACKAGE):
    data, checksum, selected, skipped = prepare(db, path)
    return {'version': data['version'], 'checksum': checksum, 'existing_models': sum(c is not None for _, c in selected),
        'new_models': [r['model_name'] for r, c in selected if c is None],
        'documented_specifications': sum(len(r['configurations'][0]['specifications']) for r, _ in selected),
        'selected_photographs': sum(len(data['photos'].get(r['manufacturer']+'|'+r['model_name'], [])) for r, _ in selected),
        'skipped': skipped, 'research': data['research']}


def same_photo(image, proposal):
    if unquote(image.remote_url or '') == unquote(proposal['image_url']): return True
    def commons_file(url):
        parts = urlsplit(url or '')
        return unquote(parts.path).replace('_', ' ') if parts.hostname == 'commons.wikimedia.org' and parts.path.startswith('/wiki/File:') else None
    existing = commons_file(image.source_url)
    return bool(existing and existing == commons_file(proposal['source_url']))


def apply(db, path=PACKAGE):
    try: return _apply(db, path)
    except Exception:
        db.rollback()
        raise


def _apply(db, path):
    catalog_lock(db)
    data, checksum, selected, skipped = prepare(db, path)
    if any(a.snapshot.get('checksum') == checksum for a in db.scalars(
            select(CatalogReconciliation).where(CatalogReconciliation.entity == ENTITY))):
        db.rollback()
        return {'version': data['version'], 'already_applied': True, 'created': 0, 'updated': 0}
    report = dict(version=data['version'], checksum=checksum, created=0, updated=0,
        specifications_added=0, specifications_corrected=0, specifications_retired=0,
        descriptions_updated=0, curated_descriptions_preserved=0, photographs_added=0,
        renamed=0, skipped=skipped, protected=[], conflicts=[])
    if not selected:
        db.rollback()
        return report
    specs_before = db.scalar(select(func.count()).select_from(Specification))
    job = stage(db, 'manual', Path(path).name, 'json', Path(path).read_bytes(),
        records=[r for r, _ in selected], options={'upload': True, ENTITY: data['version']}, commit=False)
    audit, attributions = [], []
    for row, (record, c) in zip(job.rows, selected):
        if row.status == 'invalid': raise ValueError('Riga non valida: nessuna modifica salvata.')
        created = c is None
        if created:
            # Prefer the exact existing company name. VTech and Video Technology
            # already coexist in some databases; no company merge is implied.
            makers = list(db.scalars(select(Manufacturer)))
            exact = [m for m in makers if m.name.casefold() == record['manufacturer'].casefold()]
            aliases = [m for m in makers if scoped_key(m.name, record['model_name'])[0] == scoped_key(record['manufacturer'], record['model_name'])[0]]
            choices = exact or aliases
            if len(choices) > 1: raise ValueError('Produttore ambiguo per '+record['model_name'])
            maker = choices[0] if choices else Manufacturer(name=record['manufacturer'])
            if not choices:
                db.add(maker)
                for p in data.get('manufacturer_profiles', []):
                    if p['name'] == maker.name:
                        maker.country, maker.description = p['country'], p['description']
                        maker.sources.append(source(db, p['source']))
            c = Computer(manufacturer=maker, model_name=record['model_name'])
            db.add(c); db.flush()
        row.computer_id = c.id
        row.candidates = [c.id]
        row.error = None
        row.status = 'imported' if created else 'updated'
        report['created' if created else 'updated'] += 1
        change = {'computer_id': c.id, 'original_name': c.model_name, 'created': created,
                  'specifications': [], 'image_ids': [], 'facts_added': [], 'release_ids': []}
        root = source(db, record['source'])
        if root not in c.sources: c.sources.append(root)

        def claim(target, field, value, previous, citation, evidence, status='pending'):
            s = source(db, citation)
            if s not in c.sources: c.sources.append(s)
            db.add(ImportClaim(row_id=row.id, computer_id=c.id, source_id=s.id,
                entity=type(target).__name__, target_id=target.id, field=field, value=value,
                previous=previous, status=status, estimated=False, evidence=evidence))
            return s

        cfg = configuration(c)
        if cfg is None:
            cfg = Configuration(variant_name='Scheda tecnica'); c.configurations.append(cfg); db.flush()
        # Retire/correct only exact old, unverified, explicitly legacy assertions.
        for rule in data['corrections']:
            if (rule['manufacturer'], rule['model_name']) != (record['manufacturer'], record['model_name']): continue
            matches = [s for s in cfg.specifications if spec_values(s) == rule['before']]
            if len(matches) != 1: continue
            target = matches[0]
            if not legacy_spec(db, target):
                report['protected'].append({'model_name': c.model_name, 'property': target.property_name,
                                            'reason': 'Dato verificato o non riconducibile al legacy: conservato.'}); continue
            before = {**spec_values(target), 'id': target.id,
                      'source_links': [dict(x._mapping) for x in db.execute(select(spec_source).where(spec_source.c.target_id == target.id))]}
            change['specifications'].append({'before': before, 'after': rule['after'], 'source': rule['source'], 'evidence': rule['evidence']})
            for old in db.scalars(select(ImportClaim).where(ImportClaim.entity == 'Specification',
                    ImportClaim.target_id == target.id, ImportClaim.status == 'pending')):
                if is_mame_source(old.source):
                    old.status = 'rejected'
                    old.review_note = 'Rettifica legacy esplicita: '+data['version']+'; valore precedente conservato nell’audit.'
            if rule['after'] is None:
                cfg.specifications.remove(target); report['specifications_retired'] += 1
            else:
                values = Spec.model_validate(rule['after']).model_dump()
                for field in rule['before']: setattr(target, field, values.get(field))
                target.catalog_details = {}
                target.sources = [source(db, rule['source'])]
                claim(target, 'quantity', {k: getattr(target, k) for k in ('numeric_value', 'text_value', 'unit')},
                      {k: before[k] for k in ('numeric_value', 'text_value', 'unit')}, rule['source'], rule['evidence'])
                report['specifications_corrected'] += 1
        db.flush()
        for raw in record['configurations'][0]['specifications']:
            values = Spec.model_validate(raw).model_dump(mode='json', exclude_none=True)
            citation = values.pop('source'); evidence = values.pop('evidence'); values.pop('estimated', None)
            matches = matching_specs(cfg.specifications, values)
            previous = {k: getattr(matches[0], k) for k in ('numeric_value', 'text_value', 'unit')} if len(matches) == 1 else {}
            incoming = {k: values.get(k) for k in ('numeric_value', 'text_value', 'unit')}
            if not matches:
                target = Specification(**values); cfg.specifications.append(target); db.flush()
                target.sources.append(source(db, citation)); report['specifications_added'] += 1
                change['specifications'].append({'added_id': target.id, 'value': values})
                claim(target, 'quantity', incoming, {}, citation, evidence)
            elif len(matches) == 1 and quantity_equal(matches[0], previous, incoming):
                target = matches[0]; s = source(db, citation)
                if s not in target.sources: target.sources.append(s)
                claim(target, 'quantity', incoming, previous, citation, evidence)
            else:
                # Do not attach a contradicting citation as support of the old value.
                target = matches[0]
                claim(target, 'quantity', incoming, previous, citation, evidence, 'conflict')
                report['conflicts'].append({'model_name': c.model_name, 'property': values['property_name'],
                    'retained': previous, 'incoming': incoming, 'candidate_ids': [s.id for s in matches]})
        incoming = record.get('description')
        if incoming and incoming != c.description:
            if replaceable(c.model_name, c.manufacturer.name, c.description) and not verified_field(db, c.id, 'description'):
                before = c.description; c.description = incoming
                claim(c, 'description', {'value': incoming}, {'value': before}, record['source'], record['evidence'])
                change['description_before'] = before; report['descriptions_updated'] += 1
                if 'wikipedia.org/' in record['source']['url']:
                    attributions.append({'computer_id': c.id, 'title': record['source']['title'], 'url': record['source']['url'],
                        'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/', 'method': 'sintesi italiana documentata',
                        'description_sha256': hashlib.sha256(incoming.encode()).hexdigest()})
            else: report['curated_descriptions_preserved'] += 1
        for item in record.get('facts', []):
            target = next((f for f in c.facts if (f.fact_type, f.statement) == (item['fact_type'], item['statement'])), None)
            if target is None:
                target = Fact(fact_type=item['fact_type'], statement=item['statement']); c.facts.append(target); db.flush()
                change['facts_added'].append(target.id)
            s = claim(target, 'statement', {'value': target.statement}, {}, item['source'], item['evidence'])
            if s not in target.sources: target.sources.append(s)
        # Existing commercialization (including yearless prices) remains untouched.
        if created:
            c.categories = [reference(db, Category, n) for n in record.get('categories', [])]
            for item in record.get('releases', []):
                day, precision = historical_date(item['release_date']); s = source(db, item['source'])
                target = Release(market=reference(db, Market, item['market']), release_date=day,
                    release_precision=precision, sources=[s], catalog_details={'date_scope': 'model', 'date_sources': [s.id]})
                c.releases.append(target); db.flush(); change['release_ids'].append(target.id)
                claim(target, 'release_date', {'value': day.isoformat(), 'precision': precision}, {}, item['source'], item['evidence'])
        primary = bool(c.image_url or any(i.is_primary for i in c.images))
        for photo in data['photos'].get(record['manufacturer']+'|'+record['model_name'], []):
            if any(same_photo(i, photo) for i in c.images) or c.image_url == photo['image_url']: continue
            values = {k: v for k, v in photo.items() if k not in ('permission_basis', 'image_url')}
            image = ComputerImage(remote_url=photo['image_url'], **values,
                is_primary=not primary, display_order=max((i.display_order for i in c.images), default=-1)+1)
            c.images.append(image); db.flush(); primary = True
            citation = {'title': 'Immagine — '+record['model_name'], 'url': photo['source_url'],
                        'source_type': 'image', 'author': photo['author'], 'license': photo['license_name']}
            s = source(db, citation)
            if s not in c.sources: c.sources.append(s)
            change['image_ids'].append(image.id); report['photographs_added'] += 1
        for rule in data['renames']:
            if (rule['manufacturer'], rule['model_name']) != (record['manufacturer'], record['model_name']): continue
            if c.model_name != rule['model_name']: continue
            collision = db.scalar(select(Computer.id).where(Computer.manufacturer_id == c.manufacturer_id,
                        Computer.model_name == rule['new_name'], Computer.id != c.id))
            if collision or verified_field(db, c.id, 'model_name'):
                report['protected'].append({'model_name': c.model_name, 'property': 'Nome', 'reason': 'Nome verificato o collisione.'}); continue
            remember(db, c, c.id); old = c.model_name; c.model_name = rule['new_name']
            claim(c, 'model_name', {'value': c.model_name}, {'value': old}, rule['source'], rule['evidence'])
            change['renamed_to'] = c.model_name; report['renamed'] += 1
        audit.append(change)
    job.status = 'completed'
    db.flush()
    report['import_job_id'] = job.id
    report['claims'] = dict(Counter(c.status for r in job.rows for c in r.claims))
    reconciliation = CatalogReconciliation(entity=ENTITY, source_id=0, target_id=0,
        note='Ricerca per modello; rettifiche legacy puntuali, nuove asserzioni pending, fotografie con condizioni documentate.',
        snapshot={**report, 'changes': audit, 'description_attributions': attributions, 'research': data['research']})
    db.add(reconciliation)
    from ..catalog_store import refresh_pending
    db.flush(); refresh_pending(db, commit=False, locked=True)
    # Physical catalog maintenance can consolidate equivalent specifications.
    # Report the rows that actually survived, preserving the allocation audit.
    allocated = [s['added_id'] for change in audit for s in change['specifications'] if 'added_id' in s]
    report['specifications_created_before_normalization'] = report['specifications_added']
    report['specifications_added'] = db.scalar(select(func.count()).select_from(Specification).where(Specification.id.in_(allocated)))
    report['specifications_consolidated'] = len(allocated) - report['specifications_added']
    report['net_specifications_change'] = db.scalar(select(func.count()).select_from(Specification)) - specs_before
    reconciliation.snapshot = {**reconciliation.snapshot, **report}
    db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Applica il pacchetto; senza opzione mostra l’anteprima.')
    args = parser.parse_args()
    from ..main import SessionLocal
    with SessionLocal() as db: result = apply(db) if args.apply else preview(db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
