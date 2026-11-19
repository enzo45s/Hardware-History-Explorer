"""Recover auditable workbook cells; never scrape numbers from arbitrary prose."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app import main
from app.main import SessionLocal
from app.models import Computer, Manufacturer, Market, Release, Fact
from app.import_models import ImportJob, ImportRow, ImportClaim
from app.importing.prices import PRICED, workbook_records
from app.importing.price_recovery import recover_price_contexts
from test_historical_prices import upload, apply
from price_workbook_fixture import entry, workbook


def enterprise_entry(**changes):
    return entry(**{'Produttore': 'Intelligent Software / Enterprise Computers', 'Modello': 'Enterprise Sixty Four',
        'Anno lancio': '1985', 'Prezzo al lancio': '249', 'Valuta': 'GBP', 'Mercato / Paese': 'Regno Unito',
        'Configurazione cui si riferisce': 'Enterprise 64, 64 KB; prezzo al primo lancio (novembre 1984/inizio 1985)',
        'Stato ricerca': 'Prezzo di lancio verificato',
        'Note': 'Recensione 1984: £249; circa £180 nel giugno 1985. Il prezzo pre-vendita annunciato non prova la data di consegna.', **changes})


def target():
    with SessionLocal() as db:
        c = Computer(model_name='Enterprise Sixty Four', manufacturer=Manufacturer(name='Intelligent Software / Enterprise Computers'),
            releases=[Release(market=Market(name='Non specificato dalla fonte (Enterprise fixture)'), release_date=date(1985, 1, 1), release_precision='year')])
        db.add(c); db.commit()
        return c.id


def legacy_import(client, records=None):
    # Emulate the old parser while using its exact stored JSON evidence format.
    with patch('app.importing.prices.price_kind', lambda status: PRICED.get(status)):
        job = upload(client, workbook(records if records is not None else [enterprise_entry()]))
        apply(client, job)
    return job


def recover():
    with SessionLocal() as db:
        return recover_price_contexts(db)


@pytest.mark.parametrize('status', ['Prezzo di lancio verificato', 'Prezzo al lancio verificato',
    'Prezzo di lancio documentato', 'Prezzo di lancio confermato', ' prezzo di lancio con fonte ', 'PREZZO CON FONTE'])
def test_declared_launch_labels_produce_prices_but_not_verification(status):
    records, report = workbook_records(workbook([enterprise_entry(**{'Stato ricerca': status})]))
    assert report['price_records'] == 1 and not report['sources_checked']
    release = records[0]['releases'][0]
    assert (release['price'], release['currency'], release['market']) == (249, 'GBP', 'Regno Unito')
    assert 'release_date' not in release and release['price_type'] == 'prezzo riportato'
    assert '£180' in records[0]['facts'][0]['statement']


def test_legacy_enterprise_context_is_recovered_once_with_source_and_original_notes(client):
    cid = target(); old = legacy_import(client)
    before = client.get(f'/api/computers/{cid}').json()
    assert not any(r['price'] is not None for r in before['releases'])
    with SessionLocal() as db:
        row = db.scalar(select(ImportRow).where(ImportRow.job_id == old['id']))
        original_row = deepcopy(row.normalized)
        original_job = db.get(ImportJob, old['id']).raw_payload
        original_claims = [(c.id, c.status, deepcopy(c.value)) for c in db.scalars(select(ImportClaim).where(ImportClaim.row_id == row.id))]
    recovered = recover()
    assert recovered['candidates'] == 1 and recovered['counts']['updated'] == 1
    after = client.get(f'/api/computers/{cid}').json()
    summary, = after['display_releases']
    assert (summary['market'], summary['release_date'], summary['price'], summary['currency']) == ('Europa', '1985', 249, 'GBP')
    assert summary['price_countries'] == ['Regno Unito'] and summary['date_scope'] == 'model'
    assert after['facts'] == before['facts'] and '£180' in after['facts'][0]['statement']
    price = next(r for r in after['releases'] if r['price'] is not None)
    assert price['price'] == 249 and price['release_date'] is None
    assert price['sources'][0]['id'] == before['facts'][0]['sources'][0]['id']
    detail = client.get(f'/api/admin/imports/{recovered["job_ids"][0]}').json()
    assert detail['verification_counts'].get('verified', 0) == 0
    assert all(c['status'] == 'pending' for c in detail['rows'][0]['claims'])
    with SessionLocal() as db:
        assert db.get(ImportJob, old['id']).raw_payload == original_job
        row = db.scalar(select(ImportRow).where(ImportRow.job_id == old['id']))
        assert row.normalized == original_row
        assert [(c.id, c.status, c.value) for c in db.scalars(select(ImportClaim).where(ImportClaim.row_id == row.id))] == original_claims
        counts = (db.scalar(select(func.count()).select_from(Release)), db.scalar(select(func.count()).select_from(ImportJob)))
    assert recover()['candidates'] == 0
    with SessionLocal() as db:
        assert (db.scalar(select(func.count()).select_from(Release)), db.scalar(select(func.count()).select_from(ImportJob))) == counts


@pytest.mark.parametrize('change', ['rejected', 'estimated', 'edited_note', 'removed_source', 'edited_source_url', 'deleted_note', 'deleted_computer', 'malformed_evidence'])
def test_recovery_respects_manual_decisions_missing_data_and_source_edits(client, change):
    cid = target(); job = legacy_import(client)
    with SessionLocal() as db:
        row = db.scalar(select(ImportRow).where(ImportRow.job_id == job['id']))
        claim = db.scalar(select(ImportClaim).where(ImportClaim.row_id == row.id, ImportClaim.entity == 'Fact', ImportClaim.field == 'statement'))
        fact = db.get(Fact, claim.target_id)
        if change == 'rejected': claim.status = 'rejected'
        elif change == 'estimated': claim.estimated = True
        elif change == 'edited_note': fact.statement += ' Modifica manuale.'
        elif change == 'removed_source': fact.sources.clear()
        elif change == 'edited_source_url': claim.source.url = 'https://example.org/edited-source'
        elif change == 'deleted_note': db.delete(fact)
        elif change == 'deleted_computer': db.delete(db.get(Computer, cid))
        else: row.normalized = {**row.normalized, 'evidence': 'not structured JSON'}
        db.commit()
    assert recover()['candidates'] == 0


def test_conflicting_price_is_not_overwritten_and_deleted_recovered_price_does_not_reappear(client):
    cid = target(); legacy_import(client)
    with SessionLocal() as db:
        computer = db.get(Computer, cid)
        computer.releases.append(Release(market=Market(name='Regno Unito'), price=300, currency='GBP', price_type='prezzo riportato'))
        db.commit()
    report = recover()
    assert report['candidates'] == 1
    assert next(r for r in client.get(f'/api/computers/{cid}').json()['releases'] if r['price'])['price'] == 300
    detail = client.get(f'/api/admin/imports/{report["job_ids"][0]}').json()
    claim = next(c for c in detail['rows'][0]['claims'] if c['field'] == 'price_bundle')
    assert claim['status'] == 'conflict' and claim['value']['price'] == 249
    with SessionLocal() as db:
        db.delete(db.scalar(select(Release).where(Release.computer_id == cid, Release.price.is_not(None)))); db.commit()
    assert recover()['candidates'] == 0
    assert not any(r['price'] for r in client.get(f'/api/computers/{cid}').json()['releases'])


@pytest.mark.parametrize('status', ['Prezzo della famiglia/variante diversa', 'Prezzo solo indicativo', 'Prezzo base senza accessorio',
    'Prezzo di lancio stimato', 'Prezzo di lancio verificato ma della famiglia', 'Indizio da verificare'])
def test_estimates_partial_values_and_different_variants_remain_context_only(client, status):
    cid = target(); legacy_import(client, [enterprise_entry(**{'Stato ricerca': status})])
    assert recover()['candidates'] == 0
    assert not any(r['price'] is not None for r in client.get(f'/api/computers/{cid}').json()['releases'])


def test_new_imports_accept_status_without_recovery_and_startup_repairs_legacy_records(client):
    cid = target(); old = legacy_import(client)
    assert not any(r['price'] is not None for r in client.get(f'/api/computers/{cid}').json()['releases'])
    from fastapi.testclient import TestClient
    with TestClient(main.app) as restarted:
        assert next(r for r in restarted.get(f'/api/computers/{cid}').json()['releases'] if r['price'])['price'] == 249
    fresh = upload(client, workbook([enterprise_entry()]))
    assert fresh['price_workbook_report']['price_records'] == 1
    apply(client, fresh)
    assert len(client.get(f'/api/computers/{cid}').json()['facts']) == 1
    assert len([r for r in client.get(f'/api/computers/{cid}').json()['releases'] if r['price']]) == 1


@pytest.mark.parametrize('changes', [{'Prezzo al lancio': '1,234'}, {'Prezzo al lancio': 'NaN'}, {'Prezzo al lancio': '-249'},
    {'Prezzo al lancio': '0'}, {'Valuta': ''}, {'Valuta': 'gbp'}, {'Mercato / Paese': ''}])
def test_invalid_legacy_cells_do_not_become_prices_or_block_startup(client, changes):
    cid = target(); legacy_import(client, [enterprise_entry(**changes)])
    assert recover()['candidates'] == 0
    assert not any(r['price'] is not None for r in client.get(f'/api/computers/{cid}').json()['releases'])


def test_recovery_of_canonical_context_only_json_is_immediate_and_reviewable(client):
    cid = target()
    with patch('app.importing.prices.price_kind', lambda status: PRICED.get(status)):
        records, _ = workbook_records(workbook([enterprise_entry()]))
    from test_imports import upload as upload_json
    job = upload_json(client, records, provider='historical_prices').json()
    assert not job['data_coverage']['prices']
    apply(client, job)
    assert next(r for r in client.get(f'/api/computers/{cid}').json()['releases'] if r['price'])['price'] == 249
    reports = client.get('/api/admin/imports/price-context-recovery').json()
    assert len(reports) == 1 and reports[0]['existing_only']
    assert reports[0]['counts'] == {'updated': 1} and reports[0]['verification_counts']['pending']


def test_concurrent_recovery_passes_create_only_one_price_and_audit_job(client):
    cid = target(); legacy_import(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(lambda _: recover(), range(2)))
    assert sorted(r['candidates'] for r in reports) == [0, 1]
    assert len([r for r in client.get(f'/api/computers/{cid}').json()['releases'] if r['price'] is not None]) == 1
    assert len(client.get('/api/admin/imports/price-context-recovery').json()) == 1


def test_archive_reset_does_not_restore_prices_or_show_recovery_as_current(client):
    target(); legacy_import(client); recover()
    from app.archive import fingerprint, reset_catalog, ResetRequest
    with SessionLocal() as db:
        token = fingerprint(db); db.rollback()
        reset_catalog(db, ResetRequest(token=token, confirmation='SVUOTA ARCHIVIO', backup_confirmed=True, note='Synthetic reset after price recovery.'))
    assert recover()['candidates'] == 0
    assert client.get('/api/computers').json()['total'] == 0
    assert client.get('/api/admin/imports/price-context-recovery').json() == []
