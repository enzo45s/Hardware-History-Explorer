"""Restart snapshots preserve evidence, curated text, leases and source waits."""
import asyncio
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from app import history_sources
from app.history_models import HistoryJob
from app.import_models import ImportClaim
from app.main import SessionLocal
from app.models import Computer, Source
from test_history import TEXT, page, payload, target, clock


def two_targets(client):
    with SessionLocal() as db:
        db.get(Computer, 2).description = None
        db.commit()
    return target(client)


def empty_source(monkeypatch):
    async def research(*args, **kwargs):
        return {'status': 'no_match', 'reason': 'Synthetic missing text'}, payload()
    monkeypatch.setattr(history_sources, 'research', research)


def test_requests_advance_after_one_second_but_not_before(client, monkeypatch, clock):
    empty_source(monkeypatch); jid = two_targets(client)['id']
    first = client.post(f'/api/admin/history/{jid}/step').json()
    assert first['counts']['pending'] == 1
    assert client.post(f'/api/admin/history/{jid}/step').status_code == 429
    clock[0] += timedelta(milliseconds=999)
    assert client.post(f'/api/admin/history/{jid}/step').status_code == 429
    clock[0] += timedelta(milliseconds=1)
    final = client.post(f'/api/admin/history/{jid}/step').json()
    assert final['status'] == 'completed' and final['counts']['no_match'] == 2


def test_restart_paused_run_starts_from_first_eligible_and_keeps_old_report(client, monkeypatch, clock):
    empty_source(monkeypatch); jid = two_targets(client)['id']
    client.post(f'/api/admin/history/{jid}/step')
    client.post(f'/api/admin/history/{jid}/pause')
    previous = client.get(f'/api/admin/history/{jid}/report').json()
    restarted = client.post(f'/api/admin/history/{jid}/restart')
    assert restarted.status_code == 201
    new = restarted.json()
    assert new['id'] != jid and new['current']['computer_id'] == 1
    assert new['current']['attempt'] == 1 and new['current']['searches'] == []
    assert new['counts'] == {'pending': 2, 'preserved': 8}
    old = client.get(f'/api/admin/history/{jid}/report').json()
    assert old['job']['status'] == 'archived' and old['items'] == previous['items']
    assert client.post('/api/admin/history').json()['id'] == new['id']
    assert client.post(f'/api/admin/history/{jid}/restart').status_code == 409


def test_restart_completed_preserves_updated_text_attribution_and_sources(client, monkeypatch, clock):
    jid = two_targets(client)['id']
    async def research(model, maker):
        raw = payload(page())
        return history_sources.select_result(model, maker, raw), raw
    monkeypatch.setattr(history_sources, 'research', research)
    client.post(f'/api/admin/history/{jid}/step'); clock[0] += timedelta(seconds=1)
    assert client.post(f'/api/admin/history/{jid}/step').json()['status'] == 'completed'
    before = client.get('/api/computers/1').json()
    restarted = client.post(f'/api/admin/history/{jid}/restart').json()
    assert restarted['counts'] == {'pending': 1, 'preserved': 9}
    assert restarted['current']['computer_id'] == 2
    after = client.get('/api/computers/1').json()
    assert after == before and after['description'] == TEXT
    assert after['description_attribution']['title'] == 'Synthetic History One'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Source)) == 1
        assert db.scalar(select(func.count()).select_from(ImportClaim)) == 1
        assert db.scalar(select(func.count()).select_from(HistoryJob).where(HistoryJob.active_key == 'italian')) == 1


def test_restart_cannot_interrupt_an_active_request(client, monkeypatch, clock):
    jid = target(client)['id']
    assert client.post(f'/api/admin/history/{jid}/restart').status_code == 409
    async def research(model, maker):
        await asyncio.to_thread(client.post, f'/api/admin/history/{jid}/pause')
        assert (await asyncio.to_thread(client.post, f'/api/admin/history/{jid}/restart')).status_code == 409
        raw = payload(page())
        return history_sources.select_result(model, maker, raw), raw
    monkeypatch.setattr(history_sources, 'research', research)
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['updated'] == 1


def test_restart_cannot_bypass_wikipedia_retry_after(client, monkeypatch, clock):
    calls = []
    async def occupied(*args, **kwargs):
        calls.append(args)
        raise HTTPException(503, 'Synthetic source wait', headers={'Retry-After': '60'})
    monkeypatch.setattr(history_sources, 'research', occupied)
    jid = target(client)['id']
    assert client.post(f'/api/admin/history/{jid}/step').json()['status'] == 'paused'
    restarted = client.post(f'/api/admin/history/{jid}/restart').json()
    assert restarted['id'] != jid
    assert client.post(f'/api/admin/history/{restarted["id"]}/step').status_code == 429
    clock[0] += timedelta(seconds=59)
    assert client.post(f'/api/admin/history/{restarted["id"]}/step').status_code == 429
    assert len(calls) == 1
    clock[0] += timedelta(seconds=1)
    empty_source(monkeypatch)
    assert client.post(f'/api/admin/history/{restarted["id"]}/step').json()['status'] == 'completed'


def test_restart_all_curated_completes_immediately_and_cannot_replace_another_queue(client, monkeypatch, clock):
    empty_source(monkeypatch); jid = target(client)['id']
    client.post(f'/api/admin/history/{jid}/step')
    with SessionLocal() as db:
        db.get(Computer, 1).description = 'Testo curato a mano da conservare.'
        db.commit()
    restarted = client.post(f'/api/admin/history/{jid}/restart').json()
    assert restarted['status'] == 'completed' and restarted['counts'] == {'preserved': 10}
    with SessionLocal() as db:
        db.get(Computer, 1).description = None; db.commit()
    active = client.post('/api/admin/history').json()
    assert active['status'] == 'ready'
    assert client.post(f'/api/admin/history/{restarted["id"]}/restart').status_code == 409
    assert client.get('/api/admin/history').json()['job']['id'] == active['id']
    assert client.post('/api/admin/history/999999/restart').status_code == 404


def test_restart_old_report_retains_a_newer_completed_runs_source_cooldown(client, monkeypatch, clock):
    empty_source(monkeypatch); old_id = target(client)['id']
    client.post(f'/api/admin/history/{old_id}/step')
    clock[0] += timedelta(seconds=1)
    latest = client.post('/api/admin/history').json()
    async def occupied(*args, **kwargs):
        raise HTTPException(503, 'Synthetic source wait', headers={'Retry-After': '60'})
    monkeypatch.setattr(history_sources, 'research', occupied)
    assert client.post(f'/api/admin/history/{latest["id"]}/step').json()['status'] == 'paused'
    skipped = client.post(f'/api/admin/history/{latest["id"]}/skip', json={'item_id': latest['current']['id']}).json()
    assert skipped['status'] == 'completed'
    restarted = client.post(f'/api/admin/history/{old_id}/restart').json()
    assert restarted['current']['computer_id'] == 1
    assert client.post(f'/api/admin/history/{restarted["id"]}/step').status_code == 429
