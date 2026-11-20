"""Synthetic linked website tests traversal; only the Amiga excerpt is real."""
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.main import SessionLocal
from app.models import Computer, Manufacturer
from app.import_models import ImportJob
from app.importing import bulk1000bit as bulk
from migrations.historical_imports import migrate

PREFIX = '/api/admin/1000bit/bulk'
HTML = Path(__file__).with_name('fixtures').joinpath('1000bit-amiga1200.html').read_bytes()
URL = bulk.SEED
SECOND = 'https://www.1000bit.it/scheda.asp?id=900001'
OTHER = 'https://www.1000bit.it/scheda.asp?id=900002'


def body_for(name, id):
    return HTML.replace(b'Amiga 1200', name.encode()).replace(b'id=282', f'id={id}'.encode())


def catalog():
    with SessionLocal() as db:
        maker = db.scalar(select(Manufacturer).where(Manufacturer.name == 'Commodore'))
        rows = [Computer(model_name=name, manufacturer=maker, description='Manual description preserved')
                for name in ('Amiga 1200', 'Bulk Synthetic Fixture')]
        db.add_all(rows); db.commit()
        return [c.id for c in rows]


@pytest.fixture
def website(monkeypatch):
    calls = []
    def fetch(url, limit):
        calls.append(url)
        if url.endswith('/robots.txt'):
            return 200, b'User-agent: *\nAllow: /\nCrawl-delay: 7', 'text/plain', {}
        if '/database' in url:
            return 200, f'''<a href="{URL}">Amiga</a><a href="{SECOND}">Synthetic</a>
              <a href="{OTHER}">Unrelated</a><a href="database.asp?sort=foo&by=bar">Same index</a>
              <a href="https://evil.example/scheda.asp?id=1">Excluded</a>
              <a href="/support/manual.pdf">Excluded</a><a href="database.asp?coll=-1">Private</a>
              <form><a href="scheda.asp?id=999999">Form ignored</a></form>'''.encode(), 'text/html', {}
        if url == URL:
            return 200, HTML, 'text/html; charset=utf-8', {}
        if url == SECOND:
            return 200, body_for('Bulk Synthetic Fixture', 900001), 'text/html', {}
        if url == OTHER:
            return 200, body_for('Unknown Synthetic Model', 900002), 'text/html', {}
        raise AssertionError('Unexpected request: ' + url)
    monkeypatch.setattr(bulk, 'fetch', fetch)
    return calls, fetch


def start(client, **options):
    response = client.post(PREFIX, json=options)
    assert response.status_code == 201, response.text
    return response.json()


def due(job_id):
    with SessionLocal() as db:
        db.get(bulk.BulkJob, job_id).next_request_at = bulk.now() - timedelta(seconds=1)
        db.commit()


def advance(client, job, force=True):
    if force:
        due(job['id'])
    response = client.post(f"{PREFIX}/{job['id']}/step")
    assert response.status_code == 200, response.text
    return response.json()


def complete(client, job, max_steps=30):
    for _ in range(max_steps):
        if job['status'] != 'ready':
            return job
        job = advance(client, job)
    pytest.fail('Queue did not terminate: ' + str(job))


def test_automatic_traversal_updates_snapshot_without_per_model_input(client, website):
    ids = catalog()
    before = client.get('/api/computers').json()['total']
    job = start(client)
    assert job['total'] == before
    assert start(client)['id'] == job['id']
    done = complete(client, job)
    assert done['status'] == 'completed'
    assert done['counts']['updated'] == 2 and done['counts']['not_found'] == before - 2
    assert done['conflicts'] == 2  # Existing descriptions are preserved, not replaced.
    assert client.get('/api/computers').json()['total'] == before
    for cid in ids:
        computer = client.get(f'/api/computers/{cid}').json()
        assert computer['description'] == 'Manual description preserved'
        assert len(computer['configurations']) == 1 and len(computer['configurations'][0]['specifications']) == 7
        assert computer['configurations'][0]['specifications'][0]['sources'][0]['publisher'] == '1000bit'
    calls, _ = website
    assert len(calls) == len(set(calls)), 'Visited pages must never be downloaded twice.'
    assert done['interval_seconds'] == 7
    assert not any('evil' in url or 'pdf' in url or '999999' in url or 'coll=' in url for url in calls)
    again = complete(client, start(client))
    assert again['counts']['unchanged'] == 2 and again['counts'].get('updated', 0) == 0
    assert client.get('/api/computers').json()['total'] == before


