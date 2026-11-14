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
    assert image['caption'].startswith('Scelta automatica Commons') and seen == [c['photo_search_query']]
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


def test_rejected_query_gets_one_persisted_simplification_then_recovers(client, monkeypatch, clock):
    jid, cid = single_queue(client)
    with SessionLocal() as db:
        row = db.scalar(select(PhotoItem).where(PhotoItem.job_id == jid))
        row.query = 'Apple ]['; db.commit()
    calls = []
    async def search(query, limit):
        calls.append(query)
        if query == 'Apple ][':
            raise HTTPException(422, 'Invalid query (cirrussearch-parse-error)')
        return {'1': page()}
    monkeypatch.setattr(main, 'search_pages', search)
    first = client.post(f'/api/admin/photos/{jid}/step').json()
    assert first['status'] == 'ready' and first['current']['query'] == 'Apple II'
    assert first['counts'] == {'pending': 1}
    assert client.get('/api/admin/photos').json()['job']['current']['query'] == 'Apple II'
    assert client.post(f'/api/admin/photos/{jid}/step').status_code == 429
    clock[0] += timedelta(seconds=2)
    second = client.post(f'/api/admin/photos/{jid}/step').json()
    assert second['status'] == 'completed' and second['counts'] == {'added': 1}
    assert calls == ['Apple ][', 'Apple II']


def test_permanent_failure_of_simple_query_does_not_block_next_model(client, monkeypatch, clock):
    jid = client.post('/api/admin/photos').json()['id']
    with SessionLocal() as db:
        row = db.scalar(select(PhotoItem).where(PhotoItem.job_id == jid).order_by(PhotoItem.position))
        row.query = 'Plain model'; db.commit()
    calls = []
    async def invalid(query, limit):
        calls.append(query)
        raise HTTPException(422, 'Invalid query')
    monkeypatch.setattr(main, 'search_pages', invalid)
    first = client.post(f'/api/admin/photos/{jid}/step').json()
    assert first['status'] == 'ready' and first['counts']['search_error'] == 1
    assert first['current']['model_name'] != first['recent'][0]['model_name']
    clock[0] += timedelta(seconds=2)
    client.post(f'/api/admin/photos/{jid}/step')
    assert len(calls) == 2 and calls[0] != calls[1]


def test_current_query_edit_and_skip_preserve_cooldown_and_do_not_change_catalog(client, monkeypatch, clock):
    jid = client.post('/api/admin/photos').json()['id']
    async def unavailable(*args):
        raise HTTPException(503, 'Commons busy', headers={'Retry-After': '60'})
    monkeypatch.setattr(main, 'search_pages', unavailable)
    paused = client.post(f'/api/admin/photos/{jid}/step').json()
    current = paused['current']; before = client.get(f"/api/computers/{current['computer_id']}").json()
    edited = client.post(f'/api/admin/photos/{jid}/query', json={'item_id': current['id'], 'query': 'IBM 360'}).json()
    assert edited['current']['query'] == 'IBM 360' and edited['error'] is None
    assert edited['next_request_at'] == paused['next_request_at']
    client.post(f'/api/admin/photos/{jid}/resume')
    assert client.post(f'/api/admin/photos/{jid}/step').status_code == 429
    skipped = client.post(f'/api/admin/photos/{jid}/skip', json={'item_id': current['id']}).json()
    assert skipped['counts']['skipped'] == 1 and skipped['current']['id'] != current['id']
    assert skipped['next_request_at'] == paused['next_request_at']
    assert client.get(f"/api/computers/{current['computer_id']}").json() == before
    assert client.post(f'/api/admin/photos/{jid}/skip', json={'item_id': current['id']}).status_code == 409


def test_current_edit_and_skip_cannot_race_an_inflight_request_or_archived_job(client, clock):
    jid, cid = single_queue(client)
    state = client.get('/api/admin/photos').json()['job']; item_id = state['current']['id']
    with SessionLocal() as db:
        job = db.get(PhotoJob, jid); job.lease_token = 'inflight'; job.lease_until = clock[0] + timedelta(seconds=90); db.commit()
    assert client.post(f'/api/admin/photos/{jid}/skip', json={'item_id': item_id}).status_code == 409
    assert client.post(f'/api/admin/photos/{jid}/query', json={'item_id': item_id, 'query': 'Other search'}).status_code == 409
    clock[0] += timedelta(seconds=91)
    assert client.post(f'/api/admin/photos/{jid}/query', json={'item_id': item_id, 'query': 'Other search'}).status_code == 200
    with SessionLocal() as db:
        job = db.get(PhotoJob, jid); job.status = 'archived'; job.active_key = None; db.commit()
    assert client.get('/api/admin/photos').json()['job']['current'] is None
    assert client.post(f'/api/admin/photos/{jid}/query', json={'item_id': item_id, 'query': 'Other search'}).status_code == 409


