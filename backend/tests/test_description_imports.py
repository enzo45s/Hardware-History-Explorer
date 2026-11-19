"""Synthetic, offline JSON prose: safe matching, original text and provenance."""
import asyncio
import json
import pytest
from sqlalchemy import func, select

from app.main import SessionLocal, EAGER, full
from app.models import Computer, Manufacturer, Source
from app.import_models import ImportClaim, ComputerAlias
from app.importing.identity import provider_computer_key
from app.assistant_context import retrieve


TEXT = 'Questo computer sintetico fu introdotto nel 1981 per verificare l’importazione dei cenni storici. Non descrive fatti relativi a sistemi reali.'


def entry(**changes):
    return {'manufacturer': 'IBM', 'model_name': 'Synthetic Description 1', 'description': TEXT,
            'source': {'title': 'Fonte sintetica della prova', 'url': 'https://example.org/synthetic-description', 'source_type': 'website'}, **changes}


def computer(model='Synthetic Description 1', maker='IBM', description=None):
    with SessionLocal() as db:
        manufacturer = db.scalar(select(Manufacturer).where(Manufacturer.name == maker))
        if manufacturer is None:
            manufacturer = Manufacturer(name=maker)
        c = Computer(manufacturer=manufacturer, model_name=model, description=description)
        db.add(c); db.commit()
        return c.id


def upload(client, records=None, **form):
    raw = json.dumps(records if records is not None else [entry()], ensure_ascii=False).encode()
    response = client.post('/api/admin/imports/upload', files={'file': ('descriptions.json', raw, 'application/json')},
        data={'provider': 'historical_descriptions', 'rights_confirmed': 'true', **form})
    assert response.status_code == 201, response.text
    return response.json()


def detail(client, job):
    return client.get(f'/api/admin/imports/{job["id"]}').json()


def apply(client, job):
    result = client.post(f'/api/admin/imports/{job["id"]}/apply')
    assert result.status_code == 200, result.text
    return result.json()


def test_preview_original_wrapper_bom_and_forced_existing_only(client):
    cid = computer()
    before = client.get(f'/api/computers/{cid}').json()
    raw = ('\ufeff' + json.dumps({'records': [entry()]})).encode()
    result = client.post('/api/admin/imports/upload', files={'file': ('descriptions.json', raw)},
        data={'provider': 'historical_descriptions', 'rights_confirmed': 'true', 'existing_only': 'false'})
    assert result.status_code == 201 and result.json()['existing_only']
    job = result.json(); row = detail(client, job)['rows'][0]
    assert row['computer_id'] == cid and row['raw'] == entry()
    assert row['description_preview']['action'] == 'fill'
    assert row['description_preview']['proposed'] == TEXT
    assert client.get(f'/api/computers/{cid}').json() == before
    assert client.get(f'/api/admin/imports/{job["id"]}/original').content == raw
    assert 'import-original.json' in client.get(f'/api/admin/imports/{job["id"]}/original').headers['content-disposition']
    retry = client.post(f'/api/admin/imports/{job["id"]}/retry').json()
    assert retry['retry_of'] == job['id'] and retry['existing_only']


@pytest.mark.parametrize('maker,model,incoming_maker,incoming_model', [
    ('Acorn Computers Ltd.', 'A3010', 'Acorn', 'Acorn A3010'),
    ('Apple Computer', 'Apple II', 'Apple', 'Apple ]['),
    ('Sun Microsystems Inc.', 'SPARCstation 20', 'Sun', 'Sun SPARCstation20'),
    ('NeXT Software Inc', 'NeXTcube', 'NeXT', 'NeXT cube'),
    ('IBM', 'IBM PC 5150', 'International Business Machines Corporation', 'PC 5150'),
    ('Acorn Computers', 'System 3', 'Acorn', 'Acorn System 3 (6502 CPU)'),
])
def test_matching_short_brands_spacing_and_public_names(client, maker, model, incoming_maker, incoming_model):
    with SessionLocal() as db:
        existing = db.scalar(select(Computer).where(Computer.model_name == model))
        cid = existing.id if existing else None
    cid = cid or computer(model, maker)
    job = upload(client, [entry(manufacturer=incoming_maker, model_name=incoming_model)])
    assert detail(client, job)['rows'][0]['computer_id'] == cid


