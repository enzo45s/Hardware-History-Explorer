"""Synthetic Commons metadata only: no real photographs or remote requests."""
from datetime import datetime, timedelta, timezone
import asyncio
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app import main, photo_jobs
from app.main import SessionLocal
from app.models import Computer, ComputerImage
from app.photo_jobs import PhotoJob, PhotoItem


def page(name='First', rank=1, licence='CC BY-SA 4.0', author='Alice'):
    return {'title': f'File:{name}.jpg', 'index': rank, 'imageinfo': [{
        'url': f'https://upload.wikimedia.org/{name}.jpg',
        'thumburl': f'https://upload.wikimedia.org/thumb/{name}.jpg',
        'descriptionurl': f'https://commons.wikimedia.org/wiki/File:{name}.jpg',
        'mime': 'image/jpeg', 'extmetadata': {'Artist': {'value': author},
        'LicenseShortName': {'value': licence},
        'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by-sa/4.0/'}}}]}


@pytest.fixture
def clock(monkeypatch):
    timestamp = [datetime(2030, 1, 1, tzinfo=timezone.utc)]
    monkeypatch.setattr(photo_jobs, 'now', lambda: timestamp[0])
    return timestamp


def single_queue(client):
    job = client.post('/api/admin/photos').json()
    with SessionLocal() as db:
        rows = db.scalars(select(PhotoItem).where(PhotoItem.job_id == job['id']).order_by(PhotoItem.position)).all()
        for row in rows[1:]: db.delete(row)
        cid = rows[0].computer_id
        db.commit()
    return job['id'], cid


def test_first_relevant_reusable_result_and_attribution(client, monkeypatch, clock):
    seen = []
    async def search(query, limit):
        seen.append(query)
        return {'900': page('Second', 2), '10': page('First', 1), '1': page('Unlicensed', 0, 'Unknown')}
    monkeypatch.setattr(main, 'search_pages', search)
    jid, cid = single_queue(client)
    result = client.post(f'/api/admin/photos/{jid}/step')
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'completed' and result.json()['counts'] == {'added': 1}
    c = client.get(f'/api/computers/{cid}').json(); image = c['images'][0]
    assert image['url'].endswith('/First.jpg') and image['author'] == 'Alice'
    assert image['license_name'] == 'CC BY-SA 4.0' and image['license_url']
    assert image['source_url'].endswith('File:First.jpg') and image['is_primary']
    assert image['caption'].startswith('Scelta automatica Commons') and seen == [c['model_name']]
    assert client.post(f'/api/admin/photos/{jid}/step').json()['counts'] == {'added': 1}
    assert client.post(f'/api/admin/photos/{jid}/pause').json()['status'] == 'completed'
    assert client.post(f'/api/admin/photos/{jid}/resume').json()['status'] == 'completed'
    assert len(client.get(f'/api/computers/{cid}/images').json()) == 1
    assert client.post('/api/admin/photos').json()['total'] == 9
    assert client.delete(f"/api/computers/{cid}/images/{image['id']}").status_code == 204


def test_durable_unique_queue_excludes_manual_and_legacy_covers(client):
    client.post('/api/computers/1/images', json={'image_url': 'https://example.org/manual.jpg'})
    with SessionLocal() as db:
        db.get(Computer, 2).image_url = 'https://example.org/legacy.jpg'; db.commit()
    first = client.post('/api/admin/photos').json(); jid = first['id']
    assert first['total'] == 8 and client.post('/api/admin/photos').json()['id'] == jid
    assert client.get('/api/admin/photos').json()['missing'] == 8
    assert client.post(f'/api/admin/photos/{jid}/pause').json()['status'] == 'paused'
    with SessionLocal() as db: assert db.get(PhotoJob, jid).status == 'paused'
    assert client.post(f'/api/admin/photos/{jid}/step').json()['counts'] == {'pending': 8}
    assert client.post(f'/api/admin/photos/{jid}/resume').json()['status'] == 'ready'


