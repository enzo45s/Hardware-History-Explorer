"""Synthetic prices verify provenance and conservative workbook imports."""
import json
import struct

import pytest
from sqlalchemy import select

from app.main import SessionLocal
from app.models import Computer, Market, Release
from app.importing.prices import workbook_records
from price_workbook_fixture import entry, workbook


def upload(client, raw=None, **form):
    response = client.post('/api/admin/imports/upload', files={'file': ('research.xlsx', raw or workbook())},
        data={'provider': 'historical_prices', 'rights_confirmed': 'true', **form})
    assert response.status_code == 201, response.text
    return response.json()


def apply(client, job):
    response = client.post(f"/api/admin/imports/{job['id']}/apply")
    assert response.status_code == 200, response.text
    return response.json()


def test_only_master_is_read_and_source_column_rotation_is_repaired():
    shifted = entry(**{'Fonte URL': 'Synthetic alternate configuration', 'Affidabilità fonte': 'https://example.org/synthetic-list',
        'Altri listini / varianti': 'Media-alta'})
    records, report = workbook_records(workbook([shifted, entry(**{'Modello': 'Missing', 'Prezzo al lancio': '', 'Stato ricerca': 'Da ricercare'})], extra_sheet=True))
    assert len(records) == 1 and report['without_price'] == 1
    assert report['ignored_sheets'] == ['Quinta ricerca estesa'] and report['source_columns_repaired'] == 1
    record = records[0]
    assert record['source']['url'] == 'https://example.org/synthetic-list'
    assert 'Media-alta' in record['facts'][0]['statement'] and 'Synthetic alternate configuration' in record['facts'][0]['statement']
    assert json.loads(record['evidence'])['original']['Affidabilità fonte'] == 'https://example.org/synthetic-list'
    assert record['releases'][0]['market'] == 'Stati Uniti' and 'release_date' not in record['releases'][0]


@pytest.mark.parametrize('status', ['Prezzo della famiglia/variante diversa', 'Prezzo solo indicativo', 'Prezzo base senza accessorio', 'Indizio da verificare'])
def test_variant_and_partial_prices_remain_context_only(status):
    records, report = workbook_records(workbook([entry(**{'Stato ricerca': status})]))
    assert 'releases' not in records[0] and records[0]['facts']
    assert report['price_records'] == 0 and report['context_only_records'] == 1


def test_later_price_list_does_not_become_a_launch_date():
    record = workbook_records(workbook([entry(**{'Stato ricerca': "Listino d'epoca, non lancio"})]))[0][0]
    assert record['releases'][0]['price_type'] == 'listino successivo'
    assert 'release_date' not in record['releases'][0] and '1981' in record['facts'][0]['statement']


@pytest.mark.parametrize('changes', [{'Prezzo al lancio': '1,234'}, {'Prezzo al lancio': 'NaN'}, {'Prezzo al lancio': '-1'}, {'Prezzo al lancio': '1e-9999'},
    {'Valuta': ''}, {'Mercato / Paese': ''}, {'Fonte URL': 'javascript:alert(1)'},
    {'Fonte URL': 'https://user:secret@example.org'}, {'Affidabilità fonte': 'https://example.org/other'}])
def test_ambiguous_or_unsafe_prices_become_visible_invalid_rows(changes):
    records, report = workbook_records(workbook([entry(**changes)]))
    assert records[0]['error'] and report['invalid_records'] == 1 and report['price_records'] == 0


def test_formulas_and_oversized_archives_are_never_evaluated():
    records, _ = workbook_records(workbook(formula=True))
    assert 'formule' in records[0]['error']
    data = bytearray(workbook()); central = data.index(b'PK\x01\x02')
    struct.pack_into('<I', data, central + 24, 70 * 1024 * 1024)
    with pytest.raises(ValueError, match='decompressione'): workbook_records(bytes(data))
    with pytest.raises(ValueError): workbook_records(b'not an Excel workbook')
    with pytest.raises(ValueError, match='Prezzi per modello'): workbook_records(workbook(sheet_name='Unknown'))


