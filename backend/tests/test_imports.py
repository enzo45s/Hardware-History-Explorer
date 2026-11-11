"""Synthetic fixtures test mechanics; they are never published as historical facts."""
import copy
import hashlib
import json
import pytest
from sqlalchemy import select, func
from app.main import SessionLocal, engine, EAGER, full
from app.models import Computer, Specification, Manufacturer, ComputerImage
from app.import_models import ImportJob, ImportClaim
from app.importing.normalize import Record, name_key, parse_payload
from app.importing.providers import retroflops_records, wikidata_records
from app.assistant_context import retrieve
from migrations.historical_imports import migrate


def record(**changes):
    return {'manufacturer': 'ETL Test Manufacturer', 'model_name': 'Synthetic Test System',
            'external_id': 'synthetic-1', 'source': {'title': 'Synthetic test dataset', 'url': 'https://example.org/etl', 'license': 'Test fixture only'},
            'releases': [{'market': 'Test market', 'release_date': '1981', 'price': 0, 'currency': 'USD'}],
            'configurations': [{'variant_name': 'Test variant', 'specifications': [
                {'component_type': 'RAM', 'property_name': 'Capacity', 'text_value': '4 kbytes'}]}], **changes}


def upload(client, rows, **kwargs):
    return client.post('/api/admin/imports/upload', files={'file': ('fixture.json', json.dumps(rows), 'application/json')},
                       data={'rights_confirmed': 'true', **kwargs})


def apply(client, job):
    response = client.post(f'/api/admin/imports/{job}/apply')
    assert response.status_code == 200, response.text
    return response.json()


def detail(client, job):
    return client.get(f'/api/admin/imports/{job}').json()


def test_preview_does_not_modify_catalog_and_keeps_original(client):
    before = client.get('/api/computers').json()['total']
    raw = ('\ufeff' + json.dumps([record()])).encode()
    job = client.post('/api/admin/imports/upload', files={'file': ('original.json', raw)}, data={'rights_confirmed': 'true'}).json()
    assert job['checksum'] == hashlib.sha256(raw).hexdigest()
    assert client.get('/api/computers').json()['total'] == before
    assert client.get(f"/api/admin/imports/{job['id']}/original").content == raw
    normalized = detail(client, job['id'])['rows'][0]['normalized']
    assert normalized['configurations'][0]['specifications'][0]['numeric_value'] == 4
    assert normalized['configurations'][0]['specifications'][0]['unit'] == 'KB'


def test_import_idempotence_sources_and_integration(client):
    before = client.get('/api/computers').json()['total']
    job = upload(client, [record()]).json()['id']
    assert apply(client, job)['counts'] == {'imported': 1}
    c_id = detail(client, job)['rows'][0]['computer_id']
    c = client.get(f'/api/computers/{c_id}').json()
    assert c['year'] == 1981 and c['releases'][0]['price'] == 0
    assert c['configurations'][0]['specifications'][0]['sources'][0]['url'] == 'https://example.org/etl'
    assert client.get('/api/analytics').json()['total'] == before + 1
    assert client.get('/api/computers/suggestions?q=Synthetic').json()['items'][0]['id'] == c_id
    assert client.get('/api/compare', params={'ids': f'1,{c_id}'}).status_code == 200
    assert apply(client, job)['counts'] == {'imported': 1}
    again = upload(client, [record()]).json()['id']
    assert apply(client, again)['counts'] == {'unchanged': 1}
    assert client.get('/api/computers').json()['total'] == before + 1


def test_conflict_is_not_overwritten_and_human_can_resolve_with_audit(client):
    first = upload(client, [record()]).json()['id']; apply(client, first)
    changed = record(); changed['configurations'][0]['specifications'][0] = {'component_type': 'RAM', 'property_name': 'Capacity', 'numeric_value': 8, 'unit': 'KB', 'estimated': True}
    job = upload(client, [changed]).json()['id']; apply(client, job)
    row = detail(client, job)['rows'][0]
    claim = next(c for c in row['claims'] if c['status'] == 'conflict')
    assert claim['estimated'] and claim['previous']['numeric_value'] == 4
    c_id = row['computer_id']
    assert client.get(f'/api/computers/{c_id}').json()['configurations'][0]['specifications'][0]['numeric_value'] == 4
    response = client.post(f"/api/admin/imports/claims/{claim['id']}/review", json={'decision': 'accept', 'note': 'Synthetic test verification against fixture.'})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'verified'
    assert client.get(f'/api/computers/{c_id}').json()['configurations'][0]['specifications'][0]['numeric_value'] == 8
    assert client.post(f"/api/admin/imports/claims/{claim['id']}/review", json={'decision': 'reject', 'note': 'Already reviewed'}).status_code == 409


