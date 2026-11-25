"""Exercise the real sourced package on disposable, synthetic catalog records."""
import json
from pathlib import Path

from sqlalchemy import select

from app.main import SessionLocal
from app.models import Computer, Manufacturer, Category, Configuration, Specification
from app.import_models import ImportClaim, ImportRow
from app.importing.normalize import Record

PACKAGE = Path(__file__).resolve().parents[2] / 'docs/datasets/olivetti-2026-11/olivetti-specifiche.json'


def test_olivetti_package_is_sourced_and_stays_within_the_operator_catalog():
    payload = json.loads(PACKAGE.read_text())
    targets = {line.split(' · ', 1)[1] for line in PACKAGE.with_name('modelli.txt').read_text().splitlines()}
    assert len(targets) == 81
    assert payload['_metadata']['import_mode'] == 'existing_only'
    records = [Record.model_validate(row) for row in payload['records']]
    assert len(records) == 62
    assert {r.model_name for r in records} <= targets
    assert sum(len(c.specifications) for r in records for c in r.configurations) == 513
    for row in records:
        assert row.manufacturer == 'Olivetti'
        assert not any((row.releases, row.sales, row.facts, row.categories, row.description, row.announcement_date))
        for cfg in row.configurations:
            keys = [(s.component_type, s.component_name, s.property_name) for s in cfg.specifications]
            assert len(keys) == len(set(keys)), row.model_name
            assert all(s.source and s.source.url and s.evidence and not s.estimated for s in cfg.specifications)
    p101 = next(r for r in records if r.model_name == 'Programma 101')
    assert not any(s.component_type == 'RAM' for c in p101.configurations for s in c.specifications)
    elea = next(r for r in records if r.model_name == 'Elea 9003')
    assert not any(s.component_type == 'RAM' for c in elea.configurations for s in c.specifications)
    assert any('160.000' in (s.text_value or '') for c in elea.configurations for s in c.specifications)
    lsx = next(r for r in records if r.model_name == 'LSX 5000')
    assert {c.variant_name for c in lsx.configurations} == {'LSX 5025E', 'LSX 5040E', 'LSX 5050'}


def test_actual_package_enriches_existing_models_without_resurrecting_deleted_ones(client):
    data = json.loads(PACKAGE.read_text())
    absent = 'M15 Plus'
    identifiers = {}
    with SessionLocal() as db:
        maker = Manufacturer(name='Olivetti')
        category = Category(name='Classificazione già curata')
        db.add_all([maker, category]); db.flush()
        for row in data['records']:
            if row['model_name'] == absent:
                continue
            c = Computer(manufacturer=maker, model_name=row['model_name'], description='Introduzione curata dall’operatore.', categories=[category])
            db.add(c); db.flush(); identifiers[c.model_name] = c.id
        untouched = Computer(manufacturer=maker, model_name='Philos 20', description='Scheda senza nuovi dati documentati.', categories=[category])
        db.add(untouched); db.commit()
        untouched_id = untouched.id
    photo = client.post(f"/api/computers/{identifiers['M24']}/images", json={'image_url':'https://example.org/existing-olivetti-photo.jpg'})
    assert photo.status_code == 201
    before_total = client.get('/api/computers').json()['total']
    before_photo = client.get(f"/api/computers/{identifiers['M24']}").json()['images']
    def run():
        uploaded = client.post('/api/admin/imports/upload', files={'file': (PACKAGE.name, PACKAGE.read_bytes(), 'application/json')},
                               data={'provider':'manual', 'rights_confirmed':'true'})
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()['existing_only'] is True
        job = uploaded.json()['id']
        applied = client.post(f'/api/admin/imports/{job}/apply')
        assert applied.status_code == 200, applied.text
        assert applied.json()['status'] == 'completed', applied.text
        return applied.json(), client.get(f'/api/admin/imports/{job}').json()
    first, detail = run()
    assert first['counts'] == {'updated':61, 'skipped':1}
    assert client.get('/api/computers').json()['total'] == before_total
    assert client.get(f'/api/computers/{untouched_id}').json()['configurations'] == []
    assert all(row['computer_id'] == identifiers.get(row['normalized']['model_name']) for row in detail['rows'])
    m24 = client.get(f"/api/computers/{identifiers['M24']}").json()
    assert m24['description'] == 'Introduzione curata dall’operatore.'
    assert m24['categories'] == ['Classificazione già curata']
    assert m24['images'] == before_photo and m24['releases'] == []
    m44 = client.get(f"/api/computers/{identifiers['Olivetti L1 M44']}").json()
    assert any(s['property_name'] == 'Frequenza' and s['numeric_value'] == 8 and s['sources']
               for c in m44['configurations'] for s in c['specifications'])
    with SessionLocal() as db:
        claims = db.scalars(select(ImportClaim).join(ImportRow).where(ImportRow.job_id == first['id'])).all()
        assert claims and all(c.status == 'pending' for c in claims)
    second, _ = run()
    assert second['counts'] == {'unchanged':61, 'skipped':1}
    assert client.get('/api/computers').json()['total'] == before_total


def test_package_conflicts_require_review_instead_of_overwriting_existing_hardware(client):
    payload = json.loads(PACKAGE.read_text())
    payload['records'] = [row for row in payload['records'] if row['model_name'] == 'Olivetti L1 M44']
    with SessionLocal() as db:
        computer = Computer(manufacturer=Manufacturer(name='Olivetti'), model_name='Olivetti L1 M44',
                            configurations=[Configuration(variant_name='Scheda tecnica', specifications=[
                                Specification(component_type='CPU', property_name='Frequenza', numeric_value=4, unit='MHz')])])
        db.add(computer); db.commit(); c_id = computer.id
    response = client.post('/api/admin/imports/upload', files={'file': ('olivetti.json', json.dumps(payload), 'application/json')},
                           data={'rights_confirmed':'true'})
    assert response.status_code == 201, response.text
    job = response.json()['id']
    applied = client.post(f'/api/admin/imports/{job}/apply')
    assert applied.status_code == 200, applied.text
    detail = client.get(f'/api/admin/imports/{job}').json()
    conflicts = [claim for row in detail['rows'] for claim in row['claims'] if claim['status'] == 'conflict']
    assert len(conflicts) == 1
    assert conflicts[0]['value']['numeric_value'] == 8
    assert conflicts[0]['previous']['numeric_value'] == 4
    current = client.get(f'/api/computers/{c_id}').json()
    assert next(s for c in current['configurations'] for s in c['specifications'] if s['property_name'] == 'Frequenza')['numeric_value'] == 4
