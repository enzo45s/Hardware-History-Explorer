"""Photo enrichment must never recreate computers or disturb curated content."""
import importlib
import json
from copy import deepcopy
from pathlib import Path
import pytest
from sqlalchemy import select, func
from app.main import SessionLocal
from app.models import (Computer, Manufacturer, Configuration, Specification, Release,
                        Market, Source, ComputerImage)
from app.import_models import ImportJob, CatalogReconciliation
from app.importing import catalog_photos as photos
from app.importing.catalog_aliases import remember
from app.source_policy import is_internal_source


@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'), 'seed', lambda db: None)


def row_for(model):
    return next(r for r in photos.load()[0]['records'] if r['model_name'] == model)


def create(db, record, name=None):
    maker = db.scalar(select(Manufacturer).where(Manufacturer.name == record['manufacturer']))
    if maker is None: maker = Manufacturer(name=record['manufacturer'])
    c = Computer(manufacturer=maker, model_name=name or record['model_name'], description='Storia curata a mano')
    db.add(c); db.flush()
    return c


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_research_has_model_evidence_credit_and_no_rear_diagrams_as_photos():
    data, checksum = photos.load()
    assert len(data['records']) == 45 and len(checksum) == 64
    assert sum('crop_bounds' in r for r in data['records']) == 24
    assert {r['image_kind'] for r in data['records']} == {'photograph', 'catalog_illustration'}
    assert len(data['research']['unselected_references']) == 8
    for record in data['records']:
        assert record['photo']['source_url'] and record['photo']['author'] and record['evidence']
        assert 'data:' not in record['photo']['image_url']
        if record['match_kind'] == 'shared_enclosure': assert record['shared_enclosure_note']
    assert 'Scheda' not in row_for('IRIS 3130')['photo']['caption']
    assert 'R4000' in row_for('IRIS Indigo R4400')['photo']['caption']
    assert '2000' not in row_for('Kaypro PC')['model_aliases']


def test_preview_writes_nothing_and_empty_archive_creates_nothing(client):
    with SessionLocal() as db:
        report = photos.preview(db)
        assert report['images_to_add'] == 0 and report['skipped']
        assert count(db, Source) == count(db, ImportJob) == 0
        result = photos.apply(db)
        assert result['images_added'] == result['created_computers'] == 0
        assert count(db, Computer) == count(db, Source) == count(db, ImportJob) == 0


def test_photo_only_native_import_preserves_all_computer_technical_and_price_fields(client, monkeypatch):
    # Importing the offline package must not call a web provider.
    monkeypatch.setattr('httpx.get', lambda *a, **k: pytest.fail('Unexpected network request'))
    with SessionLocal() as db:
        data, _ = photos.load()
        before = {}
        market = Market(name='Europa')
        for row in data['records']:
            c = create(db, row)
            c.configurations.append(Configuration(variant_name='Configurazione manuale',
                specifications=[Specification(component_type='RAM', property_name='Capacità', numeric_value=123, unit='KB')]))
            c.releases.append(Release(market=market, price=1234, currency='GBP'))
            before[c.id] = (c.model_name, c.description)
        db.commit()
        ids = list(before)
        result = photos.apply(db); db.expire_all()
        assert result['images_added'] == 45 and result['created_computers'] == 0
        assert count(db, Computer) == 45 and count(db, Specification) == 45 and count(db, Release) == 45
        for c in db.scalars(select(Computer)):
            assert (c.model_name, c.description) == before[c.id]
            assert c.configurations[0].specifications[0].numeric_value == 123
            assert c.releases[0].price == 1234 and c.releases[0].currency == 'GBP'
            assert len(c.images) == 1 and c.images[0].is_primary
            assert c.sources and all(not is_internal_source(s) for s in c.sources)
        assert photos.apply(db)['already_applied']
        assert count(db, ImportJob) == 1
        # An intentional later removal is not reversed by replaying the package.
        c = db.get(Computer, ids[0]); c.images.clear(); db.commit()
        assert photos.apply(db)['already_applied'] and count(db, ComputerImage) == 44
    listing = client.get('/api/computers', params={'q': 'PC-9801FS'}).json()
    assert listing['items'][0]['image_url'].find('#hhe-crop=') > 0
    detail = client.get('/api/computers/'+str(listing['items'][0]['id'])).json()
    assert '#hhe-crop=' not in detail['images'][0]['url']
    assert '#hhe-crop=' in detail['images'][0]['thumbnail_url']