def test_missing_values_fill_and_existing_photos_survive(client):
    first = upload(client, [record()]).json()['id']; apply(client, first)
    c_id = detail(client, first)['rows'][0]['computer_id']
    client.post(f'/api/computers/{c_id}/images', json={'image_url': 'https://example.org/test-photo.png'})
    second = upload(client, [record(description='Synthetic description for tests')]).json()['id']
    assert apply(client, second)['counts'] == {'updated': 1}
    assert len(client.get(f'/api/computers/{c_id}').json()['images']) == 1


def test_invalid_row_does_not_rollback_good_rows_and_retry_is_audited(client):
    job = upload(client, [record(), record(model_name='', manufacturer='')]).json()['id']
    assert detail(client, job)['rows'][1]['status'] == 'invalid'
    assert apply(client, job)['status'] == 'partial'
    retry = client.post(f'/api/admin/imports/{job}/retry').json()
    assert retry['retry_of'] == job
    assert apply(client, retry['id'])['counts'] == {'unchanged': 1, 'invalid': 1}


def test_ambiguous_existing_duplicate_needs_mapping(client):
    with SessionLocal() as db:
        m = Manufacturer(name='ETL Test Manufacturer'); db.add(m); db.flush()
        db.add_all([Computer(manufacturer=m, model_name='Synthetic Test System') for _ in range(2)]); db.commit()
    job = upload(client, [record()]).json()['id']
    row = detail(client, job)['rows'][0]
    assert row['status'] == 'ambiguous'
    response = client.post(f"/api/admin/imports/{job}/rows/{row['id']}/match", json={'computer_id': row['candidates'][0]})
    assert response.status_code == 200
    assert apply(client, job)['counts'] == {'updated': 1}


def test_manual_external_ids_are_scoped_by_source(client):
    one = upload(client, [record()]).json()['id']; apply(client, one)
    other = record(model_name='Unrelated Synthetic System', source={'title': 'Other test dataset', 'url': 'https://example.org/other'})
    two = upload(client, [other]).json()['id']
    assert detail(client, two)['rows'][0]['status'] == 'ready'
    assert apply(client, two)['counts'] == {'imported': 1}


def test_upload_limits_authorization_and_unsafe_urls(client):
    assert client.post('/api/admin/imports/upload', files={'file': ('test.json', '[]')}).status_code == 422
    assert upload(client, [record(source={'title': 'Bad', 'url': 'javascript:alert(1)'})]).json()['counts'] == {'invalid': 1}
    assert upload(client, [record(source={'title': 'Bad', 'url': 'https://secret:password@example.org/'})]).json()['counts'] == {'invalid': 1}
    assert upload(client, [record()] * 1001).status_code == 422
    assert client.post('/api/admin/imports/upload', files={'file': ('big.json', b'x' * (8 * 1024 * 1024 + 1))}, data={'rights_confirmed': 'true'}).status_code == 413


def test_csv_and_normalization_preserve_uncertainty_and_distinct_units():
    assert name_key('  ＩＢＭ  PC  ') == name_key('IBM PC')
    _, data = parse_payload(b'manufacturer,model_name,source,categories\nTest,Fixture,"{""title"":""Fixture""}",Home|Personal\n', 'csv')
    assert Record.model_validate(data[0]).categories == ['Home', 'Personal']
    for value in ('NaN', 'Infinity'):
        with pytest.raises(ValueError):
            Record.model_validate(record(configurations=[{'variant_name': 'X', 'specifications': [{'component_type': 'RAM', 'property_name': 'Capacity', 'numeric_value': value}]}]))
    with pytest.raises(ValueError):
        Record.model_validate(record(announcement_date='circa 1980'))
    for unit in ('KB', 'KiB'):
        data = Record.model_validate(record(configurations=[{'variant_name': 'X', 'specifications': [{'component_type': 'RAM', 'property_name': 'Capacity', 'numeric_value': 4, 'unit': unit}]}]))
        assert data.configurations[0].specifications[0].unit == unit


def test_remote_failure_is_persisted_and_retryable(client, monkeypatch):
    def blocked(*args):
        raise RuntimeError('secret proxy connection string')
    monkeypatch.setattr('app.importing.router.fetch_provider', blocked)
    result = client.post('/api/admin/imports/remote', json={'provider': 'wikidata', 'ids': ['Q1']}).json()
    assert result['status'] == 'failed' and 'secret' not in result['error']
    assert client.post(f"/api/admin/imports/{result['id']}/retry").json()['retry_of'] == result['id']
    assert client.post('/api/admin/imports/remote', json={'provider': 'oldcomputers'}).status_code == 422