def test_network_error_retains_current_model_and_respects_retry_after(client, monkeypatch, clock):
    jid = client.post('/api/admin/photos').json()['id']; calls = []
    async def unavailable(query, limit):
        calls.append(query); raise HTTPException(503, 'Wikimedia occupato', headers={'Retry-After': '60'})
    monkeypatch.setattr(main, 'search_pages', unavailable)
    response = client.post(f'/api/admin/photos/{jid}/step').json()
    assert response['status'] == 'paused' and response['counts'] == {'pending': 10}
    assert response['error'] == 'Wikimedia occupato'
    client.post(f'/api/admin/photos/{jid}/resume')
    assert client.post(f'/api/admin/photos/{jid}/step').status_code == 429
    clock[0] += timedelta(seconds=60)
    async def empty(query, limit): calls.append(query); return {}
    monkeypatch.setattr(main, 'search_pages', empty)
    response = client.post(f'/api/admin/photos/{jid}/step').json()
    assert calls[0] == calls[1] and response['counts'] == {'no_match': 1, 'pending': 9}
    assert response['error'] is None
    assert client.post(f'/api/admin/photos/{jid}/step').status_code == 429
    clock[0] += timedelta(seconds=2)
    assert client.post(f'/api/admin/photos/{jid}/step').json()['counts'] == {'no_match': 2, 'pending': 8}


def test_manual_photo_added_during_search_is_kept(client, monkeypatch, clock):
    jid, cid = single_queue(client)
    async def search(query, limit):
        with SessionLocal() as db:
            db.add(ComputerImage(computer_id=cid, remote_url='https://example.org/manual.jpg', is_primary=True)); db.commit()
        return {'1': page()}
    monkeypatch.setattr(main, 'search_pages', search)
    assert client.post(f'/api/admin/photos/{jid}/step').json()['counts'] == {'skipped': 1}
    assert client.get(f'/api/computers/{cid}/images').json()[0]['url'] == 'https://example.org/manual.jpg'


def test_busy_lease_recovers_after_expiry(client, monkeypatch, clock):
    jid, cid = single_queue(client)
    async def search(query, limit): return {'1': page()}
    monkeypatch.setattr(main, 'search_pages', search)
    with SessionLocal() as db:
        job = db.get(PhotoJob, jid); job.lease_token = 'other'; job.lease_until = clock[0] + timedelta(seconds=90); db.commit()
    assert client.post(f'/api/admin/photos/{jid}/step').status_code == 429
    clock[0] += timedelta(seconds=91)
    assert client.post(f'/api/admin/photos/{jid}/step').json()['counts'] == {'added': 1}


def test_reset_during_request_archives_queue(client, monkeypatch, clock):
    jid, cid = single_queue(client)
    async def search(query, limit):
        def reset():
            preview = client.get('/api/admin/archive/preview').json()
            response = client.post('/api/admin/archive/reset', json={'token': preview['token'], 'confirmation': 'SVUOTA ARCHIVIO',
                'backup_confirmed': True, 'note': 'Disposable queue reset test'})
            assert response.status_code == 200, response.text
        await asyncio.to_thread(reset)
        return {'1': page()}
    monkeypatch.setattr(main, 'search_pages', search)
    response = client.post(f'/api/admin/photos/{jid}/step')
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'archived'
    assert client.get('/api/computers').json()['total'] == 0


@pytest.mark.parametrize('licence,author,expected', [('CC BY-SA 4.0','Alice',True), ('CC BY 3.0','Alice',True),
    ('CC0','Alice',True), ('Public domain','Alice',True), ('CC BY-NC 4.0','Alice',False),
    ('CC BY-ND 4.0','Alice',False), ('Unknown','Alice',False), ('CC BY 4.0','',False)])
def test_metadata_requirements(licence, author, expected):
    assert photo_jobs.reusable({'license_name':licence,'author':author,'source_url':'https://commons.wikimedia.org/wiki/File:Test.jpg'}) is expected


def test_repeatable_migration_preserves_catalog_and_queue(client):
    from migrations.photo_jobs import migrate
    jid, cid = single_queue(client)
    migrate(main.engine); migrate(main.engine)
    assert client.get('/api/admin/photos').json()['job']['id'] == jid
    assert client.get(f'/api/computers/{cid}').status_code == 200