def test_upload_matches_by_name_not_workbook_id_keeps_original_and_can_retry(client):
    raw = workbook()
    job = upload(client, raw, existing_only='false')
    assert job['existing_only'] and job['price_workbook_report']['price_records'] == 1
    detail = client.get(f"/api/admin/imports/{job['id']}").json()
    cid = detail['rows'][0]['computer_id']
    assert cid != 1  # ID in the workbook is 1; model is IBM PC 5150, not System/360.
    assert client.get(f'/api/computers/{cid}').json()['model_name'] == 'IBM PC 5150'
    assert client.get(f"/api/admin/imports/{job['id']}/original").content == raw
    assert 'import-original.xlsx' in client.get(f"/api/admin/imports/{job['id']}/original").headers['content-disposition']
    retry = client.post(f"/api/admin/imports/{job['id']}/retry").json()
    assert retry['retry_of'] == job['id'] and retry['existing_only']
    assert retry['price_workbook_report'] == job['price_workbook_report']


def test_price_import_preserves_timeline_configuration_photos_and_does_not_duplicate(client):
    cid = next(row['id'] for row in client.get('/api/computers').json()['items'] if row['model_name'] == 'IBM PC 5150')
    client.post(f'/api/computers/{cid}/images', json={'image_url': 'https://example.org/original.jpg'})
    before = client.get(f'/api/computers/{cid}').json()
    job = upload(client)
    assert apply(client, job)['counts'] == {'updated': 1}
    after = client.get(f'/api/computers/{cid}').json()
    for key in ('year', 'first_release', 'description', 'configurations', 'images', 'categories'):
        assert after[key] == before[key]
    price = next(release for release in after['releases'] if release['price'] is not None)
    assert price['price'] == 1000.5 and price['currency'] == 'USD' and price['release_date'] is None
    assert price['sources'][0]['access_date'] is None
    assert 'monitor' in after['facts'][0]['statement']
    assert apply(client, upload(client))['counts'] == {'unchanged': 1}
    repeated = client.get(f'/api/computers/{cid}').json()
    assert len(repeated['releases']) == len(after['releases']) and len(repeated['facts']) == 1
    assert client.get('/api/computers').json()['total'] == 10
    assertions = client.get(f"/api/admin/imports/{job['id']}").json()['rows'][0]['claims']
    assert assertions and not any(claim['status'] == 'verified' for claim in assertions)


def test_existing_price_conflict_keeps_saved_value_and_configuration_context(client):
    with SessionLocal() as db:
        computer = db.scalar(select(Computer).where(Computer.model_name == 'IBM PC 5150'))
        market = Market(name='Stati Uniti'); db.add(market); db.flush()
        computer.releases.append(Release(market=market, price=900, currency='USD', price_type='prezzo riportato'))
        db.commit(); cid = computer.id
    job = upload(client); apply(client, job)
    assert next(row['price'] for row in client.get(f'/api/computers/{cid}').json()['releases'] if row['price']) == 900
    claims = client.get(f"/api/admin/imports/{job['id']}").json()['rows'][0]['claims']
    price = next(claim for claim in claims if claim['field'] == 'price_bundle')
    assert price['status'] == 'conflict' and price['value']['price'] == 1000.5
    assert 'Synthetic configuration with monitor' in price['evidence']