@pytest.mark.parametrize('value,expected', [('Apple ][', 'Apple II'), ('Apple //e', 'Apple IIe'),
    ('Apple ///', 'Apple III'), ('Apple - ][', 'Apple - II'), ('Apple - //e', 'Apple - IIe'),
    ('Apple - ///', 'Apple - III'), ('ZX Spectrum +2', 'ZX Spectrum Plus 2'), ('IBM (360): test', 'IBM 360 test')])
def test_fallback_retains_distinguishing_model_tokens(value, expected):
    assert photo_jobs.simple_query(value) == expected
    assert photo_jobs.simple_query(expected) == expected


@pytest.mark.parametrize('maker,model,expected', [
    ('Apple Computer', 'Apple Macintosh 128K', 'Apple - Macintosh 128K'),
    ('Apple Computer, Inc.', 'Apple Computer II', 'Apple - II'),
    ('Apple', 'Apple ][', 'Apple - ]['),
    ('IBM', 'IBM PC 5150', 'IBM - PC 5150'),
    ('International Business Machines', 'IBM System/360', 'IBM - System/360'),
    ('Commodore Business Machines', 'Commodore 64', 'Commodore - 64'),
    ('Acorn', 'Acornsoft 123', 'Acorn - Acornsoft 123'),
    ('Sinclair', 'ZX Spectrum +2', 'Sinclair - ZX Spectrum +2'),
    ('', 'Unknown model', 'Unknown model'),
])
def test_brand_model_query_preserves_model_and_avoids_repeated_brand(maker, model, expected):
    assert photo_jobs.photo_query(maker, model) == expected
    assert len(photo_jobs.photo_query('M' * 180, 'Model' * 36)) <= 90


def restart_queue(client, previous=None):
    response = client.post('/api/admin/photos/restart', json={'expected_job_id': previous})
    assert response.status_code == 201, response.text
    return response.json()


def test_restart_uses_current_1105_computers_including_existing_photos(client, clock):
    old_photo = client.post('/api/computers/1/images', json={'image_url': 'https://example.org/old.jpg'}).json()
    previous = client.post('/api/admin/photos').json()
    with SessionLocal() as db:
        maker = db.get(Computer, 1).manufacturer_id
        db.add_all(Computer(manufacturer_id=maker, model_name=f'Synthetic model {i}') for i in range(1095))
        db.get(Computer, 2).image_url = 'https://example.org/legacy.jpg'
        db.get(PhotoJob, previous['id']).next_request_at = clock[0] + timedelta(seconds=60)
        old_items = db.scalars(select(PhotoItem).where(PhotoItem.job_id == previous['id'])).all()
        old_items[0].status = 'no_match'
        db.commit()
    job = restart_queue(client, previous['id'])
    assert job['replace_existing'] is True and job['total'] == 1105 and job['counts'] == {'pending': 1105}
    assert client.get('/api/admin/photos').json()['total'] == 1105
    assert job['missing'] == 1103
    assert client.post(f"/api/admin/photos/{job['id']}/step").status_code == 429
    assert client.post('/api/admin/photos/restart', json={'expected_job_id': previous['id']}).status_code == 409
    with SessionLocal() as db:
        old = db.get(PhotoJob, previous['id'])
        assert old.status == 'superseded' and old.active_key is None
        assert len(db.scalars(select(PhotoItem).where(PhotoItem.job_id == old.id)).all()) == previous['total']
        rows = db.scalars(select(PhotoItem).where(PhotoItem.job_id == job['id']).order_by(PhotoItem.position)).all()
        assert len({row.computer_id for row in rows}) == 1105
        assert rows[0].query == 'IBM - System/360' and rows[-1].position == 1105
    assert client.get('/api/computers/1/images').json() == [old_photo]
    assert client.post(f"/api/admin/photos/{previous['id']}/resume").json()['status'] == 'superseded'


def test_replacement_sets_new_cover_and_keeps_other_gallery_images(client, monkeypatch, clock):
    first = client.post('/api/computers/1/images', json={'image_url': 'https://example.org/old.jpg', 'is_primary': True}).json()
    second = client.post('/api/computers/1/images', json={'image_url': 'https://example.org/gallery.jpg'}).json()
    job = restart_queue(client)
    queries = []
    async def search(query, limit):
        queries.append(query); return {'1': page('Replacement')}
    monkeypatch.setattr(main, 'search_pages', search)
    result = client.post(f"/api/admin/photos/{job['id']}/step").json()
    assert result['counts'] == {'replaced': 1, 'pending': 9} and result['missing'] == 9
    photos = client.get('/api/computers/1/images').json()
    assert len(photos) == 3 and photos[0]['url'].endswith('/Replacement.jpg')
    assert photos[0]['author'] == 'Alice' and photos[0]['license_name'] == 'CC BY-SA 4.0'
    assert sum(photo['is_primary'] for photo in photos) == 1
    assert {photo['id'] for photo in photos[1:]} == {first['id'], second['id']}
    assert client.get('/api/computers/1').json()['image_url'].endswith('/thumb/Replacement.jpg')
    assert queries == ['IBM - System/360']


