"""Synthetic historical evidence only; no network required for automated tests."""
import asyncio
from datetime import datetime, timedelta, timezone
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from app import history, history_sources
from app.main import SessionLocal, full, EAGER
from app.models import Computer, Source, computer_source
from app.history_models import HistoryItem
from app.import_models import ImportClaim, ImportJob
from app.assistant_context import retrieve

TEXT = ('Synthetic History One è un computer di IBM introdotto nel 1981 per un contesto storico di prova. '
        'Fu sviluppato per applicazioni aziendali e didattiche in questo esempio sintetico, senza attribuire fatti a un sistema reale.')
def page(title='Synthetic History One', text=TEXT, **extra):
    return {'ns': 0, 'title': title, 'pageid': 123, 'extract': text, 'revisions': [{'revid': 456}], **extra}
def payload(*pages): return {'query': {'pages': list(pages)}}

@pytest.fixture
def clock(monkeypatch):
    timestamp = [datetime(2030, 1, 1, tzinfo=timezone.utc)]
    monkeypatch.setattr(history, 'now', lambda: timestamp[0])
    return timestamp

def target(client):
    with SessionLocal() as db:
        c = db.get(Computer, 1)
        c.model_name = 'Synthetic History One'
        c.description = 'Synthetic History One è un calcolatore di IBM. Le configurazioni censite riportano Synthetic CPU.'
        db.commit()
    response = client.post('/api/admin/history')
    assert response.status_code == 201, response.text
    return response.json()

def fake_found(monkeypatch):
    async def research(model, maker):
        raw = payload(page())
        return history_sources.select_result(model, maker, raw), raw
    monkeypatch.setattr(history_sources, 'research', research)

def test_only_exact_known_template_is_replaceable():
    for value in (None, 'X è un calcolatore di IBM.', 'X è un calcolatore di IBM. MAME associa il modello all’anno 1980. Le configurazioni emulate documentano CPU.'):
        assert history_sources.replaceable('X', 'IBM', value)
    for value in ('X è un calcolatore di IBM. Contesto storico scritto a mano.', 'X è un calcolatore di IBM. Le configurazioni censite riportano CPU. Ulteriore contesto storico.', 'Una descrizione breve ma scritta a mano.', 'Y è un calcolatore di IBM.'):
        assert not history_sources.replaceable('X', 'IBM', value)

def test_matching_requires_exact_model_brand_history_and_unique_non_disambiguation_page():
    result = history_sources.select_result('Synthetic History One', 'IBM', payload(page()))
    assert result['status'] == 'found' and result['description'] == TEXT and 'oldid=456' in result['url']
    for candidate in (page('Synthetic History family'), page(text='Un computer IBM.'), page(pageprops={'disambiguation': ''}), page(revisions=[])):
        assert history_sources.select_result('Synthetic History One', 'IBM', payload(candidate))['status'] == 'no_match'
    assert history_sources.select_result('Synthetic History One', 'Apple', payload(page()))['status'] == 'no_match'
    assert history_sources.select_result('Synthetic History Two', 'IBM', payload(page()))['status'] == 'no_match'
    assert history_sources.select_result('Synthetic History One', 'IBM', payload(page(), page('Synthetic History One (computer)')))['status'] == 'ambiguous'
    assert history_sources.model_key('Apple', 'Apple II') != history_sources.model_key('Apple', 'Apple IIe')
    assert history_sources.model_key('IBM', '5150 (Enhanced)') == history_sources.model_key('IBM', '5150')
    assert history_sources.model_key('IBM', '5150 Enhanced') != history_sources.model_key('IBM', '5150')
    assert history_sources.model_key('HP', 'HP 85') == history_sources.model_key('Hewlett-Packard', 'Hewlett-Packard 85')

def test_sourced_update_preserves_catalog_audit_pending_state_assistant_and_replay(client, monkeypatch, clock):
    fake_found(monkeypatch); job = target(client); jid = job['id']
    before = client.get('/api/computers/1').json()
    assert job['counts'] == {'pending': 1, 'preserved': 9}
    assert client.post('/api/admin/history').json()['id'] == jid
    result = client.post(f'/api/admin/history/{jid}/step')
    assert result.status_code == 200, result.text
    assert result.json()['counts'] == {'updated': 1, 'preserved': 9} and result.json()['status'] == 'completed'
    after = client.get('/api/computers/1').json()
    assert after['description'] == TEXT
    for key in ('configurations', 'releases', 'images', 'categories', 'facts'): assert after[key] == before[key]
    assert after['description_attribution']['title'] == 'Synthetic History One'
    assert after['description_attribution']['license_url'].endswith('/by-sa/4.0/')
    assert after['sources'][-1]['publisher'] == 'Wikipedia'
    with SessionLocal() as db:
        claim = db.scalar(select(ImportClaim))
        assert claim.status == 'pending' and claim.previous['value'] == before['description']
        assert db.execute(select(computer_source)).one().verification_status == 'pending'
        item = db.scalar(select(HistoryItem).where(HistoryItem.status == 'updated'))
        assert item.raw_payload == payload(page())
        imported = db.get(ImportJob, item.import_job_id)
        assert imported.provider == 'italian_history' and 'revisions' in imported.raw_payload
        import_id = imported.id
        context = retrieve(db, 'Synthetic History One', EAGER, full)['computers'][0]
        assert context['description'] == TEXT
        assert any(c['status'] == 'pending' and c['field'] == 'description' for c in context['import_assertions'])
    assert client.post('/api/admin/history').json()['counts'] == {'preserved': 10}
    assert client.get('/api/admin/history').json()['eligible'] == 0
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['updated'] == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ImportClaim)) == 1
        assert db.scalar(select(func.count()).select_from(Source)) == 1
    report = client.get(f'/api/admin/history/{jid}/report')
    assert 'attachment;' in report.headers['content-disposition'] and len(report.json()['items']) == 10
    assert client.get(f'/api/admin/imports/{import_id}').json()['rows'][0]['claims'][0]['status'] == 'pending'
    assert client.post(f'/api/admin/imports/{import_id}/retry').status_code == 409