def test_only_description_changes_and_source_remains_pending_in_assistant(client):
    with SessionLocal() as db:
        c = db.get(Computer, 1)
        model, maker = c.model_name, c.manufacturer.name
        placeholder = f'{model} è un calcolatore di {maker}. Le configurazioni censite riportano Synthetic CPU.'
        c.description = placeholder; db.commit()
    before = client.get('/api/computers/1').json()
    job = upload(client, [entry(model_name=model, manufacturer=maker)])
    assert detail(client, job)['rows'][0]['description_preview']['action'] == 'replace_template'
    assert apply(client, job)['counts'] == {'updated': 1}
    after = client.get('/api/computers/1').json()
    assert after['description'] == TEXT
    for field in before:
        if field not in ('description', 'display_description', 'sources', 'description_attribution'):
            assert after[field] == before[field], field
    claims = detail(client, job)['rows'][0]['claims']
    assert len(claims) == 1 and claims[0]['field'] == 'description'
    assert claims[0]['status'] == 'pending' and claims[0]['previous'] == {'value': placeholder}
    assert claims[0]['source']['url'] == entry()['source']['url']
    imported_source = next(s for s in after['sources'] if s['url'] == entry()['source']['url'])
    assert imported_source['access_date'] is None
    with SessionLocal() as db:
        context = retrieve(db, model, EAGER, full)['computers']
        found = next(c for c in context if c['id'] == 1)
        assert found['description'] == TEXT
        assert any(c['field'] == 'description' and c['status'] == 'pending' for c in found['import_assertions'])


def test_curated_text_is_a_conflict_and_requires_explicit_review(client):
    current = 'Una descrizione curata manualmente da conservare.'
    cid = computer(description=current)
    job = upload(client)
    assert detail(client, job)['rows'][0]['description_preview']['action'] == 'conflict'
    assert apply(client, job)['counts'] == {'unchanged': 1}
    assert client.get(f'/api/computers/{cid}').json()['description'] == current
    row = detail(client, job)['rows'][0]; claim = row['claims'][0]
    assert claim['status'] == 'conflict'
    reviewed = client.post(f'/api/admin/imports/claims/{claim["id"]}/review', json={'decision': 'accept', 'note': 'Confronto manuale della fonte sintetica.'})
    assert reviewed.status_code == 200
    assert client.get(f'/api/computers/{cid}').json()['description'] == TEXT


def test_manual_edit_after_preview_wins_and_deleted_card_is_not_recreated(client):
    cid = computer(); job = upload(client)
    with SessionLocal() as db:
        db.get(Computer, cid).description = 'Testo modificato dopo l’anteprima.'; db.commit()
    apply(client, job)
    assert client.get(f'/api/computers/{cid}').json()['description'] == 'Testo modificato dopo l’anteprima.'
    assert detail(client, job)['rows'][0]['claims'][0]['status'] == 'conflict'
    other = upload(client)
    assert client.delete(f'/api/computers/{cid}').status_code == 204
    count = client.get('/api/computers').json()['total']
    assert apply(client, other)['counts'] == {'skipped': 1}
    assert client.get('/api/computers').json()['total'] == count


def test_ambiguous_matching_and_manual_choice_do_not_rename_cards(client):
    first = computer(); second = computer('IBM Synthetic Description 1')
    job = upload(client); row = detail(client, job)['rows'][0]
    assert row['status'] == 'ambiguous' and set(row['candidates']) == {first, second}
    assert row['description_preview']['action'] == 'ambiguous'
    assert client.post(f'/api/admin/imports/{job["id"]}/rows/{row["id"]}/match', json={'computer_id': second}).status_code == 200
    assert apply(client, job)['counts'] == {'updated': 1}
    assert client.get(f'/api/computers/{first}').json()['description'] is None
    chosen = client.get(f'/api/computers/{second}').json()
    assert chosen['description'] == TEXT and chosen['model_name'] == 'IBM Synthetic Description 1'