@pytest.mark.parametrize('outcome', ['no_match', 'unlicensed', 'outage'])
def test_replacement_keeps_existing_cover_until_usable_result(client, monkeypatch, clock, outcome):
    previous = client.post('/api/computers/1/images', json={'image_url': 'https://example.org/keep.jpg'}).json()
    job = restart_queue(client)
    async def search(query, limit):
        if outcome == 'outage': raise HTTPException(503, 'Commons busy', headers={'Retry-After': '60'})
        return {} if outcome == 'no_match' else {'1': page(licence='Unknown')}
    monkeypatch.setattr(main, 'search_pages', search)
    result = client.post(f"/api/admin/photos/{job['id']}/step").json()
    assert result['status'] == ('paused' if outcome == 'outage' else 'ready')
    assert result['counts'] == ({'pending': 10} if outcome == 'outage' else {'no_match': 1, 'pending': 9})
    assert client.get('/api/computers/1/images').json() == [previous]


def test_replacement_reuses_same_image_without_duplicate_gallery_entries(client, monkeypatch, clock):
    previous = client.post('/api/computers/1/images', json={'image_url': 'https://upload.wikimedia.org/First.jpg'}).json()
    job = restart_queue(client)
    async def search(query, limit): return {'1': page()}
    monkeypatch.setattr(main, 'search_pages', search)
    assert client.post(f"/api/admin/photos/{job['id']}/step").json()['counts']['replaced'] == 1
    images = client.get('/api/computers/1/images').json()
    assert len(images) == 1 and images[0]['id'] == previous['id'] and images[0]['is_primary']
    assert images[0]['author'] == 'Alice' and images[0]['license_name'] == 'CC BY-SA 4.0'


def test_replacement_does_not_overwrite_manual_changes_during_network_request(client, monkeypatch, clock):
    client.post('/api/computers/1/images', json={'image_url': 'https://example.org/old.jpg'})
    job = restart_queue(client)
    async def search(query, limit):
        with SessionLocal() as db:
            db.get(Computer, 1).image_url = 'https://example.org/new-manual-cover.jpg'
            db.commit()
        return {'1': page('DoNotSave')}
    monkeypatch.setattr(main, 'search_pages', search)
    result = client.post(f"/api/admin/photos/{job['id']}/step").json()
    assert result['counts'] == {'skipped': 1, 'pending': 9}
    assert len(client.get('/api/computers/1/images').json()) == 1
    with SessionLocal() as db: assert db.get(Computer, 1).image_url.endswith('/new-manual-cover.jpg')


def test_restart_during_inflight_request_invalidates_old_result_and_keeps_lease_delay(client, monkeypatch, clock):
    previous = client.post('/api/admin/photos').json()
    async def search(query, limit):
        await asyncio.to_thread(restart_queue, client, previous['id'])
        return {'1': page('OldResponse')}
    monkeypatch.setattr(main, 'search_pages', search)
    result = client.post(f"/api/admin/photos/{previous['id']}/step").json()
    assert result['status'] == 'superseded' and result['counts'] == {'pending': 10}
    latest = client.get('/api/admin/photos').json()['job']
    assert latest['replace_existing'] is True
    assert client.post(f"/api/admin/photos/{latest['id']}/step").status_code == 429
    assert client.get('/api/computers/1/images').json() == []
    clock[0] += timedelta(seconds=91)
    async def empty(query, limit): return {}
    monkeypatch.setattr(main, 'search_pages', empty)
    assert client.post(f"/api/admin/photos/{latest['id']}/step").json()['counts']['no_match'] == 1


def test_migration_adds_mode_to_legacy_queue_and_is_repeatable(client):
    from sqlalchemy import text
    from migrations.photo_jobs import migrate
    jid, _ = single_queue(client)
    with main.engine.begin() as connection:
        connection.execute(text('ALTER TABLE commons_photo_jobs DROP COLUMN replace_existing'))
    migrate(main.engine); migrate(main.engine)
    result = client.get('/api/admin/photos').json()['job']
    assert result['id'] == jid and result['replace_existing'] is False and result['total'] == 1


def test_empty_catalog_restart_finishes_immediately(client):
    with SessionLocal() as db:
        for computer in db.scalars(select(Computer)).all(): db.delete(computer)
        db.commit()
    result = restart_queue(client)
    assert result['status'] == 'completed' and result['total'] == 0
