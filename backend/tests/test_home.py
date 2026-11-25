from datetime import date
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app, SessionLocal
from app.models import Computer, ComputerImage, Manufacturer, Market, Release, Source
from app.import_models import CatalogReconciliation


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr('app.main.seed', lambda db: None)
    with TestClient(app) as client:
        yield client


def test_empty_home_does_not_create_demo_records(client):
    assert client.get('/api/home').json() == {
        'summary': {'systems': 0, 'manufacturers': 0}, 'spotlight': None, 'featured': []}
    with SessionLocal() as db:
        db.add(Manufacturer(name='Synthetic maker without systems')); db.commit()
    assert client.get('/api/home').json() == {
        'summary': {'systems': 0, 'manufacturers': 1}, 'spotlight': None, 'featured': []}


def test_real_ids_curated_covers_partial_dates_and_sourced_text_are_preserved(client):
    with SessionLocal() as db:
        makers = [Manufacturer(name=name) for name in ('Unrelated namesake', 'Commodore', 'Olivetti', 'Apple', 'IBM')]
        db.add_all(makers)
        market = Market(name='Synthetic test market'); db.add(market)
        wrong = [Computer(model_name='Commodore 64', manufacturer=makers[0]) for _ in range(15)]
        rows = [Computer(model_name=model, manufacturer=maker, description='Synthetic sourced introduction.')
                for model, maker in zip(('Commodore 64', 'Programma 101', 'Apple ][', 'IBM PC 5150'), makers[1:])]
        db.add_all([*wrong, *rows]); db.flush()
        source = Source(title='Synthetic text source', url='https://example.org/history')
        rows[0].sources.append(source)
        rows[0].images.extend([
            ComputerImage(remote_url='https://example.org/old.jpg', display_order=0),
            ComputerImage(remote_url='https://example.org/curated.jpg', thumbnail_url='https://example.org/thumb.jpg',
                          author='Synthetic photographer', license_name='Synthetic conditions',
                          source_url='https://example.org/photo', license_url='https://example.org/terms',
                          is_primary=True, display_order=2)])
        rows[0].releases.append(Release(market=market, release_date=date(1982, 1, 1), release_precision='year'))
        rows[1].releases.append(Release(market=market, release_date=date(1965, 10, 1), release_precision='month'))
        db.add(CatalogReconciliation(entity='admin_retirement', source_id=0, target_id=0, note='Synthetic retained credit',
            snapshot={'description_attributions': [{'computer_id': rows[0].id,
                'description_sha256': hashlib.sha256(rows[0].description.encode()).hexdigest(),
                'title': 'Synthetic Wikipedia attribution', 'url': source.url,
                'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/',
                'method': 'estratto introduttivo italiano'}]}))
        db.commit(); ids = [c.id for c in rows]
        counts = {table.__tablename__: db.scalar(select(func.count()).select_from(table))
                  for table in (Computer, Manufacturer, ComputerImage, Release, Source)}
    response = client.get('/api/home'); assert response.status_code == 200
    home = response.json()
    assert home['summary'] == {'systems': 19, 'manufacturers': 5}
    assert home['spotlight']['id'] == ids[0]
    assert [c['id'] for c in home['featured']] == ids[1:]
    assert home['spotlight']['image_url'] == 'https://example.org/thumb.jpg'
    assert home['spotlight']['cover']['url'] == 'https://example.org/curated.jpg'
    assert home['spotlight']['cover']['author'] == 'Synthetic photographer'
    assert home['spotlight']['cover']['license_url'] == 'https://example.org/terms'
    assert home['spotlight']['description_attribution']['url'] == 'https://example.org/history'
    assert home['featured'][0]['first_release'] == '1965-10'
    assert home['featured'][2]['year'] is None and home['featured'][2]['cover'] is None
    assert all(client.get(f'/api/computers/{id}').status_code == 200 for id in ids)
    with SessionLocal() as db:
        assert counts == {table.__tablename__: db.scalar(select(func.count()).select_from(table))
                          for table in (Computer, Manufacturer, ComputerImage, Release, Source)}


def test_missing_or_deleted_editorial_choices_use_bounded_actual_archive(client):
    with SessionLocal() as db:
        maker = Manufacturer(name='Synthetic alternative maker')
        rows = [Computer(manufacturer=maker, model_name=f'Alternative system {i:02d}') for i in range(20)]
        db.add_all(rows); db.flush()
        rows[-1].images.append(ComputerImage(remote_url='https://example.org/last.jpg'))
        db.commit(); first = rows[-1].id
    home = client.get('/api/home').json()
    assert home['summary'] == {'systems': 20, 'manufacturers': 1}
    assert len(home['featured']) == 3 and home['spotlight']['id'] == first
    assert first not in {c['id'] for c in home['featured']}
    assert len({c['id'] for c in home['featured']}) == 3
    assert all(c['model_name'].startswith('Alternative system') for c in home['featured'])
    with SessionLocal() as db:
        db.delete(db.get(Computer, first)); db.commit()
    updated = client.get('/api/home').json()
    assert updated['summary']['systems'] == 19
    assert len(updated['featured']) == 3 and first not in {c['id'] for c in updated['featured']}
    assert updated['spotlight']['id'] != first
    assert all(c['cover'] is None and c['image_url'] is None for c in updated['featured'])


@pytest.mark.parametrize('count', [1, 2, 3])
def test_small_archive_is_not_padded_or_repeated(client, count):
    with SessionLocal() as db:
        maker = Manufacturer(name='Only maker')
        db.add_all([Computer(model_name=f'Existing system {i}', manufacturer=maker) for i in range(count)]); db.commit()
    home = client.get('/api/home').json()
    assert len(home['featured']) == count - 1
    ids = [home['spotlight']['id'], *(c['id'] for c in home['featured'])]
    assert len(set(ids)) == count


def test_missing_c64_keeps_the_three_collection_choices_when_another_showcase_exists(client):
    with SessionLocal() as db:
        rows = [Computer(model_name=model, manufacturer=Manufacturer(name=maker))
                for maker, model in [('Olivetti', 'Programma 101'), ('Apple Computer', 'Apple II'),
                                     ('IBM', 'IBM PC 5150'), ('Synthetic other maker', 'Other actual system')]]
        db.add_all(rows); db.commit(); ids = [c.id for c in rows]
    home = client.get('/api/home').json()
    assert home['spotlight']['id'] == ids[3]
    assert [c['id'] for c in home['featured']] == ids[:3]
