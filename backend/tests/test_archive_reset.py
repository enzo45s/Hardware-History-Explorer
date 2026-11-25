"""Reset is exercised only in the disposable databases supplied by conftest."""
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from app.main import app, SessionLocal, UPLOAD_DIR
from app.models import Computer, Manufacturer, Category, Market, Source, Specification, Configuration, ComputerImage, Release
from app.import_models import ArchiveReset, ImportJob, ImportRow, ImportClaim, ExternalIdentity
from test_imports import record, upload, apply, detail
from test_import_reconciliation import legacy_duplicate, preview as merge_preview, PREFIX as MERGE_PREFIX

PREFIX = '/api/admin/archive'


def decision(client):
    response = client.get(PREFIX + '/preview')
    assert response.status_code == 200, response.text
    return {'token': response.json()['token'], 'confirmation': 'SVUOTA ARCHIVIO',
            'backup_confirmed': True, 'note': 'Reset this isolated synthetic test database.'}


def reset(client):
    response = client.post(PREFIX + '/reset', json=decision(client))
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_and_explicit_confirmation_do_not_change_the_catalog(client):
    data = decision(client)
    for changes in ({'confirmation': 'reset'}, {'backup_confirmed': False}, {'note': ''}):
        assert client.post(PREFIX + '/reset', json={**data, **changes}).status_code == 422
    assert client.get('/api/computers').json()['total'] == 10
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ArchiveReset)) == 0


def test_reset_keeps_files_sources_originals_and_stays_empty_after_restart(client):
    source_id, target_id, _, _, _, job, data = legacy_duplicate(client)
    original = client.get(f'/api/admin/imports/{job}/original').content
    result = reset(client)
    assert result['computers'] == 0 and result['demo_seed_disabled']
    assert result['removed']['computers'] == 11
    assert client.get('/api/computers').json()['total'] == 0
    meta = client.get('/api/meta').json()
    assert meta['manufacturers'] == [] and meta['categories'] == [] and meta['markets'] == []
    assert (UPLOAD_DIR / 'retained.webp').is_file()
    assert client.get(f'/api/admin/imports/{job}/original').content == original
    assert detail(client, job)['status'] == 'archived'
    assert client.post(f'/api/admin/imports/{job}/apply').status_code == 409
    with SessionLocal() as db:
        for model in (Computer, Manufacturer, Category, Market, Specification, Configuration, ComputerImage, Release, ExternalIdentity):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert db.scalar(select(func.count()).select_from(Source)) > 0
        assert all(row.computer_id is None and row.candidates == [] for row in db.scalars(select(ImportRow)))
    snapshot = client.get(PREFIX + f"/resets/{result['reset_id']}/original").json()
    assert len(snapshot['tables']['computers']) == 11
    assert snapshot['tables']['computer_images'][0]['local_filename'] == 'retained.webp'
    with TestClient(app) as restarted:
        assert restarted.get('/api/computers').json()['total'] == 0
        assert restarted.get('/api/analytics').status_code == 200
    # The same file is a fresh import, then idempotent; no seed is reintroduced.
    new_job = upload(client, [data]).json()['id']
    assert apply(client, new_job)['counts'] == {'imported': 1}
    assert client.get('/api/computers').json()['total'] == 1
    assert apply(client, upload(client, [data]).json()['id'])['counts'] == {'unchanged': 1}


def test_stale_preview_is_rejected_even_when_counts_are_identical(client):
    data = decision(client)
    with SessionLocal() as db:
        db.scalar(select(Computer).limit(1)).description = 'A newer synthetic edit'; db.commit()
    response = client.post(PREFIX + '/reset', json=data)
    assert response.status_code == 409 and 'cambiato' in response.json()['detail']
    assert client.get('/api/computers').json()['total'] == 10
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ArchiveReset)) == 0


def test_old_claims_cannot_describe_or_modify_a_new_computer_with_a_reused_id(client):
    job = upload(client, [record(manufacturer='IBM', model_name='IBM System/360', configurations=[])]).json()['id']
    apply(client, job)
    claim = next(c for c in detail(client, job)['rows'][0]['claims'] if c['field'] == 'model_name')
    old_id = claim['target_id']
    reset(client)
    with SessionLocal() as db:
        db.add(Computer(id=old_id, manufacturer=Manufacturer(name='New synthetic manufacturer'), model_name='New synthetic system'))
        db.commit()
    archived = next(c for c in detail(client, job)['rows'][0]['claims'] if c['id'] == claim['id'])
    assert archived['display']['stale'] and archived['display']['current'] == 'Elemento non più disponibile'
    response = client.post(f"/api/admin/imports/claims/{claim['id']}/review", json={'decision': 'accept', 'note': 'A stale claim must not be applied.'})
    assert response.status_code == 409
    assert client.get(f'/api/computers/{old_id}').json()['model_name'] == 'New synthetic system'


def test_old_configuration_reconciliation_is_not_replayed_after_a_clean_reset(client):
    source_id, target_id, _, _, _, _, data = legacy_duplicate(client)
    merge = merge_preview(client, 'computer', source_id, target_id)
    assert client.post(MERGE_PREFIX + '/apply', json={**merge, 'note': 'Merge the synthetic duplicate before resetting.'}).status_code == 200
    reset(client)
    job = upload(client, [data]).json()['id']
    assert apply(client, job)['counts'] == {'imported': 1}
    row = detail(client, job)['rows'][0]
    c = client.get(f"/api/computers/{row['computer_id']}").json()
    assert len(c['configurations']) == 1
    assert c['configurations'][0]['variant_name'] == 'Configurazione rappresentativa'


def test_failure_during_deletion_rolls_back_catalog_history_and_reset_marker(client, monkeypatch):
    import app.archive as archive
    job = upload(client, [record()]).json()['id']; apply(client, job)
    real_delete = archive.delete
    def fail_after_computers(model):
        if model is Manufacturer:
            raise IntegrityError('synthetic failure', {}, Exception('private diagnostic'))
        return real_delete(model)
    monkeypatch.setattr(archive, 'delete', fail_after_computers)
    response = client.post(PREFIX + '/reset', json=decision(client))
    assert response.status_code == 409 and 'private diagnostic' not in response.text
    assert client.get('/api/computers').json()['total'] == 11
    assert detail(client, job)['status'] == 'completed'
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ArchiveReset)) == 0
        assert db.scalar(select(func.count()).select_from(ExternalIdentity)) == 1