def test_assistant_can_retrieve_imported_computer_beyond_first_hundred(client):
    with SessionLocal() as db:
        maker = Manufacturer(name='Synthetic batch'); db.add(maker); db.flush()
        db.add_all([Computer(manufacturer=maker, model_name=f'Fixture {i}') for i in range(110)]); db.commit()
    job = upload(client, [record()]).json()['id']; apply(client, job)
    with SessionLocal() as db:
        context = retrieve(db, 'Quale RAM ha Synthetic Test System?', EAGER, full)
        c = next(c for c in context['computers'] if c['model'] == 'Synthetic Test System')
        assert c['sources'] and c['configurations'][0]['specifications'][0]['sources']
        assert c['import_assertions'][0]['status'] == 'pending'


def test_additive_migration_repeatable_and_preserves_catalog(client):
    before = client.get('/api/computers').json()['total']
    migrate(engine); migrate(engine)
    assert client.get('/api/computers').json()['total'] == before


def test_wikidata_adapter_does_not_invent_release_from_inception():
    payload = {'requested_ids': ['Q1'], 'entities': {'Q1': {'labels': {'en': {'value': 'Test'}}, 'claims': {
        'P176': [{'mainsnak': {'datavalue': {'value': {'id': 'Q2'}}}}],
        'P571': [{'mainsnak': {'datavalue': {'value': {'time': '+1980-01-01T00:00:00Z', 'precision': 9}}}}]}},
        'Q2': {'labels': {'en': {'value': 'Test Maker'}}}}}
    result = wikidata_records(payload)[0]
    assert result['manufacturer'] == 'Test Maker' and 'releases' not in result
    assert result['source']['license'] == 'CC0'


def test_retroflops_adapter_keeps_attribution_unknowns_and_variant_measurements():
    payload = {'schemaVersion': 'catalog-v1', 'systems': [{'id': 'test', 'name': 'Test', 'manufacturer': 'Test Maker', 'type': 'home-computer',
        'releaseDate': '1980', 'description': '{{measurement:unresolved}}', 'sourceIds': [],
        'configurations': [{'id': 'test', 'label': 'Test variant', 'entries': [{'componentId': 'ram', 'role': 'system-memory', 'measurementIds': ['capacity', 'unknown']}]}]}],
        'components': [{'id': 'ram', 'name': 'Test RAM'}], 'measurements': [{'id': 'capacity', 'metric': 'capacity', 'quantity': {'state': 'value', 'value': '4', 'unit': 'KiB'}},
        {'id': 'unknown', 'quantity': {'state': 'unknown'}}]}
    result = retroflops_records(payload)[0]
    normalized = Record.model_validate(result)
    assert normalized.configurations[0].specifications[0].numeric_value == 4
    assert len(normalized.configurations[0].specifications) == 1
    assert result['source']['license'].startswith('CC BY 4.0') and 'description' not in result


def test_prices_are_atomic_with_currency_and_review_does_not_use_stale_value(client):
    data = record(releases=[{'market': 'Test market', 'release_date': '1981', 'currency': 'USD'}])
    job = upload(client, [data]).json()['id']; apply(client, job)
    updated = record(releases=[{'market': 'Test market', 'release_date': '1981', 'price': 200, 'currency': 'EUR'}])
    job = upload(client, [updated]).json()['id']; apply(client, job)
    row = detail(client, job)['rows'][0]
    claim = next(c for c in row['claims'] if c['field'] == 'price_bundle')
    assert claim['status'] == 'conflict'
    release = client.get(f"/api/computers/{row['computer_id']}").json()['releases'][0]
    assert release['price'] is None and release['currency'] == 'USD'
    from app.models import Release
    with SessionLocal() as db:
        db.get(Release, claim['target_id']).currency = 'GBP'; db.commit()
    response = client.post(f"/api/admin/imports/claims/{claim['id']}/review", json={'decision': 'accept', 'note': 'Check stale assertion'})
    assert response.status_code == 409