@pytest.mark.parametrize('cover_type', ['gallery', 'legacy_url'])
def test_existing_manual_or_automatic_photos_and_covers_are_preserved(client, cover_type):
    with SessionLocal() as db:
        c = create(db, row_for('Kaypro 4/84'))
        if cover_type == 'gallery': c.images.append(ComputerImage(remote_url='https://example.org/manual.jpg', is_primary=True))
        else: c.image_url = 'https://example.org/legacy.jpg'
        db.commit(); before = c.image_url
        result = photos.apply(db)
        assert result['images_added'] == 0 and c.image_url == before
        assert count(db, ComputerImage) == (1 if cover_type == 'gallery' else 0)
        assert count(db, Source) == count(db, ImportJob) == 0


def test_aliases_and_old_pc_name_reuse_identity_without_renaming(client):
    with SessionLocal() as db:
        pc = create(db, row_for('Kaypro PC'), name='PC')
        former = create(db, row_for('Kaypro 2/84'))
        remember(db, former, former.id); former.model_name = 'Nome modificato dal curatore'
        db.commit(); ids = [pc.id, former.id]
        result = photos.apply(db)
        assert result['images_added'] == 2 and count(db, Computer) == 2
        assert db.get(Computer, ids[0]).model_name == 'PC'
        assert db.get(Computer, ids[1]).model_name == 'Nome modificato dal curatore'


def test_duplicate_models_are_not_merged_and_substantive_configurations_survive(client):
    with SessionLocal() as db:
        for _ in range(2): create(db, row_for('Kaypro PC'))
        c = create(db, row_for('PC-9821As'))
        c.configurations = [Configuration(variant_name='Base'), Configuration(variant_name='Windows')]
        db.commit(); cid = c.id; cfgids = {v.id for v in c.configurations}
        result = photos.apply(db)
        assert result['images_added'] == 1 and count(db, Computer) == 3
        assert {v.id for v in db.get(Computer, cid).configurations} == cfgids
        assert any(r['model_name'] == 'Kaypro PC' and 'ambigua' in r['reason'] for r in result['skipped'])


def test_existing_real_source_is_reused_and_internal_citation_not_revived(client):
    with SessionLocal() as db:
        record = row_for('PC-9821As'); c = create(db, record)
        internal = Source(title='HHE — riferimento interno', publisher='Hardware History Explorer', url=record['source']['url'])
        real = Source(title='Catalogo NEC conservato da With98', url=record['source']['url'])
        db.add_all([internal, real]); db.commit(); sid = real.id
        photos.apply(db); db.expire_all()
        assert {s.id for s in db.get(Computer, c.id).sources} == {sid}
        assert count(db, Source) == 2


@pytest.mark.parametrize('failure_point', ['stage', 'refresh_pending'])
def test_failure_rolls_back_images_sources_and_audit(client, monkeypatch, failure_point):
    def fail(*a, **k): raise RuntimeError('synthetic failure')
    if failure_point == 'stage': monkeypatch.setattr(photos, 'stage', fail)
    else: monkeypatch.setattr('app.catalog_store.refresh_pending', fail)
    with SessionLocal() as db:
        create(db, row_for('PC-9821As')); db.commit()
        with pytest.raises(RuntimeError, match='synthetic failure'): photos.apply(db)
        assert count(db, Computer) == 1
        for model in [ComputerImage, Source, ImportJob, CatalogReconciliation]: assert count(db, model) == 0


@pytest.mark.parametrize('field', ['crop', 'rights', 'match'])
def test_incomplete_evidence_or_invalid_crop_is_rejected_before_writes(tmp_path, client, field):
    data, _ = photos.load(); data = deepcopy(data)
    data['records'] = [deepcopy(row_for('PC-9821As'))]
    r = data['records'][0]
    if field == 'crop': r['crop_bounds'][2] = 1000000
    elif field == 'rights': r.pop('usage_basis')
    else: r['match_kind'] = 'shared_enclosure'; r.pop('shared_enclosure_note', None)
    path = tmp_path/'bad.json'; path.write_text(json.dumps(data))
    with SessionLocal() as db:
        with pytest.raises(ValueError): photos.apply(db, path)
        assert count(db, Source) == count(db, Computer) == 0