def test_approved_aliases_resolve_without_mutating_or_creating_them(client):
    cid = computer('Synthetic Canonical')
    with SessionLocal() as db:
        maker, model = provider_computer_key('historical_prices', 'IBM', 'Synthetic Former Name')
        db.add(ComputerAlias(manufacturer_key=maker, model_key=model, original_name='Synthetic Former Name',
            computer_id=cid, original={'manufacturer_name': 'IBM'})); db.commit()
    job = upload(client, [entry(model_name='Synthetic Former Name')])
    assert detail(client, job)['rows'][0]['computer_id'] == cid
    assert apply(client, job)['counts'] == {'updated': 1}
    assert client.get(f'/api/computers/{cid}').json()['model_name'] == 'Synthetic Canonical'


def test_unmatched_is_skipped_and_replays_preserve_counts_and_sources(client):
    cid = computer(); job = upload(client, [entry(), entry(model_name='Synthetic Missing')])
    count = client.get('/api/computers').json()['total']
    assert apply(client, job)['counts'] == {'updated': 1, 'skipped': 1}
    with SessionLocal() as db:
        source_ids = [s.id for s in db.scalars(select(Source))]
        claims = db.scalar(select(func.count()).select_from(ImportClaim))
    apply(client, job)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ImportClaim)) == claims
    assert apply(client, upload(client))['counts'] == {'unchanged': 1}
    assert client.get('/api/computers').json()['total'] == count
    assert client.get(f'/api/computers/{cid}').json()['description'] == TEXT
    with SessionLocal() as db:
        assert [s.id for s in db.scalars(select(Source))] == source_ids


@pytest.mark.parametrize('changes', [
    {'description': ''}, {'description': '   '}, {'description': None}, {'description': 42},
    {'source': {'title': 'Synthetic missing URL'}},
    {'source': {'title': 'Unsafe URL', 'url': 'javascript:alert(1)'}},
    {'source': {'title': 'Unsafe URL', 'url': 'https://user:secret@example.org'}},
    {'verified': True}, {'computer_id': 1}, {'releases': []}, {'configurations': []},
])
def test_invalid_records_are_visible_without_applying_unrelated_fields(client, changes):
    computer(); job = upload(client, [entry(**changes), entry()])
    assert job['counts'] == {'invalid': 1, 'ready': 1}
    assert detail(client, job)['rows'][0]['error']
    assert apply(client, job)['counts'] == {'invalid': 1, 'updated': 1}


def test_wrong_format_rights_and_batch_limit_are_checked(client):
    for filename, records, rights in [('bad.csv', [entry()], 'true'), ('empty.json', [], 'true'),
        ('too-many.json', [entry()] * 1001, 'true'), ('no-rights.json', [entry()], 'false')]:
        r = client.post('/api/admin/imports/upload', files={'file': (filename, json.dumps(records))},
            data={'provider': 'historical_descriptions', 'rights_confirmed': rights})
        assert r.status_code == 422


def test_hundred_records_build_one_matching_index_and_share_one_source(client, monkeypatch):
    from app.importing import descriptions
    calls = []; original = descriptions.candidate_index
    def indexed(db):
        calls.append(True)
        return original(db)
    monkeypatch.setattr(descriptions, 'candidate_index', indexed)
    with SessionLocal() as db:
        maker = db.scalar(select(Manufacturer).where(Manufacturer.name == 'IBM'))
        db.add_all([Computer(manufacturer=maker, model_name=f'Synthetic Batch {n}') for n in range(100)]); db.commit()
    job = upload(client, [entry(model_name=f'IBM Synthetic Batch {n}') for n in range(100)])
    assert len(calls) == 1 and job['counts'] == {'ready': 100}
    assert apply(client, job)['counts'] == {'updated': 100}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Source).where(Source.url == entry()['source']['url'])) == 1


def test_imported_text_wins_over_an_automatic_request_already_in_flight(client, monkeypatch):
    from app import history_sources
    from test_history import target, page, payload
    research_job = target(client)
    imported = upload(client, [entry(model_name='Synthetic History One')])
    async def research(model, maker):
        result = await asyncio.to_thread(client.post, f'/api/admin/imports/{imported["id"]}/apply')
        assert result.status_code == 200 and result.json()['counts'] == {'updated': 1}
        raw = payload(page())
        return history_sources.select_result(model, maker, raw), raw
    monkeypatch.setattr(history_sources, 'research', research)
    outcome = client.post(f'/api/admin/history/{research_job["id"]}/step').json()
    assert outcome['counts']['changed'] == 1 and 'updated' not in outcome['counts']
    assert client.get('/api/computers/1').json()['description'] == TEXT
