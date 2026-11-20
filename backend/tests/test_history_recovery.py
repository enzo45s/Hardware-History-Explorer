"""Regressions from an operator report, using sourced Italian responses."""
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import pytest
from sqlalchemy import select, func
from app import history_sources as h
from app.main import SessionLocal
from app.models import Computer
from app.history_models import HistoryItem
from app.import_models import ImportClaim
from test_history import clock, target, fake_found, payload


CASES = json.loads((Path(__file__).parent / 'fixtures/wikipedia-it-history-recovery.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['model_name'])
def test_real_rejected_italian_articles_are_recovered_with_original_revision(case):
    result = h.select_result(case['model_name'], case['manufacturer'], case['response'], full_page=True)
    assert result['status'] == 'found'
    assert 120 <= len(result['description']) <= 1500
    assert f'oldid={result["revision_id"]}' in result['url']
    assert result['license_url'].endswith('/by-sa/4.0/')
    if case['model_name'] == 'Atari 800':
        assert '#' in result['url'] and 'commercializzati prima di novembre 1979' in result['description']


def test_research_aliases_do_not_remove_hardware_suffixes_or_other_macintosh_names():
    assert h.canonical_model('Macintosh PowerBook 180', 'Apple') == 'PowerBook 180'
    assert h.search_plan('Macintosh PowerBook 180c', 'Apple')[1]['query'] == 'Apple PowerBook 180c'
    assert h.model_key('Apple', 'Macintosh PowerBook 180c') != h.model_key('Apple', 'PowerBook 180')
    assert h.model_key('Apple', 'Macintosh II') != h.model_key('Apple', 'Macintosh IIx')
    assert h.model_key('Next Software Inc', 'NeXTcube Turbo') != h.model_key('NeXT', 'NeXTcube')
    powerbook = next(c for c in CASES if c['model_name'] == 'Macintosh PowerBook 180')
    assert h.select_result('Macintosh PowerBook 180c', 'Apple', powerbook['response'], full_page=True)['status'] == 'no_match'


def test_compact_intro_still_requires_history_computer_context_manufacturer_and_exact_model():
    epson = next(c for c in CASES if c['model_name'] == 'Epson HX-20')
    assert h.select_result('Epson HX-20', 'Unrelated maker', epson['response'])['status'] == 'no_match'
    assert h.intro('Un computer Epson presentato nel 1981.') is None
    assert h.intro('Un oggetto Epson presentato nel 1981. ' * 8) is None
    assert h.intro('Un computer Epson disponibile per lo studio. ' * 8) is None


def test_numeric_family_passage_cannot_match_an_extra_suffix():
    case = next(c for c in CASES if c['model_name'] == 'Atari 800')
    raw = deepcopy(case['response'])
    page = raw['query']['pages'][0]
    page['extract'] = page['extract'].replace('800', '800XL')
    assert h.select_result('Atari 800', 'Atari', raw, full_page=True)['status'] == 'no_match'


def test_targeted_retry_suggestions_are_bounded_and_do_not_repeat_current_failures():
    old = {'search_version': 2, 'searches': [{**s, 'attempt': i} for i, s in enumerate(h.search_plan('PowerBook 180', 'Apple'), 1)], 'candidates': []}
    assert not h.improved_retry('PowerBook 180', 'Apple', old)
    old['searches'][0]['query'] = '"Macintosh PowerBook 180" computer'
    old['searches'][1]['query'] = 'Apple Macintosh PowerBook 180'
    assert h.improved_retry('Macintosh PowerBook 180', 'Apple', old)
    assert h.improved_retry('Epson HX-20', 'Epson', {'search_version': 2, 'candidates': [{'title': 'Epson HX-20'}]})
    assert not h.improved_retry('Epson HX-20', 'Epson', {'search_version': h.SEARCH_VERSION, 'candidates': [{'title': 'Epson HX-20'}]})


def test_targeted_retry_keeps_other_missing_records_and_previous_audit(client, monkeypatch, clock):
    with SessionLocal() as db:
        db.get(Computer, 2).description = None; db.commit()
    async def empty(*args, **kwargs): return {'status': 'no_match', 'search_version': 2}, payload()
    monkeypatch.setattr(h, 'research', empty)
    job = target(client); jid = job['id']
    assert client.post(f'/api/admin/history/{jid}/retry-unresolved', json={'only_improved': True}).status_code == 409
    client.post(f'/api/admin/history/{jid}/step'); clock[0] += timedelta(seconds=2)
    assert client.post(f'/api/admin/history/{jid}/step').json()['status'] == 'completed'
    with SessionLocal() as db:
        items = db.scalars(select(HistoryItem).where(HistoryItem.job_id == jid, HistoryItem.status == 'no_match').order_by(HistoryItem.position)).all()
        items[0].result = {**items[0].result, 'candidates': [{'title': 'Synthetic History One', 'url': 'https://example.org/synthetic'}]}
        items[1].result = {**items[1].result, 'searches': h.search_plan(items[1].model_name, items[1].manufacturer)}
        db.commit()
    assert client.get('/api/admin/history').json()['job']['retry_suggested'] == 1
    result = client.post(f'/api/admin/history/{jid}/retry-unresolved', json={'only_improved': True}).json()
    assert result['counts'] == {'pending': 1, 'no_match': 1, 'preserved': 8}
    assert result['current']['previous_runs'] == 1
    fake_found(monkeypatch); clock[0] += timedelta(seconds=2)
    result = client.post(f'/api/admin/history/{jid}/step').json()
    assert result['counts'] == {'updated': 1, 'no_match': 1, 'preserved': 8}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ImportClaim)) == 1