def test_price_badge_is_absent_from_display_but_originals_claim_states_and_replay_stay_unchanged(client):
    from app.models import Fact
    from app.assistant_context import retrieve
    from app.main import EAGER, full
    job = upload(client)
    apply(client, job)
    detail = client.get(f"/api/admin/imports/{job['id']}").json()
    computer_id = detail['rows'][0]['computer_id']
    before_claims = [(claim['id'], claim['status']) for claim in detail['rows'][0]['claims']]
    data = client.get(f'/api/computers/{computer_id}').json()
    note = next(fact for fact in data['facts'] if fact['type'] == 'Contesto del prezzo')
    assert note['statement'].startswith('Ricerca da verificare.')
    assert note['display_statement'] == note['statement'].removeprefix('Ricerca da verificare. ')
    assert 'Synthetic configuration with monitor' in note['display_statement']
    assert note['sources'] and any(release['price'] == 1000.5 for release in data['releases'])
    with SessionLocal() as db:
        stored = db.scalar(select(Fact).where(Fact.computer_id == computer_id))
        assert stored.statement == note['statement']
        context = retrieve(db, data['model_name'], EAGER, full)
        item = next(row for row in context['computers'] if row['id'] == computer_id)
        assert item['facts'][0]['statement'] == note['display_statement']
        assert all(claim['status'] == 'pending' for claim in item['import_assertions'])
    after = client.get(f"/api/admin/imports/{job['id']}").json()
    assert [(claim['id'], claim['status']) for claim in after['rows'][0]['claims']] == before_claims
    assert apply(client, upload(client))['counts'] == {'unchanged': 1}
    assert len(client.get(f'/api/computers/{computer_id}').json()['facts']) == 1


def test_unknown_model_is_skipped_even_when_creation_is_requested(client):
    job = upload(client, workbook([entry(**{'Modello': 'Unknown synthetic system'})]), existing_only='false')
    assert apply(client, job)['counts'] == {'skipped': 1}
    assert client.get('/api/computers').json()['total'] == 10


@pytest.mark.parametrize('maker,original,exported', [('Apple','Apple ][',']['), ('Apple','Apple //c','c'),
    ('Apple','Apple //c Plus','c Plus'), ('Apple','Apple //e','e'), ('Data General','Data General/One','One')])
def test_legacy_export_names_match_existing_models_without_renaming(client, maker, original, exported):
    manufacturer = next((row for row in client.get('/api/manufacturers').json() if row['name'] == maker), None)
    if manufacturer is None: manufacturer = client.post('/api/manufacturers', json={'name': maker}).json()
    if original == 'Apple ][':
        existing = next(row for row in client.get('/api/computers').json()['items'] if row['model_name'] == 'Apple II')
        c = client.put(f"/api/computers/{existing['id']}", json={'model_name': original, 'manufacturer_id': manufacturer['id']}).json()
    else:
        c = client.post('/api/computers', json={'model_name': original, 'manufacturer_id': manufacturer['id']}).json()
    job = upload(client, workbook([entry(**{'Produttore': maker, 'Modello': exported})]))
    assert client.get(f"/api/admin/imports/{job['id']}").json()['rows'][0]['computer_id'] == c['id']
    assert apply(client, job)['counts'] == {'updated': 1}
    assert client.get(f"/api/computers/{c['id']}").json()['model_name'] == original


def test_ambiguous_legacy_export_key_is_not_selected_automatically(client):
    maker = next(row for row in client.get('/api/manufacturers').json() if row['name'] == 'Apple')
    for name in ('Apple //c', 'Apple c'):
        client.post('/api/computers', json={'model_name': name, 'manufacturer_id': maker['id']})
    job = upload(client, workbook([entry(**{'Produttore': 'Apple', 'Modello': 'c'})]))
    assert job['counts'] == {'ambiguous': 1}
    assert apply(client, job)['counts'] == {'ambiguous': 1}


def test_legacy_brackets_cannot_hide_a_known_apple_ii_duplicate(client):
    maker = next(row for row in client.get('/api/manufacturers').json() if row['name'] == 'Apple')
    client.post('/api/computers', json={'model_name': 'Apple ][', 'manufacturer_id': maker['id']})
    job = upload(client, workbook([entry(**{'Produttore': 'Apple', 'Modello': ']['})]))
    assert job['counts'] == {'ambiguous': 1}
