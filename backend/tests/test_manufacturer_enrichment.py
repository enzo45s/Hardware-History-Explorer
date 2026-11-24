import json
from datetime import date

import pytest
from sqlalchemy import select, func

from app.main import SessionLocal
from app.models import Manufacturer, Source, manufacturer_source, Computer
from app.import_models import CatalogReconciliation
from app.manufacturer_enrichment import apply_enrichment, load_package, AUDIT_ENTITY, PACKAGE
from fastapi import HTTPException


def package(tmp_path, fields=None, names=None):
    fields = fields or {'description': 'Testo italiano sintetico.', 'founded': '1980',
                        'logo_url': 'https://example.org/logo.png', 'logo_author': 'Autore sintetico',
                        'description_author': 'Autore del testo sintetico'}
    citation = {'title': 'Synthetic company documentation', 'url': 'https://example.org/history', 'publisher': 'Synthetic publisher'}
    record = {'manufacturer_names': names or ['Synthetic Maker'], 'fields': fields,
              'field_sources': {field: [citation['url']] for field in fields}, 'sources': [citation]}
    path = tmp_path / 'manufacturers.json'
    path.write_text(json.dumps({'version': 'synthetic-v1', 'researched_on': '2026-11-23', 'records': [record]}))
    return path


def test_missing_only_exact_identity_sources_audit_and_repeat(tmp_path):
    path = package(tmp_path)
    with SessionLocal() as db:
        maker = Manufacturer(name='Synthetic Maker', country='Italia')
        other = Manufacturer(name='Synthetic Maker Subsidiary')
        db.add_all([maker, other]); db.commit(); mid = maker.id
        report = apply_enrichment(db, path=path)
        assert report['updated'] == 1 and report['matched'] == 1
        assert report['unmatched'] == [{'id': other.id, 'name': other.name}]
        db.refresh(maker)
        assert maker.country == 'Italia' and maker.founded == date(1980, 1, 1)
        assert maker.founded_precision == 'year' and other.description is None
        assert db.scalar(select(func.count()).select_from(Manufacturer)) == 2
        link = db.execute(select(manufacturer_source)).mappings().one()
        assert link['verification_status'] == 'pending'
        assert 'description' in json.loads(link['evidence'])['fields']
        audit = db.scalar(select(CatalogReconciliation).where(CatalogReconciliation.entity == AUDIT_ENTITY))
        assert audit.snapshot['changes'][0]['before']['description'] is None
        assert audit.snapshot['changes'][0]['applied']['logo_author'] == 'Autore sintetico'
        db.commit()
        assert apply_enrichment(db, path=path)['already_applied']
        assert apply_enrichment(db, path=path, explicit=True)['updated'] == 0
        assert db.scalar(select(func.count()).select_from(Source)) == 1
        assert db.scalar(select(func.count()).select_from(Computer)) == 0
        maker.description = None; db.commit()
        assert apply_enrichment(db, path=path)['already_applied']
        db.refresh(maker); assert maker.description is None
        assert apply_enrichment(db, path=path, explicit=True)['updated'] == 1
        db.refresh(maker); assert maker.id == mid and maker.description


def test_existing_text_logo_and_dates_are_protected_without_false_credits(tmp_path):
    path = package(tmp_path)
    with SessionLocal() as db:
        maker = Manufacturer(name='Synthetic Maker', description='Testo curato a mano.', logo_url='https://example.org/manual.png',
                             founded=date(1979, 5, 3))
        db.add(maker); db.commit()
        result = apply_enrichment(db, path=path)
        assert result['updated'] == 0
        db.refresh(maker)
        assert maker.description == 'Testo curato a mano.' and maker.logo_url.endswith('manual.png')
        assert maker.description_author is None and maker.logo_author is None
        assert maker.founded == date(1979, 5, 3) and maker.sources == []


def test_existing_date_conflict_preserves_curated_date_and_imports_other_fields(tmp_path):
    path = package(tmp_path, {'founded': '1980', 'country': 'Italia'})
    with SessionLocal() as db:
        maker = Manufacturer(name='Synthetic Maker', ceased=date(1979, 1, 1), ceased_precision='year')
        db.add(maker); db.commit()
        result = apply_enrichment(db, path=path)
        assert result['updated'] == 1 and result['conflicts'][0]['fields'] == {'founded': '1980'}
        db.refresh(maker)
        assert maker.country == 'Italia' and maker.founded is None and maker.ceased.year == 1979