def test_sales_reviews_facts_and_sources_are_imported_without_duplicates(client):
    citation = {'title': 'Synthetic field-level citation', 'url': 'https://example.org/field'}
    data = record(sales=[{'market': 'Test market', 'units_sold': 100, 'estimated': True, 'source': citation}],
                  reviews=[{'publication': 'Test publication', 'score': 4, 'max_score': 5, 'source': citation}],
                  facts=[{'fact_type': 'test', 'statement': 'Synthetic statement used only for testing.', 'source': citation}])
    first = upload(client, [data]).json()['id']; apply(client, first)
    again = upload(client, [data]).json()['id']; assert apply(client, again)['counts'] == {'unchanged': 1}
    row = detail(client, again)['rows'][0]
    c = client.get(f"/api/computers/{row['computer_id']}").json()
    for key in ('sales', 'reviews', 'facts'):
        assert len(c[key]) == 1 and c[key][0]['sources'][0]['url'] == citation['url']
    assert c['sales'][0]['estimated'] is True


def test_failed_row_transaction_preserves_other_rows(client):
    # Duplicate specification identity makes a later incremental import ambiguous.
    data = record(); duplicate = copy.deepcopy(data['configurations'][0]['specifications'][0])
    data['configurations'][0]['specifications'].append(duplicate)
    first = upload(client, [data]).json()['id']; apply(client, first)
    # Repeated equivalent specs are matched conservatively, never deleted.
    with SessionLocal() as db:
        c_id = detail(client, first)['rows'][0]['computer_id']
        cfg = db.get(Computer, c_id).configurations[0]
        cfg.specifications.append(Specification(component_type='RAM', property_name='Capacity', numeric_value=4, unit='KB'))
        db.commit()
    job = upload(client, [record(description='Must roll back on failure'), record(model_name='Other valid fixture', external_id='synthetic-2')]).json()['id']
    result = apply(client, job)
    assert result['counts'] == {'failed': 1, 'imported': 1}
    assert client.get(f'/api/computers/{c_id}').json()['description'] is None


def test_adapted_uploads_also_respect_row_limit(client):
    entities = {f'Q{i}': {} for i in range(1, 1002)}
    result = upload(client, {'entities': entities}, provider='wikidata')
    assert result.status_code == 422


def test_wikidata_preserves_supported_date_precision_and_skips_qualified_dates():
    payload = {'requested_ids': ['Q1'], 'entities': {'Q1': {'labels': {'en': {'value': 'Test'}}, 'claims': {
        'P176': [{'mainsnak': {'datavalue': {'value': {'id': 'Q2'}}}}],
        'P577': [{'mainsnak': {'datavalue': {'value': {'time': '+1980-00-00T00:00:00Z', 'precision': 9, 'calendarmodel': 'http://www.wikidata.org/entity/Q1985727'}}}}]}},
        'Q2': {'labels': {'en': {'value': 'Test Maker'}}}}}
    result = wikidata_records(payload)[0]
    assert result['releases'][0]['release_date'] == '1980'
    payload['entities']['Q1']['claims']['P577'][0]['qualifiers'] = {'P518': []}
    assert 'releases' not in wikidata_records(payload)[0]


def test_partial_date_chronology_and_bits_are_not_reinterpreted():
    with pytest.raises(ValueError):
        Record.model_validate(record(releases=[{'market': 'Test', 'release_date': '1980-12', 'discontinuation_date': '1980-01'}]))
    from app.importing.normalize import unit_name
    assert unit_name('kb') == 'kb' and unit_name('kB') == 'KB' and unit_name('kbytes') == 'KB'


def test_manual_alias_mapping_is_preserved_by_external_identity(client):
    job = upload(client, [record()]).json()['id']; apply(client, job)
    c_id = detail(client, job)['rows'][0]['computer_id']
    alias = record(manufacturer='Another name for the synthetic test maker')
    alias_job = upload(client, [alias]).json()['id']
    row = detail(client, alias_job)['rows'][0]
    assert client.post(f"/api/admin/imports/{alias_job}/rows/{row['id']}/match", json={'computer_id': c_id}).status_code == 200
    apply(client, alias_job)
    retry = client.post(f'/api/admin/imports/{alias_job}/retry').json()['id']
    assert detail(client, retry)['rows'][0]['computer_id'] == c_id
    assert apply(client, retry)['counts'] == {'unchanged': 1}


def test_verification_counts_and_row_pagination(client):
    job = upload(client, [record(model_name=f'Synthetic {i}', external_id=f'test-{i}') for i in range(26)]).json()['id']
    apply(client, job)
    response = detail(client, job)
    assert len(response['rows']) == 25 and response['verification_counts']['pending'] > 0
    assert len(client.get(f'/api/admin/imports/{job}?offset=25').json()['rows']) == 1