def test_unresolved_does_not_change_description_or_create_a_source(client, monkeypatch, clock):
    async def research(model, maker):
        raw = payload(page('Unrelated synthetic computer'))
        return history_sources.select_result(model, maker, raw), raw
    monkeypatch.setattr(history_sources, 'research', research); job = target(client)
    before = client.get('/api/computers/1').json()['description']
    result = client.post(f"/api/admin/history/{job['id']}/step").json()
    assert result['status'] == 'completed' and result['counts']['no_match'] == 1
    assert client.get('/api/computers/1').json()['description'] == before and client.get('/api/sources').json() == []

def test_rate_limit_pause_and_resume_keep_current_model(client, monkeypatch, clock):
    job = target(client); jid = job['id']
    async def research(*args): raise HTTPException(503, 'Fonte occupata', headers={'Retry-After': '60'})
    monkeypatch.setattr(history_sources, 'research', research)
    response = client.post(f'/api/admin/history/{jid}/step').json()
    assert response['status'] == 'paused' and response['current']['computer_id'] == 1 and response['counts']['pending'] == 1
    assert client.post(f'/api/admin/history/{jid}/resume').json()['status'] == 'ready'
    assert client.post(f'/api/admin/history/{jid}/step').status_code == 429
    clock[0] += timedelta(seconds=60); fake_found(monkeypatch)
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['updated'] == 1

@pytest.mark.parametrize('change', ['description', 'model', 'delete', 'reset'])
def test_concurrent_manual_changes_and_catalog_reset_win(client, monkeypatch, clock, change):
    job = target(client); jid = job['id']
    async def research(model, maker):
        if change == 'reset':
            from app.archive import reset_catalog, fingerprint, ResetRequest
            with SessionLocal() as db:
                token = fingerprint(db); db.rollback()
                reset_catalog(db, ResetRequest(token=token, confirmation='SVUOTA ARCHIVIO', backup_confirmed=True, note='Synthetic reset during historical request'))
        elif change == 'delete': assert (await asyncio.to_thread(client.delete, '/api/computers/1')).status_code == 204
        else:
            with SessionLocal() as db:
                c = db.get(Computer, 1)
                if change == 'description': c.description = 'Descrizione manuale durante la ricerca.'
                else: c.model_name = 'Nome modificato'
                db.commit()
        raw = payload(page()); return history_sources.select_result(model, maker, raw), raw
    monkeypatch.setattr(history_sources, 'research', research)
    result = client.post(f'/api/admin/history/{jid}/step')
    assert result.status_code == 200, result.text
    assert result.json()['counts']['changed'] == 1
    if change == 'reset': assert result.json()['status'] == 'archived'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ImportClaim)) == 0
        if change == 'description': assert db.get(Computer, 1).description == 'Descrizione manuale durante la ricerca.'

def test_two_tabs_cannot_advance_same_item(client, monkeypatch, clock):
    job = target(client); jid = job['id']
    async def research(model, maker):
        assert (await asyncio.to_thread(client.post, f'/api/admin/history/{jid}/step')).status_code == 429
        raw = payload(page()); return history_sources.select_result(model, maker, raw), raw
    monkeypatch.setattr(history_sources, 'research', research)
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['updated'] == 1

def test_pause_skip_missing_job_and_attribution_after_manual_edit(client, monkeypatch, clock):
    job = target(client); jid = job['id']
    assert client.get('/api/admin/history/999/report').status_code == 404
    current = {'item_id': job['current']['id']}
    assert client.post(f'/api/admin/history/{jid}/skip', json=current).status_code == 409
    assert client.post(f'/api/admin/history/{jid}/pause').json()['status'] == 'paused'
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['pending'] == 1
    assert client.post(f'/api/admin/history/{jid}/skip', json=current).json()['counts']['skipped'] == 1
    fake_found(monkeypatch); job = client.post('/api/admin/history').json()
    assert client.post(f"/api/admin/history/{job['id']}/step").json()['counts']['updated'] == 1
    with SessionLocal() as db: db.get(Computer, 1).description = 'Un nuovo testo manuale.'; db.commit()
    assert client.get('/api/computers/1').json()['description_attribution'] is None

