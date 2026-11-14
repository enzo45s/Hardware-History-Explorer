"""Matching regressions; only the 935 names/URL were supplied by the operator.

The HTML is reconstructed, not downloaded. Other records and site responses
are synthetic and are never declared verified historical data.
"""
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.main import SessionLocal
from app.models import Computer, Manufacturer
from app.import_models import ImportJob, ImportRow
from app.importing import bulk1000bit as bulk
from app.importing.bit1000 import html_record
from app.importing.engine import catalog_candidates, original_bytes
from app.importing.identity import provider_computer_key, provider_maker_key
from test_1000bit_bulk import PREFIX, advance, complete, start

HTML = Path(__file__).with_name('fixtures').joinpath('1000bit-fujitsu935-names.html').read_bytes()
URL = 'https://www.1000bit.it/scheda.asp?id=935'


def fujitsu(*models):
    with SessionLocal() as db:
        maker = Manufacturer(name='Fujitsu'); db.add(maker)
        computers = [Computer(manufacturer=maker, model_name=model, description='Existing description') for model in models]
        db.add_all(computers); db.commit()
        return [computer.id for computer in computers]


@pytest.fixture
def website(monkeypatch):
    calls = []
    def fetch(url, limit):
        calls.append(url)
        if url.endswith('/robots.txt'): return 200, b'User-agent: *\nAllow: /', 'text/plain', {}
        if '/database' in url: return 200, b'<a href="/scheda.asp?id=935">Fujitsu</a>', 'text/html', {}
        if url == bulk.SEED: return 200, b'<a href="/scheda.asp?id=935">Fujitsu</a>', 'text/html', {}
        if url == URL: return 200, HTML, 'text/html; charset=utf-8', {}
        raise AssertionError(url)
    # The crawler's second seed is a sheet; leave it out of these matching tests.
    monkeypatch.setattr(bulk, 'queue', _single_seed_queue(bulk.queue))
    monkeypatch.setattr(bulk, 'fetch', fetch)
    return calls


def _single_seed_queue(original):
    def queue(db, job, urls): return original(db, job, [url for url in urls if url != bulk.SEED])
    return queue


@pytest.mark.parametrize('maker,model,other_maker,other_model', [
    ('Fujitsu (Japan)', 'FM 11 EX', 'Fujitsu', 'FM-11 EX'),
    ('Fujitsu (Japan)', 'FUJITSU FM11EX', 'Fujitsu', 'FM-11 EX'),
    ('Fujitsu（Japan）', 'FM\u201111 EX', 'Fujitsu', 'FM-11 EX'),
    ('NEC (Japan)', 'PC 8001', 'NEC', 'NEC PC-8001'),
    ('Toshiba (Japan)', 'T 1000', 'Toshiba', 'T1000'),
    ('Sony (Japan)', 'HB 101', 'Sony', 'HB-101'),
    ('Sinclair (UK)', 'ZX Spectrum +2', 'Sinclair', 'Sinclair ZX Spectrum+2'),
    ('Apple Computer (USA)', 'Macintosh 128K', 'Apple', 'Apple Macintosh 128K'),
    ('Commodore Business Machines (USA)', 'C64', 'Commodore', 'Commodore 64'),
    ('Acorn (United Kingdom)', 'BBC B', 'Acorn', 'Acorn BBC-B'),
    ('Synthetic (Taiwan)', 'Model 11', 'Synthetic', 'Model-11'),
])
def test_format_country_and_known_brand_prefixes_match(maker, model, other_maker, other_model):
    assert provider_computer_key('1000bit', maker, model) == provider_computer_key('1000bit', other_maker, other_model)


@pytest.mark.parametrize('maker,model,other_maker,other_model', [
    ('Fujitsu', 'FM-11 EX', 'Fujitsu', 'FM-11 AD'),
    ('Fujitsu', 'FM-11 EX', 'Fujitsu', 'FM-11'),
    ('Fujitsu', 'FM-11 EX', 'Fujitsu', 'FM-11 EX (HD)'),
    ('Fujitsu', 'FM-11 EX', 'NEC', 'FM-11 EX'),
    ('Fujitsu (Siemens)', 'FM-11 EX', 'Fujitsu', 'FM-11 EX'),
    ('Sinclair', 'ZX Spectrum+', 'Sinclair', 'ZX Spectrum'),
    ('DEC', 'PDP-11/20', 'DEC', 'PDP-1120'),
    ('Synthetic', 'Model 1.1', 'Synthetic', 'Model 11'),
])
def test_hardware_variants_and_manufacturers_stay_distinct(maker, model, other_maker, other_model):
    assert provider_computer_key('1000bit', maker, model) != provider_computer_key('1000bit', other_maker, other_model)


