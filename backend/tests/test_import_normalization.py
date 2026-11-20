"""Vocabulary, legacy preservation and human-readable decision regression tests."""
import copy
from datetime import date
import pytest
from app.main import SessionLocal
from app.models import Computer, Specification
from app.importing.normalize import Spec
from app.importing.vocabulary import normalize_spec
from test_imports import record, upload, apply, detail
from app.importing.providers import retroflops_records


@pytest.mark.parametrize('unit,value', [('Hz', 1000000), ('kHz', 1000), ('MHz', 1), ('GHz', .001)])
def test_frequency_units_share_one_canonical_value(unit, value):
    spec = Spec(component_type='main-cpu', property_name='clock-frequency', numeric_value=value, unit=unit)
    assert (spec.component_type, spec.property_name, spec.numeric_value, spec.unit) == ('CPU', 'Frequenza', 1, 'MHz')


def test_memory_kind_is_explicit_and_ambiguous_units_stay_distinct():
    base = {'component_type': 'system-memory', 'property_name': 'memory-capacity', 'numeric_value': 1024, 'unit': 'B'}
    assert normalize_spec({**base, 'component_name': 'Test RAM'}) == {**base, 'component_type': 'RAM', 'component_name': 'Test RAM', 'property_name': 'Capacità', 'numeric_value': 1, 'unit': 'KiB'}
    assert normalize_spec({**base, 'component_name': 'Firmware ROM'})['component_type'] == 'ROM'
    assert normalize_spec({**base, 'component_name': 'RAM and ROM'})['component_type'] == 'Memoria'
    assert normalize_spec({**base, 'component_name': 'Memory'})['component_type'] == 'Memoria'
    for unit in ('KB', 'KiB', 'kb', 'MB'):
        assert normalize_spec({**base, 'component_type': 'RAM', 'unit': unit})['unit'] == unit


def test_model_names_are_not_parsed_as_quantities_and_extreme_values_do_not_overflow():
    spec = Spec(component_type='CPU', property_name='model', text_value='6502 A')
    assert spec.text_value == '6502 A' and spec.numeric_value is None
    for value, unit in [(1e308, 'GHz'), (1e-320, 'Hz')]:
        data = normalize_spec({'component_type': 'CPU', 'property_name': 'Frequenza', 'numeric_value': value, 'unit': unit})
        assert data['numeric_value'] == value and data['unit'] == unit


def test_legacy_labels_and_units_match_without_deleting_or_rewriting_the_specification(client):
    job = upload(client, [record()]).json()['id']; apply(client, job)
    c_id = detail(client, job)['rows'][0]['computer_id']
    with SessionLocal() as db:
        cfg = db.get(Computer, c_id).configurations[0]
        legacy = Specification(component_type='main-cpu', property_name='clock-frequency', numeric_value=1000000, unit='Hz')
        cfg.specifications.append(legacy); db.commit(); spec_id = legacy.id
    updated = record()
    updated['configurations'][0]['specifications'].append({'component_type': 'CPU', 'property_name': 'Frequenza',
        'component_name': 'Synthetic named CPU', 'numeric_value': 1, 'unit': 'MHz'})
    job = upload(client, [updated]).json()['id']; apply(client, job)
    row = detail(client, job)['rows'][0]
    assert not [c for c in row['claims'] if c['status'] == 'conflict']
    with SessionLocal() as db:
        legacy = db.get(Specification, spec_id)
        assert legacy.numeric_value == 1000000 and legacy.unit == 'Hz'
        assert legacy.component_type == 'main-cpu'
        assert len(db.get(Computer, c_id).configurations[0].specifications) == 2
    public = client.get(f'/api/computers/{c_id}').json()
    legacy = next(s for s in public['configurations'][0]['specifications'] if s['id'] == spec_id)
    assert legacy['numeric_value'] == 1000000 and legacy['unit'] == 'Hz'
    assert legacy['normalized']['numeric_value'] == 1 and legacy['normalized']['unit'] == 'MHz'
    claim = next(c for c in row['claims'] if c['target_id'] == spec_id and c['field'] == 'quantity')
    assert claim['display']['proposed'] == '1 MHz' and not claim['display']['stale']
    response = client.post(f"/api/admin/imports/claims/{claim['id']}/review", json={'decision': 'accept', 'note': 'Checked synthetic equal frequency.'})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.get(Specification, spec_id).numeric_value == 1 and db.get(Specification, spec_id).unit == 'MHz'


def test_true_frequency_change_is_conflict(client):
    base = record(configurations=[{'variant_name': 'Base', 'specifications': [{'component_type': 'CPU', 'property_name': 'Frequenza', 'numeric_value': 1, 'unit': 'MHz'}]}])
    job = upload(client, [base]).json()['id']; apply(client, job)
    changed = copy.deepcopy(base); changed['configurations'][0]['specifications'][0].update(numeric_value=2000000, unit='Hz')
    job = upload(client, [changed]).json()['id']; apply(client, job)
    claim = next(c for c in detail(client, job)['rows'][0]['claims'] if c['status'] == 'conflict')
    assert claim['display']['field_label'] == 'CPU · Frequenza'
    assert claim['display']['current'] == '1 MHz' and claim['display']['proposed'] == '2 MHz'