def test_cooldown_pause_and_restart_keep_frontier_and_cached_robots(client, website):
    catalog(); job = start(client)
    first = advance(client, job)
    calls, _ = website
    assert len(calls) == 1 and calls[0].endswith('/robots.txt')
    assert advance(client, first, force=False)['requests'] == 1
    assert len(calls) == 1
    client.post(f"{PREFIX}/{job['id']}/pause")
    assert advance(client, first)['status'] == 'paused'
    snapshot = client.get(PREFIX).json()['job']
    assert snapshot['id'] == job['id'] and snapshot['pages']['pending'] == 2
    resumed = client.post(f"{PREFIX}/{job['id']}/resume", json={}).json()
    done = complete(client, resumed)
    assert done['status'] == 'completed' and calls.count('https://www.1000bit.it/robots.txt') == 1


def test_rate_limit_keeps_current_page_and_honors_retry_after(client, website, monkeypatch):
    catalog(); job = advance(client, start(client))
    calls, real_fetch = website
    def limited(url, limit):
        calls.append(url)
        return 429, b'', 'text/plain', {'retry-after': '120'}
    monkeypatch.setattr(bulk, 'fetch', limited)
    paused = advance(client, job)
    assert paused['status'] == 'paused' and paused['pages']['pending'] == 2
    assert 110 < (bulk.datetime.fromisoformat(paused['next_request_at']) - bulk.now()).total_seconds() <= 120
    resumed = client.post(f"{PREFIX}/{job['id']}/resume", json={}).json()
    previous_calls = len(calls)
    advance(client, resumed, force=False)
    assert len(calls) == previous_calls
    monkeypatch.setattr(bulk, 'fetch', real_fetch)
    assert complete(client, resumed)['status'] == 'completed'


def test_network_failure_is_redacted_and_does_not_lose_work(client, monkeypatch):
    catalog(); job = start(client)
    def broken(*args):
        raise httpx.ProxyError('user:secret@private-proxy')
    monkeypatch.setattr(bulk, 'fetch', broken)
    paused = advance(client, job)
    assert paused['status'] == 'paused' and paused['requests'] == 1
    assert 'secret' not in str(paused) and paused['pages']['pending'] == 2


def test_ambiguities_are_staged_while_other_models_continue(client, website):
    ids = catalog()
    with SessionLocal() as db:
        original = db.get(Computer, ids[0])
        db.add(Computer(model_name=original.model_name, manufacturer_id=original.manufacturer_id)); db.commit()
    done = complete(client, start(client))
    assert done['status'] == 'completed'
    assert done['pages']['review'] == 1 and done['counts']['updated'] == 1
    review_id = done['reviews'][0]['import_job_id']
    detail = client.get(f'/api/admin/imports/{review_id}').json()
    row = detail['rows'][0]
    assert row['status'] == 'ambiguous' and detail['existing_only']
    assert not client.get(f'/api/computers/{ids[0]}').json()['configurations']
    assert client.post(f"/api/admin/imports/{review_id}/rows/{row['id']}/match", json={'computer_id': ids[0]}).status_code == 200
    assert client.post(f'/api/admin/imports/{review_id}/apply').status_code == 200
    refreshed = client.post(f"{PREFIX}/{done['id']}/refresh").json()
    assert refreshed['reviews'] == [] and refreshed['counts']['updated'] == 2


def test_limit_can_be_raised_without_restarting_or_false_absence(client, website):
    catalog(); job = start(client, max_requests=1)
    limited = complete(client, job)
    assert limited['status'] == 'limited' and limited['requests'] == 1
    assert limited['counts'].get('not_found', 0) == 0
    assert client.post(f"{PREFIX}/{job['id']}/resume", json={}).status_code == 409
    resumed = client.post(f"{PREFIX}/{job['id']}/resume", json={'max_requests': 100}).json()
    assert complete(client, resumed)['status'] == 'completed'


def test_robots_disallow_prevents_sheet_requests(client, website, monkeypatch):
    catalog(); calls, real_fetch = website
    def restricted(url, limit):
        if url.endswith('/robots.txt'):
            calls.append(url)
            return 200, b'User-agent: *\nDisallow: /scheda.asp', 'text/plain', {}
        return real_fetch(url, limit)
    monkeypatch.setattr(bulk, 'fetch', restricted)
    done = complete(client, start(client))
    assert done['status'] == 'completed' and done['pages']['blocked'] == 3
    assert not any('/scheda.asp' in url for url in calls)
    assert done['counts'].get('updated', 0) == 0


def test_failure_rolls_back_catalog_and_frontier_as_one_transaction(client, website, monkeypatch):
    ids = catalog(); job = start(client)
    job = advance(client, job); job = advance(client, job)
    original = bulk.import_page
    def fail_after_import(*args):
        original(*args)
        raise ValueError('Synthetic failure after catalog update')
    monkeypatch.setattr(bulk, 'import_page', fail_after_import)
    paused = advance(client, job)
    assert paused['status'] == 'paused'
    assert not client.get(f'/api/computers/{ids[0]}').json()['configurations']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ImportJob)) == 0
    monkeypatch.setattr(bulk, 'import_page', original)
    resumed = client.post(f"{PREFIX}/{job['id']}/resume", json={}).json()
    assert complete(client, resumed)['counts']['updated'] == 2


