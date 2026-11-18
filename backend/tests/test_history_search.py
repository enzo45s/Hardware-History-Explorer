"""Keyword fallbacks, model-specific family passages and durable retries."""
import asyncio
import json
from pathlib import Path
from datetime import timedelta
import httpx
import pytest
from sqlalchemy import func, select
from app import history_sources
from app.main import SessionLocal
from app.models import Source
from app.history_models import HistoryItem
from app.import_models import ImportClaim
from test_history import page, payload, target, fake_found, clock


def wiki_fixture(name):
    return json.loads((Path(__file__).parent / 'fixtures' / name).read_text())


def test_keyword_plan_has_canonical_brand_and_no_literal_restrictions():
    plan = history_sources.search_plan('Apple //c', 'Apple Computer Inc')
    assert plan[1]['query'] == 'Apple IIc'
    assert '"' not in plan[1]['query'] and 'computer' not in plan[1]['query'].lower()
    assert history_sources.search_plan('PowerBook180', 'Apple Computer Inc')[2]['query'] == 'PowerBook 180'
    assert history_sources.search_plan('Atari 800XL', 'Atari Corporation')[1]['query'] == 'Atari 800XL'
    assert history_sources.maker_in_text('Apple Computer Inc', 'Un computer prodotto da Apple Inc.')
    assert history_sources.model_key('Atari', 'Atari800XL') == history_sources.model_key('Atari', 'Atari 800XL')
    assert history_sources.model_key('Apple', 'AppleIIc') == history_sources.model_key('Apple', 'Apple //c')
    assert history_sources.model_key('Apple', 'AppleIIc') != history_sources.model_key('Apple', 'Apple IIe')


@pytest.mark.parametrize('model,maker,fixture,title', [
    ('PowerBook180', 'Apple Computer Inc', 'wikipedia-it-powerbook180.json', 'PowerBook 180'),
    ('BBC Model B', 'Acorn Computers', 'wikipedia-it-bbc-micro.json', 'BBC Micro'),
    ('130XE', 'Atari', 'wikipedia-it-atari-family.json', 'Atari 8-bit'),
    ('Atari 400', 'Atari', 'wikipedia-it-atari-family.json', 'Atari 8-bit'),
    ('Atari 800XL', 'Atari', 'wikipedia-it-atari-family.json', 'Atari 8-bit'),
])
def test_real_italian_sources_keep_model_specific_context(model, maker, fixture, title):
    result = history_sources.select_result(model, maker, wiki_fixture(fixture), full_page=True)
    assert result['status'] == 'found' and result['title'] == title
    assert 180 <= len(result['description']) <= 1500
    assert 'oldid=' in result['url'] and result['license_url'].endswith('/by-sa/4.0/')
    if title == 'Atari 8-bit':
        assert '#' in result['url']
        assert history_sources.model_key(maker, model)[1].casefold() in result['description'].casefold().replace(' ', '')
    if model == 'Atari 800XL': assert 'computer più venduto di Atari' in result['description'] and '128kB' not in result['description']
    if model == '130XE': assert '5 gennaio 1985' in result['description']
    if model == 'BBC Model B': assert 'Model B si affermò' in result['description']


def test_family_evidence_requires_relationship_and_keeps_variants_separate():
    raw = wiki_fixture('wikipedia-it-atari-family.json')
    assert history_sources.select_result('Atari 800XE', 'Atari', raw, full_page=True)['status'] == 'no_match'
    assert history_sources.select_result('Atari 800XL', 'Unrelated maker', raw, full_page=True)['status'] == 'no_match'
    raw['query'].pop('redirects')
    assert history_sources.select_result('Atari 800XL', 'Atari', raw, full_page=True)['status'] == 'no_match'
    bbc = wiki_fixture('wikipedia-it-bbc-micro.json')
    bbc['query']['pages'][0]['extract'] = '\n'.join(line for line in bbc['query']['pages'][0]['extract'].splitlines() if 'b+' not in line.lower())
    assert history_sources.select_result('BBC Model B+', 'Acorn', bbc, full_page=True)['status'] == 'no_match'


def test_model_passages_accept_spacing_but_not_an_extra_hardware_suffix():
    text = ('La famiglia è una serie di computer di IBM introdotti nel 1981 per usi didattici.\n\n'
            '== Modelli ==\nSynthetic Words 12 fu introdotto nel 1984 e commercializzato per un impiego didattico esclusivamente sintetico in questa prova.')
    raw = payload(page('Synthetic Family', text=text))
    raw['query']['redirects'] = [{'from': 'Synthetic Words 12', 'to': 'Synthetic Family', 'tofragment': 'Modelli'}]
    assert history_sources.select_result('Synthetic Words12', 'IBM', raw, full_page=True)['status'] == 'found'
    raw['query']['pages'][0]['extract'] = text.replace('Words 12 fu', 'Words 12X fu')
    assert history_sources.select_result('Synthetic Words12', 'IBM', raw, full_page=True)['status'] == 'no_match'


def test_numeric_result_cannot_replace_manufacturer_qualified_lookup(monkeypatch):
    seen = []
    def handler(request):
        seen.append(dict(request.url.params))
        if len(seen) == 1:
            return httpx.Response(200, json=payload(page('400', text='400 è un numero naturale successivo a 399 e precedente a 401.')))
        return httpx.Response(200, json=wiki_fixture('wikipedia-it-atari-family.json'))
    install_transport(monkeypatch, handler)
    first, _ = asyncio.run(history_sources.research('Atari 400', 'Atari', attempt=2))
    assert first['status'] == 'no_match' and first['full_title'] is None
    second, _ = asyncio.run(history_sources.research('Atari 400', 'Atari', attempt=3, full_title=first['full_title']))
    assert seen[1]['titles'] == 'Atari 400' and second['status'] == 'found'