def test_ambiguous_legacy_aliases_do_not_merge_or_partially_update_the_catalog(client):
    job = upload(client, [record()]).json()['id']; apply(client, job)
    c_id = detail(client, job)['rows'][0]['computer_id']
    with SessionLocal() as db:
        computer = db.get(Computer, c_id)
        computer.configurations[0].specifications.extend([
            Specification(component_type='main-cpu', component_name='Synthetic CPU A', property_name='clock-frequency', numeric_value=1000000, unit='Hz'),
            Specification(component_type='CPU', component_name='Synthetic CPU B', property_name='Frequenza', numeric_value=2, unit='MHz')])
        db.commit()
    changed = record(description='This synthetic update must roll back.')
    changed['configurations'][0]['specifications'].append({'component_type': 'CPU', 'property_name': 'frequency', 'numeric_value': 1, 'unit': 'MHz'})
    job = upload(client, [changed]).json()['id']
    assert apply(client, job)['counts'] == {'failed': 1}
    row = detail(client, job)['rows'][0]
    assert 'Specifiche ripetute' in row['error'] and not row['claims']
    with SessionLocal() as db:
        computer = db.get(Computer, c_id)
        assert computer.description is None
        assert len(computer.configurations[0].specifications) == 3


def test_reference_conflicts_show_names_and_dates_keep_precision(client):
    job = upload(client, [record(announcement_date='1980')]).json()['id']; apply(client, job)
    c_id = detail(client, job)['rows'][0]['computer_id']
    changed = record(manufacturer='Synthetic Manufacturer Alternative', announcement_date='1981')
    job = upload(client, [changed]).json()['id']; row = detail(client, job)['rows'][0]
    client.post(f"/api/admin/imports/{job}/rows/{row['id']}/match", json={'computer_id': c_id})
    apply(client, job)
    claims = detail(client, job)['rows'][0]['claims']
    manufacturer = next(c for c in claims if c['field'] == 'manufacturer_id')
    assert manufacturer['display']['field_label'] == 'Produttore'
    assert manufacturer['display']['current'] == 'ETL Test Manufacturer'
    assert manufacturer['display']['proposed'] == 'Synthetic Manufacturer Alternative'
    assert manufacturer['display']['context'] == 'Synthetic Test System'
    announced = next(c for c in claims if c['field'] == 'announcement_date')
    assert announced['display']['current'] == '1980' and announced['display']['proposed'] == '1981'
    with SessionLocal() as db:
        db.get(Computer, c_id).announcement_date = date(1982, 1, 1); db.commit()
    announced = next(c for c in detail(client, job)['rows'][0]['claims'] if c['field'] == 'announcement_date')
    assert announced['display']['stale']


def test_retroflops_rumors_are_not_transformed_into_estimated_measurements():
    payload = {'schemaVersion': 'catalog-v1', 'systems': [{'id': 'test', 'name': 'Test', 'manufacturer': 'Test Maker',
        'type': 'home-computer', 'configurations': [{'id': 'base', 'entries': [{'componentId': 'cpu', 'role': 'main-cpu', 'measurementIds': ['clock']}]}]}],
        'components': [{'id': 'cpu', 'kind': 'cpu', 'name': 'Synthetic CPU'}],
        'measurements': [{'id': 'clock', 'metric': 'clock-frequency', 'evidenceLevel': 'rumored', 'quantity': {'state': 'value', 'value': '1', 'unit': 'MHz'}}]}
    specs = retroflops_records(payload)[0]['configurations'][0]['specifications']
    assert len(specs) == 1 and specs[0]['property_name'] == 'Modello'


def test_distinct_core_clocks_keep_their_scope_and_announcement_is_not_release(client):
    payload = {'schemaVersion': 'catalog-v1', 'systems': [{'id': 'test', 'name': 'Test', 'manufacturer': 'Test Maker',
        'type': 'personal-computer', 'releaseDate': '2020-11', 'notes': 'The release date is the date of the cited announcement.',
        'configurations': [{'id': 'base', 'entries': [{'componentId': 'cpu', 'role': 'main-cpu', 'measurementIds': ['fast', 'slow']}]}]}],
        'components': [{'id': 'cpu', 'kind': 'cpu', 'name': 'Synthetic mixed-core CPU'}],
        'measurements': [{'id': 'fast', 'metric': 'clock-frequency', 'subject': {'part': 'performance-cores'}, 'evidenceLevel': 'confirmed', 'quantity': {'state': 'value', 'value': '3.2', 'unit': 'GHz'}},
                         {'id': 'slow', 'metric': 'clock-frequency', 'subject': {'part': 'efficiency-cores'}, 'evidenceLevel': 'confirmed', 'quantity': {'state': 'value', 'value': '2064', 'unit': 'MHz'}}]}
    row = retroflops_records(payload)[0]
    assert row['announcement_date'] == '2020-11' and 'releases' not in row
    job = upload(client, [row]).json()['id']; apply(client, job)
    result = detail(client, job)['rows'][0]
    assert not [c for c in result['claims'] if c['status'] == 'conflict']
    c = client.get(f"/api/computers/{result['computer_id']}").json()
    values = {s['property_name']: s['numeric_value'] for s in c['configurations'][0]['specifications']}
    assert values['Frequenza (core prestazioni)'] == 3200
    assert values['Frequenza (core efficienza)'] == 2064
    assert c['announcement_date'] == '2020-11' and c['year'] is None
