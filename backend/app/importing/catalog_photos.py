"""Explicit, photo-only supplement: existing NEC, Kaypro, Daewoo and SGI cards.

No network access, creation/renaming of computers, or changes to technical data.
The default is a read-only preview. Existing galleries and covers are preserved.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.parse import urldefrag
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..admin import catalog_lock
from ..source_policy import is_internal_source
from ..import_models import CatalogReconciliation
from ..models import Computer, ComputerImage, Source
from .catalog_aliases import alias_for
from .engine import stage, source
from .identity import computer_key
from .normalize import Citation

PACKAGE = Path(__file__).parent / 'data/catalog-photos-deep-2026-11-v1.json'
ENTITY = 'catalog_photo_deep'
MAKERS = {'NEC', 'Daewoo', 'Kaypro Corporation', 'Non-Linear Systems', 'Silicon Graphics'}
KINDS = {'photograph', 'catalog_illustration'}
MATCHES = {'exact_model', 'documented_variant', 'documented_catalog', 'shared_enclosure'}


def load(path=PACKAGE):
    from ..main import ImageLinkInput
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if not 1 <= len(data['records']) <= 200: raise ValueError('Numero di immagini fuori limite.')
    seen = set()
    for row in data['records']:
        key = (row['manufacturer'], row['model_name'].casefold())
        if key in seen or row['manufacturer'] not in MAKERS:
            raise ValueError('Immagine duplicata o produttore fuori ambito.')
        seen.add(key)
        Citation.model_validate(row['source'])
        for s in row.get('supporting_sources', []): Citation.model_validate(s)
        photo = ImageLinkInput.model_validate(row['photo'])
        if (not row['source'].get('url') or not row.get('evidence') or not row.get('usage_basis')
                or not photo.author or not photo.license_name or not photo.source_url):
            raise ValueError('Immagine senza fonte, attribuzione o condizioni documentate.')
        if row['image_kind'] not in KINDS or row['match_kind'] not in MATCHES:
            raise ValueError('Tipo di immagine o abbinamento non documentato.')
        if row['match_kind'] == 'shared_enclosure' and not row.get('shared_enclosure_note'):
            raise ValueError('Aspetto comune non esplicitato.')
        has_crop = '#hhe-crop=' in (photo.thumbnail_url or '')
        if has_crop != bool(row.get('crop_bounds')):
            raise ValueError('Regione dell’immagine priva di geometria documentata.')
        if row.get('crop_bounds'):
            width, height = row['original_dimensions']
            x, y, w, h = row['crop_bounds']
            values = [width, height, x, y, w, h]
            if (any(not isinstance(v, int) or isinstance(v, bool) for v in values)
                    or min(width, height, w, h) <= 0 or min(x, y) < 0
                    or max(width, height) > 100000 or x+w > width or y+h > height):
                raise ValueError('Regione dell’immagine non valida.')
            if '#' in photo.image_url: raise ValueError('L’originale deve conservare il proprio URL senza ritagli.')
            expected = photo.image_url+'#hhe-crop='+','.join(map(str, values))
            if photo.thumbnail_url != expected: raise ValueError('Regione non coerente con l’originale.')
    return data, hashlib.sha256(raw).hexdigest()


def plan(db, path=PACKAGE):
    data, checksum = load(path)
    computers = list(db.scalars(select(Computer).options(selectinload(Computer.manufacturer),
                                                         selectinload(Computer.images))))
    index = {}
    for c in computers:
        index.setdefault(computer_key(c.manufacturer.name, c.model_name), []).append(c)
    selected, skipped = [], []
    for record in data['records']:
        matches = {}
        for name in [record['model_name'], *record.get('model_aliases', [])]:
            for c in index.get(computer_key(record['manufacturer'], name), []): matches[c.id] = c
            alias = alias_for(db, record['manufacturer'], name)
            if alias: matches[alias.computer_id] = db.get(Computer, alias.computer_id)
        if len(matches) != 1:
            skipped.append({'manufacturer': record['manufacturer'], 'model_name': record['model_name'],
                            'reason': 'Scheda assente o ambigua: nessun computer creato.'}); continue
        c = next(iter(matches.values()))
        if c.image_url or c.images:
            skipped.append({'manufacturer': record['manufacturer'], 'model_name': c.model_name,
                            'reason': 'Immagine già presente: galleria e copertina conservate.'}); continue
        selected.append((record, c))
    return data, checksum, selected, skipped


def citation_source(db, citation):
    # One bibliography resource can support several photographs. Keep precise
    # anchors and individual photographer credits on the images and in the audit.
    url = citation['url']
    base, _ = urldefrag(url)
    candidates = db.scalars(select(Source).where(Source.url.in_([url, base])).order_by(Source.id))
    existing = next((s for s in candidates if not is_internal_source(s)), None)
    return existing or source(db, citation)


def preview(db, path=PACKAGE):
    data, checksum, selected, skipped = plan(db, path)
    return {'version': data['version'], 'checksum': checksum, 'images_to_add': len(selected),
            'image_types': dict(Counter(r['image_kind'] for r, _ in selected)),
            'models': [c.model_name for _, c in selected], 'skipped': skipped, 'research': data['research']}


def apply(db, path=PACKAGE):
    try: return _apply(db, path)
    except Exception:
        db.rollback()
        raise


def _apply(db, path):
    catalog_lock(db)
    data, checksum, selected, skipped = plan(db, path)
    if any(a.snapshot.get('checksum') == checksum for a in db.scalars(
            select(CatalogReconciliation).where(CatalogReconciliation.entity == ENTITY))):
        db.rollback()
        return {'version': data['version'], 'already_applied': True, 'images_added': 0}
    report = {'version': data['version'], 'checksum': checksum, 'images_added': 0, 'created_computers': 0,
              'skipped': skipped, 'models': [], 'image_types': dict(Counter(r['image_kind'] for r, _ in selected))}
    if not selected:
        db.rollback()
        return report
    records = [{'manufacturer': c.manufacturer.name, 'model_name': c.model_name,
                'source': r['source'], 'evidence': r['evidence']} for r, c in selected]
    job = stage(db, 'manual', Path(path).name, 'json', Path(path).read_bytes(), records=records,
                options={'upload': True, 'existing_only': True, ENTITY: data['version']}, commit=False)
    changes = []
    for row, (record, c) in zip(job.rows, selected):
        if row.status == 'invalid': raise ValueError('Immagine non valida: importazione annullata.')
        row.computer_id = c.id
        row.candidates = [c.id]
        row.status = 'updated'
        row.error = None
        before = {'image_url': c.image_url, 'image_ids': [i.id for i in c.images]}
        photo = record['photo']
        image = ComputerImage(remote_url=photo['image_url'], **{k: v for k, v in photo.items() if k != 'image_url'},
                              is_primary=True, display_order=0)
        c.images.append(image)
        for citation in [record['source'], *record.get('supporting_sources', []),
                         {'title': 'Immagine — '+record['model_name'], 'url': photo['source_url'],
                          'author': photo['author'][:180], 'license': photo['license_name'], 'source_type': 'image'}]:
            s = citation_source(db, citation)
            if s not in c.sources: c.sources.append(s)
        db.flush()
        changes.append({'computer_id': c.id, 'image_id': image.id, 'before': before,
                        'record': record})
        report['models'].append(c.model_name)
        report['images_added'] += 1
    job.status = 'completed'
    report['import_job_id'] = job.id
    db.add(CatalogReconciliation(entity=ENTITY, source_id=0, target_id=0,
        note='Ricerca fotografie e cataloghi: sole gallerie vuote, originali e diritti conservati.',
        snapshot={**report, 'changes': changes, 'research': data['research']}))
    from ..catalog_store import refresh_pending
    db.flush()
    refresh_pending(db, commit=False, locked=True)
    db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Associa le immagini; senza opzione mostra l’anteprima.')
    args = parser.parse_args()
    from ..main import SessionLocal
    with SessionLocal() as db: result = apply(db) if args.apply else preview(db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