def test_stale_tab_cannot_skip_the_following_system(client):
    with SessionLocal() as db: db.get(Computer, 2).description = None; db.commit()
    job = target(client); jid = job['id']; current = {'item_id': job['current']['id']}
    client.post(f'/api/admin/history/{jid}/pause')
    first = client.post(f'/api/admin/history/{jid}/skip', json=current).json()
    assert first['counts'] == {'pending': 1, 'preserved': 8, 'skipped': 1}
    assert client.post(f'/api/admin/history/{jid}/skip', json=current).status_code == 409
    assert client.get('/api/admin/history').json()['job']['current']['computer_id'] == 2

def test_http_uses_only_official_italian_api_and_never_ai(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.host == 'it.wikipedia.org' and request.url.params['maxlag'] == '5'
        assert request.headers['User-Agent'].startswith('HardwareHistoryExplorer/')
        return httpx.Response(200, json=payload(page()))
    original = httpx.AsyncClient
    monkeypatch.setattr(history_sources.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    result, raw = asyncio.run(history_sources.research('Synthetic History One', 'IBM'))
    assert result['status'] == 'found' and len(seen) == 1

@pytest.mark.parametrize('response,expected', [(httpx.Response(429, headers={'Retry-After': '120'}), '120'), (httpx.Response(200, json={'error': {'code': 'maxlag'}}), '30'), (httpx.Response(200, content=b'<html>blocked</html>'), '30'), (httpx.Response(302, headers={'Location': 'http://127.0.0.1/private'}), '60')])
def test_http_retry_after_invalid_json_and_redirects_are_safe(monkeypatch, response, expected):
    original = httpx.AsyncClient
    monkeypatch.setattr(history_sources.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(lambda request: response), **kw))
    with pytest.raises(HTTPException) as error: asyncio.run(history_sources.research('Synthetic History One', 'IBM'))
    assert error.value.headers['Retry-After'] == expected

def test_additive_migration_is_repeatable_and_preserves_catalog(client):
    from migrations.history_research import migrate
    from app.main import engine
    before = client.get('/api/computers/1').json(); migrate(engine); migrate(engine)
    assert client.get('/api/computers/1').json() == before

def test_hp85_italian_evidence_is_specific_and_never_used_for_other_models():
    import json
    from pathlib import Path
    raw = json.loads((Path(__file__).parent / 'fixtures/wikipedia-it-hp9800.json').read_text())
    result = history_sources.select_result('HP 85', 'HP', raw)
    assert result['status'] == 'found' and result['revision_id'] == 148020204
    assert 'Corvallis' in result['description'] and 'BASIC' in result['description']
    assert '1979' not in result['description']  # no inferred launch date
    assert history_sources.select_result('HP 87', 'HP', raw)['status'] == 'no_match'
    assert history_sources.select_result('HP 85', 'Unrelated manufacturer', raw)['status'] == 'no_match'
    raw['query']['pages'][0]['extract'] = 'Passaggi di sostegno non più disponibili.'
    assert history_sources.select_result('HP 85', 'HP', raw)['status'] == 'no_match'

def test_pc5150_alias_requires_explicit_italian_identification_and_keeps_xt_separate():
    import json
    from pathlib import Path
    raw = json.loads((Path(__file__).parent / 'fixtures/wikipedia-it-pcibm.json').read_text())
    assert history_sources.select_result('IBM PC 5150', 'IBM', raw)['status'] == 'found'
    assert history_sources.select_result('IBM PC XT', 'IBM', raw)['status'] == 'no_match'
    raw['query']['pages'][0]['extract'] = raw['query']['pages'][0]['extract'].replace('IBM 5150', 'IBM PC')
    assert history_sources.select_result('IBM PC 5150', 'IBM', raw)['status'] == 'no_match'

def test_supercomputer_context_and_sentence_boundary_truncation():
    text = TEXT.replace('un computer', 'un supercomputer')
    assert history_sources.intro(text) == text
    long_text = ' '.join([TEXT] * 10)
    excerpt = history_sources.intro(long_text)
    assert len(excerpt) <= 1500 and long_text.startswith(excerpt) and excerpt.endswith('.')

def test_http_oversized_response_and_invalid_query_do_not_loop_forever(monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setattr(history_sources, 'MAX_RESPONSE', 100)
    monkeypatch.setattr(history_sources.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 101)), **kw))
    with pytest.raises(HTTPException): asyncio.run(history_sources.research('Synthetic History One', 'IBM'))
    monkeypatch.setattr(history_sources.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'error': {'code': 'badsearch'}})), **kw))
    assert asyncio.run(history_sources.research('Synthetic History One', 'IBM'))[0]['status'] == 'search_error'
