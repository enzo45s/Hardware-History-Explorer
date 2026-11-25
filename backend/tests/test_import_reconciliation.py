"""Synthetic data verifies alias prevention and reviewed, lossless reconciliation."""
import pytest
from sqlalchemy import select, func
from app.main import SessionLocal, UPLOAD_DIR
from app.models import Computer, Manufacturer, Source, ComputerImage, Configuration, Specification, Release, computer_source
from app.import_models import CatalogReconciliation, ExternalIdentity, ImportClaim
from app.importing.identity import computer_key
from test_imports import record, upload, apply, detail

PREFIX = '/api/admin/imports/reconciliation'


@pytest.mark.parametrize('manufacturer,model,existing', [
    ('Apple Computer', 'Apple II', 'Apple II'),
    ('Apple Computer, Inc.', 'Apple Macintosh 128K', 'Macintosh 128K'),
    ('International Business Machines', 'IBM Personal Computer 5150', 'IBM PC 5150'),
    ('Commodore Business Machines', 'C64', 'Commodore 64'),
])
def test_known_aliases_match_seed_without_creating_computers_or_manufacturers(client, manufacturer, model, existing):
    makers = client.get('/api/meta').json()['manufacturers']
    job = upload(client, [record(manufacturer=manufacturer, model_name=model)]).json()['id']
    row = detail(client, job)['rows'][0]
    assert row['computer_id'] is not None and row['status'] == 'ready'
    apply(client, job)
    c = client.get(f"/api/computers/{row['computer_id']}").json()
    assert c['model_name'] == existing and c['sources']
    assert client.get('/api/computers').json()['total'] == 10
    assert client.get('/api/meta').json()['manufacturers'] == makers
    assert not [claim for claim in detail(client, job)['rows'][0]['claims']
                if claim['status'] == 'conflict' and claim['field'] in ('manufacturer_id', 'model_name')]
    assert apply(client, upload(client, [record(manufacturer=manufacturer, model_name=model)]).json()['id'])['counts'] == {'unchanged': 1}


def legacy_duplicate(client):
    with SessionLocal() as db:
        target = db.scalar(select(Computer).where(Computer.model_name == 'Apple II'))
        maker = Manufacturer(name='Apple Computer', country='Synthetic country')
        citation = Source(title='Synthetic document', url='https://example.org/duplicate')
        source = Computer(manufacturer=maker, model_name='Apple II', description='Synthetic imported description', sources=[citation])
        config = Configuration(variant_name='Configurazione rappresentativa', computer=source,
            specifications=[Specification(component_type='RAM', property_name='Capacità', numeric_value=4, unit='KiB', sources=[citation])])
        source.releases.append(Release(market=target.releases[0].market, price=123, currency='USD', sources=[citation]))
        source.images.append(ComputerImage(local_filename='retained.webp', caption='Synthetic image', is_primary=True))
        db.add(source); db.commit()
        target_id, source_id, maker_id, citation_id = target.id, source.id, maker.id, citation.id
        db.execute(computer_source.update().where(computer_source.c.target_id == source_id)
            .values(evidence='Synthetic existing evidence', verification_status='pending'))
        db.commit()
        identifiers = {'configuration': config.id, 'specification': config.specifications[0].id,
                       'release': source.releases[0].id, 'image': source.images[0].id}
    (UPLOAD_DIR / 'retained.webp').write_bytes(b'Synthetic image file retained untouched')
    data = record(manufacturer='Apple Computer', model_name='Apple II', configurations=[{
        'variant_name': 'Configurazione rappresentativa', 'specifications': [
            {'component_type': 'RAM', 'property_name': 'Capacità', 'numeric_value': 4, 'unit': 'KiB'}]}])
    job = upload(client, [data]).json()['id']; row = detail(client, job)['rows'][0]
    assert row['status'] == 'ambiguous'
    assert client.post(f"/api/admin/imports/{job}/rows/{row['id']}/match", json={'computer_id': source_id}).status_code == 200
    apply(client, job)
    return source_id, target_id, maker_id, citation_id, identifiers, job, data


def preview(client, entity, source_id, target_id):
    response = client.post(PREFIX + '/preview', json={'entity': entity, 'source_id': source_id, 'target_id': target_id})
    assert response.status_code == 200, response.text
    data = response.json()
    return {key: data[key] for key in ('entity', 'source_id', 'target_id', 'token')}