def install_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(history_sources.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def test_keyword_attempt_survives_pause_and_retains_all_original_responses(client, monkeypatch, clock):
    requests = []
    def handler(request):
        requests.append(dict(request.url.params))
        if len(requests) == 1: return httpx.Response(200, json=payload())
        if len(requests) == 2: return httpx.Response(429, headers={'Retry-After': '60'})
        assert request.url.params['gsrsearch'] == 'IBM Synthetic History One'
        return httpx.Response(200, json=payload(page()))
    install_transport(monkeypatch, handler)
    job = target(client); jid = job['id']
    first = client.post(f'/api/admin/history/{jid}/step').json()
    assert first['counts']['pending'] == 1 and first['current']['attempt'] == 2
    assert first['current']['next_query'] == 'IBM Synthetic History One'
    assert client.get('/api/admin/history').json()['job']['current']['attempt'] == 2
    assert client.post(f'/api/admin/history/{jid}/step').status_code == 429 and len(requests) == 1
    clock[0] += timedelta(seconds=2)
    assert client.post(f'/api/admin/history/{jid}/step').json()['status'] == 'paused'
    client.post(f'/api/admin/history/{jid}/resume'); clock[0] += timedelta(seconds=60)
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['updated'] == 1
    assert requests[0]['gsrsearch'] == '"Synthetic History One" computer' and requests[1]['gsrsearch'] == requests[2]['gsrsearch']
    with SessionLocal() as db:
        item = db.scalar(select(HistoryItem).where(HistoryItem.status == 'updated'))
        assert len(item.raw_payload['attempts']) == 2
        assert item.raw_payload['attempts'][0]['response'] == payload()
        assert item.raw_payload['attempts'][1]['response'] == payload(page())
        assert len(item.result['searches']) == 2 and db.scalar(select(ImportClaim)).status == 'pending'
        assert db.scalar(select(func.count()).select_from(Source)) == 1


def test_no_match_is_final_only_after_all_bounded_attempts(client, monkeypatch, clock):
    requests = []
    def handler(request):
        requests.append(request); return httpx.Response(200, json=payload())
    install_transport(monkeypatch, handler)
    job = target(client); jid = job['id']; total = len(history_sources.search_plan('Synthetic History One', 'IBM'))
    for attempt in range(total):
        result = client.post(f'/api/admin/history/{jid}/step').json()
        if attempt < total - 1: assert result['counts']['pending'] == 1 and result['status'] == 'ready'
        clock[0] += timedelta(seconds=2)
    assert result['counts']['no_match'] == 1 and result['status'] == 'completed' and len(requests) == total
    assert client.get('/api/sources').json() == []


def test_retry_unresolved_keeps_previous_audit_and_does_not_duplicate_success(client, monkeypatch, clock):
    async def empty(*args): return {'status': 'no_match', 'reason': 'Synthetic prior search'}, payload()
    monkeypatch.setattr(history_sources, 'research', empty)
    job = target(client); jid = job['id']
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['no_match'] == 1
    retried = client.post(f'/api/admin/history/{jid}/retry-unresolved')
    assert retried.status_code == 200 and retried.json()['counts']['pending'] == 1 and retried.json()['current']['previous_runs'] == 1
    assert client.post(f'/api/admin/history/{jid}/retry-unresolved').status_code == 409
    fake_found(monkeypatch); clock[0] += timedelta(seconds=2)
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['updated'] == 1
    with SessionLocal() as db:
        item = db.scalar(select(HistoryItem).where(HistoryItem.status == 'updated'))
        assert item.raw_payload['previous_runs'][0]['result']['reason'] == 'Synthetic prior search'
        assert item.raw_payload['previous_runs'][0]['raw_payload'] == payload()
        assert db.scalar(select(func.count()).select_from(ImportClaim)) == 1
    assert client.post(f'/api/admin/history/{jid}/retry-unresolved').json()['counts'] == {'updated': 1, 'preserved': 9}


def test_retry_cannot_interrupt_a_request_in_flight(client, monkeypatch, clock):
    job = target(client); jid = job['id']
    async def research(model, maker):
        await asyncio.to_thread(client.post, f'/api/admin/history/{jid}/pause')
        response = await asyncio.to_thread(client.post, f'/api/admin/history/{jid}/retry-unresolved')
        assert response.status_code == 409
        raw = payload(page()); return history_sources.select_result(model, maker, raw), raw
    monkeypatch.setattr(history_sources, 'research', research)
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['updated'] == 1


def test_retry_preserves_manual_text_written_after_an_unsuccessful_run(client, monkeypatch, clock):
    from app.models import Computer
    async def empty(*args): return {'status': 'no_match'}, payload()
    monkeypatch.setattr(history_sources, 'research', empty)
    job = target(client); jid = job['id']
    client.post(f'/api/admin/history/{jid}/step')
    with SessionLocal() as db:
        db.get(Computer, 1).description = 'Contesto storico scritto a mano.'; db.commit()
    result = client.post(f'/api/admin/history/{jid}/retry-unresolved').json()
    assert result['status'] == 'completed' and result['counts']['no_match'] == 1
    assert client.get('/api/computers/1').json()['description'] == 'Contesto storico scritto a mano.'
