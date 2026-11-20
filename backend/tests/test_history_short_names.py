"""Research names are concise; stored identities and source checks stay strict."""
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app import history_sources as h
from app.main import SessionLocal
from app.history_models import HistoryItem
from test_history import page, payload, target, clock
from test_history_search import install_transport


@pytest.mark.parametrize('model,maker,first,brand', [
    ('SPARCstation 20', 'Sun Microsystems Inc.', 'SPARCstation 20', 'Sun SPARCstation 20'),
    ('Sun Microsystems SPARCstation 20', 'Sun Microsystems', 'Sun SPARCstation 20', 'Sun SPARCstation 20'),
    ('SPARCstation20', 'Sun Microsystem', 'SPARCstation 20', 'Sun SPARCstation 20'),
    ('NeXTcube', 'NeXT Software Inc', 'NeXTcube', 'NeXTcube'),
    ('NeXTstation', 'NeXT Software, Inc.', 'NeXTstation', 'NeXTstation'),
    ('Kaypro II', 'Kaypro Corporation', 'Kaypro II', 'Kaypro II'),
    ('Kaypro Corporation Kaypro II', 'Kaypro Corporation', 'Kaypro II', 'Kaypro II'),
    ('NeXT Software Inc NeXTcube', 'NeXT Software Inc', 'NeXTcube', 'NeXTcube'),
    ('II', 'Kaypro Corp.', 'Kaypro II', 'Kaypro II'),
    ('III', 'Kaypro Corporation', 'Kaypro III', 'Kaypro III'),
    ('PC', 'Kaypro Corporation', 'Kaypro PC', 'Kaypro PC'),
    ('400', 'Atari Corporation', 'Atari 400', 'Atari 400'),
    ('PowerBook180', 'Apple Computer Inc', 'PowerBook 180', 'Apple PowerBook 180'),
    ('Model 12', 'Synthetic Systems Corporation', 'Model 12', 'Synthetic Systems Model 12'),
])
def test_short_distinct_prioritized_queries(model, maker, first, brand):
    plan = h.search_plan(model, maker)
    queries = [s['query'] for s in plan if 'query' in s]
    assert queries[0] == first and brand in queries
    assert len(queries) == len(set(q.casefold() for q in queries))
    assert len(plan) <= 3
    assert all('"' not in q and ' computer' not in q.casefold() for q in queries)


def test_common_brand_matching_preserves_models_divisions_and_unrelated_words():
    assert h.model_key('NeXT Software Inc', 'NeXTcube') == h.model_key('NeXT', 'NeXT cube')
    assert h.model_key('Sun Microsystems Inc.', 'Sun Microsystems SPARCstation 20') == h.model_key('Sun', 'SPARCstation20')
    assert h.model_key('Kaypro Corporation', 'Kaypro II') == h.model_key('Kaypro', 'II')
    assert h.model_key('NeXT', 'NeXTcube') != h.model_key('NeXT', 'NeXTstation')
    assert h.model_key('Sun', 'Sunrise') != h.model_key('Sun', 'rise')
    assert h.maker_aliases('Synthetic Systems Industrial Division Corporation')[0] == 'Synthetic Systems Industrial Division'
    assert h.maker_in_text('Sun Microsystems Inc.', 'Una workstation di Sun introdotta nel 1994.')
    assert not h.maker_in_text('Sun Microsystems', 'Una workstation chiamata Sunrise.')
    assert h.maker_aliases('Sun Microsystems Inc. (Japan)')[0] == 'Sun'


def test_exact_common_title_succeeds_on_first_request_without_changing_catalog(client, monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload(page()))
    install_transport(monkeypatch, handler)
    job = target(client)
    result = client.post(f'/api/admin/history/{job["id"]}/step').json()
    assert result['counts']['updated'] == 1 and len(requests) == 1
    assert requests[0].url.params['gsrsearch'] == 'Synthetic History One'


def test_pending_legacy_cursor_replans_without_losing_audit_or_cooldown(client, monkeypatch, clock):
    job = target(client); jid = job['id']
    old_search = {'strategy': 'full_page', 'titles': 'Obsolete Synthetic Title', 'attempt': 4}
    with SessionLocal() as db:
        item = db.scalar(select(HistoryItem).where(HistoryItem.job_id == jid, HistoryItem.status == 'pending'))
        item.result = {'search_version': 5, 'next_attempt': 4, 'full_title': 'Obsolete Synthetic Title', 'searches': [old_search]}
        item.raw_payload = {'attempts': [{'search': old_search, 'response': payload()}]}
        db.commit()
    current = client.get('/api/admin/history').json()['job']['current']
    assert current['attempt'] == 1 and current['next_query'] == 'Synthetic History One'
    requests = []
    def handler(request):
        requests.append(dict(request.url.params))
        return httpx.Response(200, json=payload() if len(requests) == 1 else payload(page()))
    install_transport(monkeypatch, handler)
    first = client.post(f'/api/admin/history/{jid}/step').json()
    assert first['current']['attempt'] == 2 and first['current']['next_query'] == 'IBM Synthetic History One'
    assert client.post(f'/api/admin/history/{jid}/step').status_code == 429
    clock[0] += timedelta(seconds=2)
    assert client.post(f'/api/admin/history/{jid}/step').json()['counts']['updated'] == 1
    assert requests[1]['gsrsearch'] == 'IBM Synthetic History One'
    with SessionLocal() as db:
        item = db.scalar(select(HistoryItem).where(HistoryItem.job_id == jid, HistoryItem.status == 'updated'))
        assert item.result['search_version'] == h.SEARCH_VERSION
        assert item.result['searches'][0] == old_search
        assert len(item.raw_payload['attempts']) == 3
        assert item.raw_payload['attempts'][0] == {'search': old_search, 'response': payload()}


def test_reordering_alone_does_not_suggest_retry_but_new_short_queries_do():
    plan = h.search_plan('SPARCstation 20', 'Sun Microsystems')
    old = {'search_version': 5, 'searches': list(reversed(plan))}
    assert not h.improved_retry('SPARCstation 20', 'Sun Microsystems', old)
    old['searches'] = [{'strategy': 'literal', 'query': '"SPARCstation 20" computer'},
                       {'strategy': 'brand_model', 'query': 'Sun Microsystems SPARCstation 20'}]
    assert h.improved_retry('SPARCstation 20', 'Sun Microsystems', old)
    assert not h.improved_retry('SPARCstation 20', 'Sun Microsystems', {**old, 'search_version': h.SEARCH_VERSION})