def test_matching_rules_do_not_broaden_other_providers():
    assert provider_maker_key('manual', 'Fujitsu (Japan)') != provider_maker_key('manual', 'Fujitsu')
    assert provider_computer_key('wikidata', 'Fujitsu', 'FM11EX') != provider_computer_key('wikidata', 'Fujitsu', 'FM-11 EX')


def test_operator_fujitsu_names_match_upload_and_bulk_without_new_manufacturer(client, website):
    cid = fujitsu('FM-11 EX')[0]
    before = client.get('/api/computers').json()['total']
    maker_count = len(client.get('/api/manufacturers').json())
    record = html_record(HTML)
    assert (record['manufacturer'], record['model_name']) == ('Fujitsu (Japan)', 'FM 11 EX')
    with SessionLocal() as db: assert catalog_candidates(db, record, '1000bit') == ([cid], False)
    uploaded = client.post('/api/admin/imports/upload', files={'file': ('fujitsu-names.html', HTML)},
        data={'provider': '1000bit', 'rights_confirmed': 'true'}).json()
    row = client.get(f"/api/admin/imports/{uploaded['id']}").json()['rows'][0]
    assert row['computer_id'] == cid and row['normalized']['manufacturer'] == 'Fujitsu (Japan)'
    assert client.post(f"/api/admin/imports/{uploaded['id']}/apply").status_code == 200
    done = complete(client, start(client))
    assert done['counts']['unchanged'] == 1 and done['pages']['unchanged'] == 1
    public = client.get(f'/api/computers/{cid}').json()
    assert public['manufacturer'] == 'Fujitsu' and public['model_name'] == 'FM-11 EX'
    assert public['description'] == 'Existing description'
    assert public['sources'][0]['url'] == URL and public['sources'][0]['publisher'] == '1000bit'
    assert client.get('/api/computers').json()['total'] == before
    assert len(client.get('/api/manufacturers').json()) == maker_count
    detail = client.get(f"/api/admin/imports/{uploaded['id']}").json()
    assert not [claim for claim in detail['rows'][0]['claims'] if claim['field'] in ('model_name', 'manufacturer_id') and claim['status'] == 'conflict']


def test_colliding_format_keys_are_reviewed_even_when_one_name_is_exact(client, website):
    ids = fujitsu('FM-11 EX', 'FM 11 EX')
    done = complete(client, start(client))
    assert done['pages']['review'] == 1 and done['counts']['ambiguous'] == 2
    detail = client.get(f"/api/admin/imports/{done['reviews'][0]['import_job_id']}").json()
    assert set(detail['rows'][0]['candidates']) == set(ids)
    assert detail['rows'][0]['status'] == 'ambiguous'
    assert all(not client.get(f'/api/computers/{cid}').json()['sources'] for cid in ids)


def test_new_catalog_collision_outside_snapshot_does_not_silently_choose_original(client, website):
    cid = fujitsu('FM-11 EX')[0]
    job = start(client)
    with SessionLocal() as db:
        duplicate = Computer(manufacturer_id=db.get(Computer, cid).manufacturer_id, model_name='FM 11 EX')
        db.add(duplicate); db.commit(); other_id = duplicate.id
    done = complete(client, job)
    assert done['pages']['review'] == 1 and done['counts']['ambiguous'] == 1
    detail = client.get(f"/api/admin/imports/{done['reviews'][0]['import_job_id']}").json()
    assert set(detail['rows'][0]['candidates']) == {cid, other_id}
    assert not client.get(f'/api/computers/{cid}').json()['sources']


