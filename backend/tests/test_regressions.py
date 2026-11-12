from datetime import date

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.main import SessionLocal, engine
from app.models import Computer, ComputerImage, Release, Review


@pytest.mark.parametrize('query', [
    'year_from=-1', 'year_from=0', 'year_from=10000',
    'year_to=-1', 'year_to=0', 'year_to=10000', 'year_from=1980&year_to=1970',
])
def test_invalid_years_are_client_errors(client, query):
    assert client.get('/api/computers?' + query).status_code == 422


def test_years_match_first_release_and_paginate(client):
    with SessionLocal() as db:
        db.add(Release(computer_id=1, market_id=1, release_date=date(1978, 1, 1)))
        db.commit()
    rows = client.get('/api/computers?year_from=1970&year_to=1980').json()
    assert 1 not in [item['id'] for item in rows['items']]
    first = client.get('/api/computers?limit=3').json()
    next_page = client.get('/api/computers?limit=3&offset=3').json()
    assert first['total'] == next_page['total'] == 10
    assert len(first['items']) == len(next_page['items']) == 3
    assert not ({x['id'] for x in first['items']} & {x['id'] for x in next_page['items']})
    assert client.get('/api/computers?year_from=1&year_to=9999').json()['total'] == 10


def test_comparison_preserves_selection_and_rejects_missing_ids(client):
    assert [c['id'] for c in client.get('/api/compare?ids=2,1,2').json()] == [2, 1]
    assert client.get('/api/compare?ids=1,999999').status_code == 404


@pytest.mark.parametrize('field,value', [
    ('publisher', 'x' * 181), ('url', 'https://example.org/' + 'x' * 800),
    ('source_type', 'x' * 61), ('url', 'https://'), ('url', 'javascript:alert(1)'),
])
def test_source_validation_matches_database(client, field, value):
    assert client.post('/api/sources', json={'title': 'Test source', field: value}).status_code == 422


def test_foreign_keys_are_enforced(client):
    with SessionLocal() as db:
        db.add(ComputerImage(computer_id=999999, remote_url='https://example.org/a.jpg'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    if engine.dialect.name == 'sqlite':
        with engine.connect() as conn:
            assert conn.scalar(text('PRAGMA foreign_keys')) == 1


def test_review_requires_a_valid_scale(client):
    with SessionLocal() as db:
        db.add(Review(computer_id=1, publication='Test', score=999, max_score=None))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(Review(computer_id=1, publication='Test', score=4, max_score=5))
        db.commit()


@pytest.mark.parametrize('value', ['https://', 'https://user:pass@example.org/pic.jpg', 'http://example.org/a.jpg'])
def test_photo_urls_must_be_valid_https(client, value):
    assert client.post('/api/computers/1/images', json={'image_url': value}).status_code == 422


def test_webp_mime_without_system_mapping(client, monkeypatch):
    import mimetypes
    from test_images import png_bytes
    monkeypatch.delitem(mimetypes.types_map, '.webp', raising=False)
    # The explicit media response must not depend on the machine's MIME registry.
    r = client.post('/api/computers/1/images/upload', files={'file': ('a.png', png_bytes(), 'image/png')})
    assert r.status_code == 201
    assert client.get(r.json()['url']).headers['content-type'] == 'image/webp'


def test_commons_failure_is_a_readable_gateway_error(client, monkeypatch):
    import app.main as module

    class Unavailable:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, *args, **kwargs): raise httpx.ConnectError('offline')

    monkeypatch.setattr(module.httpx, 'AsyncClient', Unavailable)
    r = client.get('/api/images/search?q=Altair')
    assert r.status_code == 502
    assert 'Wikimedia' in r.json()['detail']