def test_merge_preserves_children_prices_images_sources_identities_and_audit(client):
    source_id, target_id, maker_id, citation_id, ids, job, data = legacy_duplicate(client)
    before = client.get('/api/computers').json()['total']
    decision = preview(client, 'computer', source_id, target_id)
    assert client.get('/api/computers').json()['total'] == before
    response = client.post(PREFIX + '/apply', json={**decision, 'note': 'Checked synthetic duplicate only.'})
    assert response.status_code == 200, response.text
    assert client.get(f'/api/computers/{source_id}').status_code == 404
    assert client.get('/api/computers').json()['total'] == before - 1
    c = client.get(f'/api/computers/{target_id}').json()
    assert any(cfg['id'] == ids['configuration'] for cfg in c['configurations'])
    assert any(spec['id'] == ids['specification'] for cfg in c['configurations'] for spec in cfg['specifications'])
    assert next(release for release in c['releases'] if release['id'] == ids['release'])['price'] == 123
    assert next(image for image in c['images'] if image['id'] == ids['image'])['caption'] == 'Synthetic image'
    assert (UPLOAD_DIR / 'retained.webp').is_file()
    assert any(s['id'] == citation_id for s in c['sources'])
    original = client.get(PREFIX + f"/history/{response.json()['reconciliation_id']}").json()
    assert any(row['id'] == source_id for row in original['computer'])
    assert original['computer_images'][0]['local_filename'] == 'retained.webp'
    with SessionLocal() as db:
        assert db.scalar(select(ExternalIdentity.computer_id)) == target_id
        assert db.scalar(select(func.count()).select_from(ImportClaim).where(ImportClaim.computer_id == source_id)) == 0
        link = db.execute(select(computer_source).where(computer_source.c.target_id == target_id,
                          computer_source.c.source_id == citation_id)).mappings().one()
        assert link['evidence'] == 'Synthetic existing evidence' and link['verification_status'] == 'pending'
    assert detail(client, job)['rows'][0]['computer_id'] == target_id
    assert apply(client, upload(client, [data]).json()['id'])['counts'] == {'unchanged': 1}
    assert client.get('/api/computers').json()['total'] == before - 1
    c = client.get(f'/api/computers/{target_id}').json()
    assert len(c['configurations']) == 2
    moved = next(cfg for cfg in c['configurations'] if cfg['id'] == ids['configuration'])
    assert len(moved['specifications']) == 1 and moved['specifications'][0]['id'] == ids['specification']
    representative = next(cfg for cfg in c['configurations'] if cfg['id'] != ids['configuration'])
    assert all(spec['component_type'] == 'CPU' for spec in representative['specifications'])


def test_manufacturer_merge_reassigns_catalog_and_reference_claims_without_promoting_them(client):
    source_id, target_id, maker_id, _, _, job, _ = legacy_duplicate(client)
    target_maker = client.get(f'/api/computers/{target_id}').json()['manufacturer_id']
    decision = preview(client, 'manufacturer', maker_id, target_maker)
    response = client.post(PREFIX + '/apply', json={**decision, 'note': 'Checked synthetic manufacturer alias.'})
    assert response.status_code == 200, response.text
    assert client.get(f'/api/computers/{source_id}').json()['manufacturer_id'] == target_maker
    assert all(m['id'] != maker_id for m in client.get('/api/meta').json()['manufacturers'])
    claims = detail(client, job)['rows'][0]['claims']
    assert not any(c['status'] == 'verified' for c in claims)
    manufacturer = next(c for c in claims if c['field'] == 'manufacturer_id')
    assert manufacturer['display']['proposed'] == 'Apple'
    audit = client.get(PREFIX + f"/history/{response.json()['reconciliation_id']}").json()
    assert any(c['value']['value'] == maker_id for c in audit['claims'])


def test_stale_preview_cannot_merge_after_a_catalog_edit(client):
    source_id, target_id, _, _, _, _, _ = legacy_duplicate(client)
    decision = preview(client, 'computer', source_id, target_id)
    with SessionLocal() as db:
        db.get(Computer, target_id).description = 'Synthetic newer edit'; db.commit()
    response = client.post(PREFIX + '/apply', json={**decision, 'note': 'This stale preview must be rejected.'})
    assert response.status_code == 409 and 'cambiati' in response.json()['detail']
    assert client.get(f'/api/computers/{source_id}').status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(CatalogReconciliation)) == 0


def test_system360_family_is_never_collapsed_into_model50(client):
    assert computer_key('IBM', 'IBM System/360') != computer_key('IBM', 'IBM System/360 Model 50')
    with SessionLocal() as db:
        family = db.scalar(select(Computer).where(Computer.model_name == 'IBM System/360'))
        model = Computer(manufacturer=family.manufacturer, model_name='IBM System/360 Model 50')
        db.add(model); db.commit(); source_id, target_id = model.id, family.id
    result = client.post(PREFIX + '/preview', json={'entity': 'computer', 'source_id': source_id, 'target_id': target_id})
    assert result.status_code == 409
    assert client.get('/api/computers').json()['total'] == 11
    assert client.get(PREFIX + '/duplicates').json() == []


def test_import_coverage_and_missing_prices_preserve_existing_price(client):
    with SessionLocal() as db:
        c = db.scalar(select(Computer).where(Computer.model_name == 'Apple II'))
        c.releases[0].price = 456; c.releases[0].currency = 'USD'; db.commit(); cid = c.id
    data = record(manufacturer='Apple Computer', model_name='Apple II', releases=[{'market': 'Globale', 'release_date': '1977'}])
    response = upload(client, [data]); job = response.json()['id']
    assert response.json()['data_coverage'] == {'records_with_source': 1, 'prices': 0}
    apply(client, job)
    c = client.get(f'/api/computers/{cid}').json()
    assert c['sources'] and c['releases'][0]['price'] == 456
    assert c['releases'][0]['currency'] == 'USD'