def test_lease_prevents_second_request_while_network_is_running(client, monkeypatch):
    catalog(); job = start(client)
    calls = []
    def fetch(url, limit):
        calls.append(url)
        with SessionLocal() as other:
            state = bulk.step(other, job['id'], fetcher=fetch)
            assert state['requests'] == 0
        return 200, b'User-agent: *\nAllow: /', 'text/plain', {}
    monkeypatch.setattr(bulk, 'fetch', fetch)
    assert advance(client, job)['requests'] == 1 and len(calls) == 1


def test_reset_during_network_never_resurrects_catalog(client, website, monkeypatch):
    catalog(); job = start(client)
    job = advance(client, job); job = advance(client, job)
    _, real_fetch = website
    def reset_during_request(url, limit):
        data = client.get('/api/admin/archive/preview').json()
        response = client.post('/api/admin/archive/reset', json={'token': data['token'], 'backup_confirmed': True,
            'confirmation': 'SVUOTA ARCHIVIO', 'note': 'Reset only the isolated test database.'})
        assert response.status_code == 200, response.text
        return real_fetch(url, limit)
    monkeypatch.setattr(bulk, 'fetch', reset_during_request)
    archived = advance(client, job)
    assert archived['status'] == 'archived'
    assert client.get('/api/computers').json()['total'] == 0
    assert client.post(f"{PREFIX}/{job['id']}/resume", json={}).json()['status'] == 'archived'


def test_cancellation_and_skip_are_explicit_and_durable(client, website, monkeypatch):
    catalog(); job = start(client)
    monkeypatch.setattr(bulk, 'fetch', lambda *_: (503, b'', 'text/plain', {}))
    advance(client, job)
    skipped = client.post(f"{PREFIX}/{job['id']}/skip").json()
    assert skipped['pages']['skipped'] == 1
    cancelled = client.post(f"{PREFIX}/{job['id']}/cancel").json()
    assert cancelled['status'] == 'cancelled'
    assert start(client)['id'] != job['id']


def test_catalog_rename_does_not_retarget_source_and_migration_is_repeatable(client, website):
    ids = catalog(); job = start(client)
    with SessionLocal() as db:
        db.get(Computer, ids[0]).model_name = 'Renamed after the catalog snapshot'; db.commit()
    done = complete(client, job)
    assert not client.get(f'/api/computers/{ids[0]}').json()['configurations']
    from app.main import engine
    migrate(engine); migrate(engine)
    assert client.get(PREFIX).json()['job']['id'] == done['id']


def test_large_catalog_is_not_limited_to_first_page_and_full_report_preserves_all_targets(client, website):
    with SessionLocal() as db:
        maker = db.scalar(select(Manufacturer).where(Manufacturer.name == 'Commodore'))
        db.add_all(Computer(model_name=f'Synthetic scale fixture {i}', manufacturer=maker) for i in range(1093))
        db.commit()
    ids = catalog()  # The matching models now lie beyond the first 1,000 records.
    done = complete(client, start(client))
    assert done['total'] == 1105 and done['counts']['updated'] == 2
    assert done['counts']['not_found'] == 1103
    response = client.get(f"{PREFIX}/{done['id']}/report")
    assert response.status_code == 200 and 'attachment' in response.headers['content-disposition']
    report = response.json()
    assert len(report['targets']) == 1105
    assert {t['computer_id'] for t in report['targets'] if t['status'] == 'updated'} == set(ids)
    assert client.get('/api/computers').json()['total'] == 1105


def test_invalid_source_values_pause_without_leaving_partial_rows(client, website, monkeypatch):
    ids = catalog(); job = start(client)
    job = advance(client, job); job = advance(client, job)
    monkeypatch.setattr(bulk, 'fetch', lambda *_: (200, HTML.replace(b'Amiga 1200', b'X' * 181), 'text/html', {}))
    paused = advance(client, job)
    assert paused['status'] == 'paused'
    assert not client.get(f'/api/computers/{ids[0]}').json()['configurations']


@pytest.mark.parametrize('url', ['https://evil.example/scheda.asp?id=1', '/wrapper.asp',
    '/database.asp?coll=-1', '/support/manual.pdf', 'javascript:alert(1)', '/scheda.asp?id=-1'])
def test_navigation_cannot_escape_database_scope(url):
    with pytest.raises(ValueError):
        bulk.crawl_url(url)
