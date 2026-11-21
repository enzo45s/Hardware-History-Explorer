import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.main import SessionLocal
from app.models import Computer, Manufacturer, Configuration, Specification
from app.import_models import ImportClaim, ImportRow
from app.importing.normalize import Record
from app.ram_research import documented_ram, validate_enrichment, coverage

PACKAGE = Path(__file__).resolve().parents[2] / 'docs/datasets/ram-2026-11/ram-mancante.json'


@pytest.mark.parametrize('component,prop,number,text,unit,expected', [
    ('RAM', 'Capacità', 64, None, 'KiB', True),
    ('RAM', 'Capacità riportata', 64, None, 'Kb', True),
    ('RAM', 'Capacità riportata', None, '16 - 64 KB', None, True),
    ('RAM', 'Capacità riportata', None, '4096 parole da 18 bit', None, True),
    ('RAM', 'Dotazioni riportate', None, '1M/4M', None, False),
    ('RAM', 'Capacità', None, '64 KB ROM', None, False),
    ('RAM', 'Capacità', None, '128 KB VRAM', None, False),
    ('ROM', 'Capacità', 64, None, 'KB', False),
    ('CPU', 'Frequenza', 64, None, 'MHz', False),
    ('RAM', 'Slot', 4, None, None, False),
    ('RAM', 'Capacità', 0, None, 'KB', False),
    ('RAM', 'Capacità', float('inf'), None, 'KB', False),
])
def test_ram_coverage_requires_a_capacity_not_a_clock_rom_or_slot_count(component, prop, number, text, unit, expected):
    assert documented_ram(dict(component_type=component, property_name=prop, numeric_value=number,
                               text_value=text, unit=unit)) is expected


def upload(client, payload):
    result = client.post('/api/admin/imports/upload', files={
        'file': ('ram.json', json.dumps(payload, ensure_ascii=False).encode(), 'application/json')},
        data={'provider': 'manual', 'rights_confirmed': 'true'})
    assert result.status_code == 201, result.text
    assert result.json()['existing_only'] and result.json()['missing_ram_only']
    return result.json()['id']


def apply(client, job):
    response = client.post(f'/api/admin/imports/{job}/apply')
    assert response.status_code == 200, response.text
    return response.json()


def test_package_is_sourced_ram_only_and_keeps_unit_and_scope_distinctions():
    data = json.loads(PACKAGE.read_text())
    assert data['_metadata']['import_mode'] == 'existing_only'
    assert data['_metadata']['enrichment_mode'] == 'missing_ram_only'
    assert len(data['records']) >= 140
    assert len({(r['manufacturer'], r['model_name']) for r in data['records']}) == len(data['records'])
    for original in data['records']:
        row = Record.model_validate(original).model_dump(mode='json', exclude_none=True)
        validate_enrichment(row)
        for cfg in row['configurations']:
            for s in cfg['specifications']:
                assert s['source']['url'].startswith('https://') and s['evidence']
                assert not s['estimated']
    assert not any(r['model_name'] in ('Programma 101', 'Elea 9003') for r in data['records'])
    rows = {r['model_name']: r for r in data['records']}
    pdp = rows['PDP-1']['configurations'][0]['specifications'][0]
    assert 'parole da 18 bit' in pdp['text_value']
    assert rows['IRIS Indigo R4000']['configurations'][0]['specifications'][0]['property_name'] == 'Capacità massima riportata'


def test_real_package_fills_existing_records_without_mutating_text_prices_photos_or_verified_status(client):
    payload = json.loads(PACKAGE.read_text())
    absent = payload['records'][-1]
    with SessionLocal() as db:
        makers = {}
        for row in payload['records'][:-1]:
            if row['manufacturer'] not in makers:
                makers[row['manufacturer']] = db.scalar(select(Manufacturer).where(Manufacturer.name == row['manufacturer'])) or Manufacturer(name=row['manufacturer'])
            maker = makers[row['manufacturer']]
            db.add(Computer(manufacturer=maker, model_name=row['model_name'], description='Testo curato.'))
        db.commit()
    before = client.get('/api/computers').json()['total']
    with SessionLocal() as db:
        lisa = db.scalar(select(Computer).where(Computer.model_name == 'Lisa'))
        lisa_id = lisa.id
    assert client.post(f'/api/computers/{lisa_id}/images', json={'image_url':'https://example.org/lisa.jpg'}).status_code == 201
    images = client.get(f'/api/computers/{lisa_id}').json()['images']
    result = apply(client, upload(client, payload))
    assert result['counts'] == {'updated': len(payload['records']) - 1, 'skipped': 1}
    assert client.get('/api/computers').json()['total'] == before
    current = client.get(f'/api/computers/{lisa_id}').json()
    assert current['description'] == 'Testo curato.' and current['images'] == images and current['releases'] == []
    with SessionLocal() as db:
        claims = db.scalars(select(ImportClaim).join(ImportRow).where(ImportRow.job_id == result['id'])).all()
        assert claims and all(c.status == 'pending' for c in claims)
        assert all(c.evidence for c in claims if c.entity == 'Specification')
        assert not db.scalar(select(Computer).where(Computer.model_name == absent['model_name']))
    second = apply(client, upload(client, payload))
    assert second['counts'] == {'skipped': len(payload['records'])}


def test_ram_added_between_preview_and_apply_is_preserved_including_ambiguous_units(client):
    data = json.loads(PACKAGE.read_text()); data['records'] = [next(r for r in data['records'] if r['model_name'] == 'Lisa')]
    with SessionLocal() as db:
        c = Computer(manufacturer=db.scalar(select(Manufacturer).where(Manufacturer.name == 'Apple')), model_name='Lisa')
        db.add(c); db.commit(); cid = c.id
    job = upload(client, data)
    with SessionLocal() as db:
        db.add(Configuration(computer_id=cid, variant_name='Configurazione curata', specifications=[
            Specification(component_type='RAM', property_name='Capacità riportata', numeric_value=512, unit='Kb')]))
        db.commit()
    assert apply(client, job)['counts'] == {'skipped': 1}
    with SessionLocal() as db:
        c = db.get(Computer, cid)
        assert len(c.configurations) == 1
        s = c.configurations[0].specifications[0]
        assert (s.numeric_value, s.unit) == (512, 'Kb')
        assert coverage(db)['without_documented_ram'] >= 0


def test_ram_package_cannot_import_other_fields(client):
    data = json.loads(PACKAGE.read_text()); data['records'] = [data['records'][0]]
    data['records'][0]['description'] = 'Non autorizzata dal vincolo RAM.'
    job = upload(client, data)
    assert apply(client, job)['counts'] == {'invalid': 1}