@pytest.mark.parametrize('change', ['missing_source', 'bad_url', 'duplicate_identity', 'invalid_chronology'])
def test_invalid_package_does_not_change_records(tmp_path, change):
    path = package(tmp_path); data = json.loads(path.read_text())
    if change == 'missing_source': data['records'][0]['field_sources'] = {}
    if change == 'bad_url': data['records'][0]['fields']['logo_url'] = 'file:///tmp/logo'
    if change == 'duplicate_identity': data['records'].append(data['records'][0])
    if change == 'invalid_chronology':
        data['records'][0]['fields']['ceased'] = '1970'
        data['records'][0]['field_sources']['ceased'] = ['https://example.org/history']
    path.write_text(json.dumps(data))
    with SessionLocal() as db:
        db.add(Manufacturer(name='Synthetic Maker')); db.commit()
        with pytest.raises((ValueError, HTTPException)): apply_enrichment(db, path=path)
        db.rollback()
        assert db.scalar(select(Manufacturer)).description is None
        assert db.scalar(select(func.count()).select_from(Source)) == 0
        assert db.scalar(select(func.count()).select_from(CatalogReconciliation)) == 0


def test_bundled_research_is_cited_and_avoids_known_namesakes():
    data, checksum = load_package()
    assert len(checksum) == 64 and len(data['records']) == 184
    rows = {r['manufacturer_names'][0]: r for r in data['records']}
    assert rows['Unitron Eletronica']['fields']['country'] == 'Brasile'
    assert not any('id=404' in s['url'] for s in rows['Unitron Eletronica']['sources'])
    assert rows['Daewoo']['fields']['founded'] == '1971'
    assert 'winia' not in rows['Daewoo']['fields'].get('logo_url', '').lower()
    assert 'founded' not in rows['National']['fields']  # Brand and parent company dates differ.
    assert 'founded' not in rows['Tesa Etikett']['fields']
    assert not rows['Alex Zhabin']['fields']  # No fabricated biography from unrelated namesakes.
    for name, suffix in [('Fenner', 'Fenner'), ('Sharp / Epcom', 'Sharp_(Epcom)')]:
        assert rows[name]['field_sources']['description'] == ['https://www.msx.org/wiki/Category:' + suffix]
        assert 'description_author' not in rows[name]['fields']  # These summaries do not derive from Wikipedia.
    assert 'https://www.msx.org/wiki/Category:Sakhr/Al_Alamiah' in rows['Sakhr']['field_sources']['description']


def test_albert_commons_logo_preserves_profile_and_records_image_provenance(client):
    path = PACKAGE.with_name('manufacturer-albert-logo-v1.json')
    package_data, _ = load_package(path)
    record = package_data['records'][0]
    assert len(package_data['records']) == 1
    assert record['research']['commons_revision'] == 1305857945
    assert record['research']['credit'] == "Took from the box shown in system's pictures."
    with SessionLocal() as db:
        historical = Source(title='Synthetic existing history', url='https://example.org/albert-history')
        maker = Manufacturer(name='Albert Computers, Inc.', description='Testo aziendale curato.',
                             country='Stati Uniti', sources=[historical])
        other = Manufacturer(name='Unrelated synthetic maker', logo_url='https://example.org/curated.png')
        db.add_all([maker, other]); db.commit(); mid = maker.id
        result = apply_enrichment(db, path=path, explicit=True)
        assert result['updated'] == 1 and set(result['fields_updated']) == set(record['fields'])
        db.refresh(maker)
        assert maker.description == 'Testo aziendale curato.' and maker.country == 'Stati Uniti'
        assert maker.founded is None  # Upload time does not become company history.
        assert maker.logo_author == 'ChatGPT, Vincenzo Colacicco'
        assert maker.logo_license_url == 'https://creativecommons.org/publicdomain/zero/1.0/'
        assert maker.logo_url.endswith('/1/13/Albert_Computers_Inc._Logo.png') and '?' not in maker.logo_url
        assert maker.logo_source_url == 'https://commons.wikimedia.org/wiki/File:Albert_Computers_Inc._Logo.png'
        assert historical in maker.sources and len(maker.sources) == 2
        assert other.logo_url == 'https://example.org/curated.png'
        link = db.execute(select(manufacturer_source).where(manufacturer_source.c.target_id == mid,
                          manufacturer_source.c.source_id != historical.id)).mappings().one()
        assert link['verification_status'] == 'pending'
        assert set(json.loads(link['evidence'])['fields']) == set(record['fields'])
        audit = db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity == AUDIT_ENTITY)
                           .order_by(CatalogReconciliation.id.desc())).first()
        assert audit.snapshot['changes'][0]['research']['uploader'] == 'Enzo45s'
        source_count = db.scalar(select(func.count()).select_from(Source))
        db.commit()
        assert apply_enrichment(db, path=path, explicit=True)['updated'] == 0
        assert db.scalar(select(func.count()).select_from(Source)) == source_count
    profile = client.get(f'/api/manufacturers/{mid}/profile').json()
    assert profile['logo_source_url'] == record['fields']['logo_source_url']
    assert profile['logo_author'] == record['fields']['logo_author']
    assert len(profile['sources']) == 2