def test_retry_legacy_unmatched_pages_preserves_successes_snapshot_and_cooldown(client, website):
    cid = fujitsu('FM-11 EX')[0]
    job = start(client)
    with SessionLocal() as db:
        for page in db.scalars(select(bulk.BulkPage).where(bulk.BulkPage.job_id == job['id'])): page.status = 'indexed'
        db.add(bulk.BulkPage(job_id=job['id'], url=URL, status='unmatched', model_name='FM 11 EX', manufacturer='Fujitsu (Japan)'))
        target = db.scalar(select(bulk.BulkTarget).where(bulk.BulkTarget.job_id == job['id'], bulk.BulkTarget.computer_id == cid))
        target.status = 'not_found'
        saved = db.get(bulk.BulkJob, job['id']); saved.status, saved.active_key = 'completed', None
        saved.next_request_at = bulk.now() + timedelta(seconds=90)
        db.commit()
    first = client.post(f"{PREFIX}/{job['id']}/retry-unmatched", json={})
    assert first.status_code == 200, first.text
    retry = first.json()
    assert retry['status'] == 'paused' and retry['pages'] == {'indexed': 1, 'pending': 1}
    assert client.post(f"{PREFIX}/{job['id']}/retry-unmatched", json={}).status_code == 409
    resumed = client.post(f"{PREFIX}/{job['id']}/resume", json={}).json()
    assert advance(client, resumed, force=False)['requests'] == 0 and website == []
    done = complete(client, resumed)
    assert done['id'] == job['id'] and done['counts']['updated'] == 1
    assert website.count(URL) == 1 and not any('/database' in url for url in website)
    assert client.get(f'/api/computers/{cid}').json()['sources'][0]['url'] == URL


def test_unmatched_original_is_retained_without_creating_models_and_can_be_retried(client, website):
    before = client.get('/api/computers').json()['total']
    done = complete(client, start(client))
    assert done['pages']['unmatched'] == 1 and client.get('/api/computers').json()['total'] == before
    page = next(page for page in done['recent'] if page['status'] == 'unmatched')
    assert page['manufacturer'] == 'Fujitsu (Japan)' and 'FM 11 EX' in page['error']
    with SessionLocal() as db:
        imported = db.get(ImportJob, page['import_job_id'])
        assert original_bytes(imported) == HTML
        assert db.scalar(select(ImportRow).where(ImportRow.job_id == imported.id)).normalized['model_name'] == 'FM 11 EX'
        assert db.scalar(select(func.count()).select_from(ImportJob)) == 1


def test_retry_rejects_archived_inflight_or_older_session(client, website):
    from datetime import timezone, datetime
    job = start(client)
    with SessionLocal() as db:
        db.add(bulk.BulkPage(job_id=job['id'], url=URL, status='unmatched'))
        saved = db.get(bulk.BulkJob, job['id']); saved.lease_token = 'inflight'; saved.lease_until = datetime.now(timezone.utc) + timedelta(seconds=180)
        db.commit()
    assert client.post(f"{PREFIX}/{job['id']}/retry-unmatched", json={}).status_code == 409
    client.post(f"{PREFIX}/{job['id']}/cancel")
    assert client.post(f"{PREFIX}/{job['id']}/retry-unmatched", json={}).status_code == 409
    assert client.post(f'{PREFIX}/99999/retry-unmatched', json={}).status_code == 404


def test_retry_cannot_reactivate_old_session_while_another_is_active(client, website):
    done = complete(client, start(client))
    active = start(client)
    assert client.post(f"{PREFIX}/{done['id']}/retry-unmatched", json={}).status_code == 409
    assert client.get(PREFIX).json()['job']['id'] == active['id']


def test_retry_can_increase_request_limit_without_losing_pause_or_successes(client, website):
    done = complete(client, start(client))
    with SessionLocal() as db:
        saved = db.get(bulk.BulkJob, done['id']); saved.max_requests = saved.requests
        db.commit()
    assert client.post(f"{PREFIX}/{done['id']}/retry-unmatched", json={}).status_code == 409
    result = client.post(f"{PREFIX}/{done['id']}/retry-unmatched", json={'max_requests': 100})
    assert result.status_code == 200 and result.json()['max_requests'] == 100
    assert result.json()['status'] == 'paused' and result.json()['pages']['pending'] == 1