@pytest.mark.parametrize('name', ['Unitron Eletronica', 'Unitron Eletrônica'])
def test_unitron_commons_logo_keeps_history_credits_and_distinct_namesakes(client, name):
    path = PACKAGE.with_name('manufacturer-unitron-logo-v1.json')
    data, _ = load_package(path)
    record = data['records'][0]
    assert len(data['records']) == 1 and set(record['fields']) == {
        'logo_url', 'logo_author', 'logo_license', 'logo_license_url', 'logo_source_url'}
    assert record['research']['commons_revision'] == 1305896637
    assert 'Digitally reconstructed' in record['research']['credit']
    with SessionLocal() as db:
        history = Source(title='Synthetic Unitron history', url='https://example.org/unitron-history')
        maker = Manufacturer(name=name, country='Brasile', description='Storia aziendale curata.', sources=[history])
        german = Manufacturer(name='Unitron', country='Germania')
        project = Manufacturer(name='bootleg (Unitron)')
        computer = Computer(manufacturer=maker, model_name='Synthetic existing Unitron model')
        db.add_all([maker, german, project, computer]); db.commit(); mid = maker.id
        result = apply_enrichment(db, path=path, explicit=True)
        assert result['updated'] == result['matched'] == 1
        db.refresh(maker)
        assert maker.description == 'Storia aziendale curata.' and maker.country == 'Brasile'
        assert maker.founded is None and maker.ceased is None
        assert maker.logo_url == record['fields']['logo_url'] and '?' not in maker.logo_url
        assert maker.logo_author == 'ChatGPT, Vincenzo Colacicco'
        assert maker.logo_license_url == 'https://creativecommons.org/publicdomain/zero/1.0/'
        assert len(maker.sources) == 2 and history in maker.sources
        assert german.logo_url is None and project.logo_url is None
        assert computer.manufacturer_id == mid
        link = db.execute(select(manufacturer_source).where(manufacturer_source.c.target_id == mid,
                          manufacturer_source.c.source_id != history.id)).mappings().one()
        assert link['verification_status'] == 'pending'
        assert set(json.loads(link['evidence'])['fields']) == set(record['fields'])
        audit = db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity == AUDIT_ENTITY)).one()
        assert audit.snapshot['changes'][0]['research']['uploader'] == 'Enzo45s'
        count = db.scalar(select(func.count()).select_from(Source)); db.commit()
        assert apply_enrichment(db, path=path, explicit=True)['updated'] == 0
        assert db.scalar(select(func.count()).select_from(Source)) == count
    profile = client.get(f'/api/manufacturers/{mid}/profile').json()
    assert profile['logo_source_url'] == record['fields']['logo_source_url']
    assert profile['logo_author'] == record['fields']['logo_author']
    assert profile['computer_count'] == 1 and len(profile['sources']) == 2


def test_report_apply_endpoints_and_manual_rewrite_credit_reset(client):
    maker = client.post('/api/manufacturers', json={'name': 'Acorn'}).json()
    response = client.post('/api/admin/manufacturers/enrichment/apply')
    assert response.status_code == 200, response.text
    profile = client.get(f"/api/manufacturers/{maker['id']}/profile").json()
    assert profile['description'] and profile['description_author'] and profile['sources']
    report = client.get('/api/admin/manufacturers/enrichment/report').json()
    assert report['total'] > 0 and next(m for m in report['manufacturers'] if m['id'] == maker['id'])['research']
    assert client.put(f"/api/manufacturers/{maker['id']}", json={'name': 'Acorn', 'description': 'Testo riveduto a mano.'}).status_code == 200
    profile = client.get(f"/api/manufacturers/{maker['id']}").json()
    assert profile['description_author'] is None and profile['description_source_url'] is None
    assert profile['sources']


@pytest.mark.parametrize('curated', [True, False])
def test_merge_keeps_attribution_bound_to_its_text_and_logo(curated):
    from app.importing.reconcile import prepare, apply
    with SessionLocal() as db:
        source = Manufacturer(name='Apple Computer', description='Testo documentato sintetico.',
                              description_author='Autore sintetico', description_source_url='https://example.org/text',
                              logo_url='https://example.org/source.png', logo_author='Autore del logo sintetico')
        target = Manufacturer(name='Apple', description='Testo curato.' if curated else None,
                              logo_url='https://example.org/curated.png' if curated else None)
        db.add_all([source, target]); db.commit(); target_id = target.id; source_id = source.id
        _, _, _, preview = prepare(db, 'manufacturer', source.id, target.id)
        apply(db, 'manufacturer', source.id, target.id, preview['token'], 'Revisione sintetica')
        db.refresh(target)
        assert target.id == target_id
        if curated:
            assert target.description == 'Testo curato.' and target.logo_url.endswith('curated.png')
            assert target.description_author is None and target.logo_author is None
        else:
            assert target.description == 'Testo documentato sintetico.' and target.description_author == 'Autore sintetico'
            assert target.logo_url.endswith('source.png') and target.logo_author == 'Autore del logo sintetico'
        audit = db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity == 'manufacturer')).one()
        assert next(m for m in audit.snapshot['manufacturer'] if m['id'] == source_id)['description_author'] == 'Autore sintetico'
