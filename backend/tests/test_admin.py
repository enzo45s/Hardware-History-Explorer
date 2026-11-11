import pytest
from sqlalchemy import text

from app.main import SessionLocal
from app.models import Fact, Review, Sale


def source(client, title='Manuale di riferimento'):
    r = client.post('/api/sources', json={'title': title, 'author': 'Ada', 'publisher': 'Archivio',
        'url': 'https://example.org/manual', 'source_type': 'manual', 'publication_date': '1982-01-01', 'access_date': '2026-11-11'})
    assert r.status_code == 201, r.text
    return r.json()


def payload(client):
    meta = client.get('/api/meta').json()
    citation = source(client)
    return {
        'model_name': 'Nuovo calcolatore', 'manufacturer_id': meta['manufacturers'][0]['id'],
        'description': 'Una scheda inserita a mano', 'announcement_date': '1981-09',
        'category_ids': [meta['categories'][0]['id']], 'source_ids': [citation['id']],
        'releases': [{'market_id': meta['markets'][0]['id'], 'release_date': '1982',
                      'price': 0, 'currency': 'USD', 'source_ids': [citation['id']]}],
        'configurations': [{'variant_name': 'Base', 'specifications': [
            {'component_type': 'RAM', 'property_name': 'Capacità', 'numeric_value': 0, 'unit': 'KB', 'source_ids': [citation['id']]},
            {'component_type': 'CPU', 'property_name': 'Modello', 'text_value': 'MOS 6502'}
        ]}]
    }


def editable(client, computer_id):
    data = client.get(f'/api/admin/computers/{computer_id}').json()
    data.pop('id')
    return data


def test_create_edit_computer_is_visible_in_catalog_filters_and_analysis(client):
    data = payload(client)
    created = client.post('/api/computers', json=data)
    assert created.status_code == 201, created.text
    cid = created.json()['id']
    public = client.get(f'/api/computers/{cid}').json()
    assert public['model_name'] == data['model_name']
    assert public['year'] == 1982 and public['announcement_date'] == '1981-09'
    assert public['sources'][0]['author'] == 'Ada'
    assert public['configurations'][0]['specifications'][0]['numeric_value'] == 0
    assert client.get('/api/analytics').json()['total'] == 11
    assert client.get('/api/computers?q=Nuovo&year_from=1982&year_to=1982').json()['total'] == 1
    update = editable(client, cid)
    release_id = update['releases'][0]['id']
    spec_id = update['configurations'][0]['specifications'][0]['id']
    update['model_name'] = 'Nome aggiornato'
    update['releases'][0]['release_date'] = '1982-04-17'
    update['configurations'][0]['specifications'][0]['numeric_value'] = 64
    r = client.put(f'/api/computers/{cid}', json=update)
    assert r.status_code == 200, r.text
    assert r.json()['releases'][0]['id'] == release_id
    assert r.json()['configurations'][0]['specifications'][0]['id'] == spec_id
    public = client.get(f'/api/computers/{cid}').json()
    assert public['model_name'] == 'Nome aggiornato'
    assert public['first_release'] == '1982-04-17'
    assert client.get('/api/computers?q=aggiornato').json()['total'] == 1


def test_edit_preserves_photographs_and_other_archival_data(client):
    image = client.post('/api/computers/1/images', json={'image_url': 'https://example.org/original.jpg'}).json()
    with SessionLocal() as db:
        db.add_all([Fact(computer_id=1, fact_type='note', statement='Preservare'),
                    Review(computer_id=1, publication='Archivio', score=4, max_score=5),
                    Sale(computer_id=1, market_id=1, units_sold=123)])
        db.commit()
    before = client.get('/api/computers/1').json()
    data = editable(client, 1)
    data['description'] = 'Descrizione rivista'
    assert client.put('/api/computers/1', json=data).status_code == 200
    after = client.get('/api/computers/1').json()
    assert after['images'][0]['id'] == image['id']
    for key in ('facts', 'reviews', 'sales', 'configurations', 'releases'):
        assert after[key] == before[key]


def test_update_source_preserves_links_and_evidence(client):
    data = payload(client)
    created = client.post('/api/computers', json=data).json()
    sid = data['source_ids'][0]
    with SessionLocal() as db:
        db.execute(text("UPDATE computer_sources SET evidence='pagina 12', verification_status='verified' WHERE source_id=:id"), {'id': sid})
        db.commit()
    citation = client.get(f'/api/sources/{sid}').json()
    citation.pop('id')
    citation['title'] = 'Manuale aggiornato'
    assert client.put(f'/api/sources/{sid}', json=citation).status_code == 200
    roundtrip = editable(client, created['id'])
    assert client.put(f"/api/computers/{created['id']}", json=roundtrip).status_code == 200
    public = client.get(f"/api/computers/{created['id']}").json()
    assert public['sources'][0]['title'] == 'Manuale aggiornato'
    assert public['configurations'][0]['specifications'][0]['sources'][0]['title'] == 'Manuale aggiornato'
    with SessionLocal() as db:
        assert db.execute(text('SELECT evidence, verification_status FROM computer_sources WHERE source_id=:id'), {'id': sid}).one() == ('pagina 12', 'verified')


@pytest.mark.parametrize('change', [
    {'model_name': '   '}, {'manufacturer_id': 99999}, {'category_ids': [99999]}, {'source_ids': [99999]},
    {'announcement_date': '1982-02-30'}, {'announcement_date': '0'},
    {'releases': [{'market_id': 99999, 'release_date': '1982'}]},
    {'configurations': [{'variant_name': 'Base', 'specifications': [{'component_type': 'RAM', 'property_name': 'KB', 'numeric_value': 4, 'text_value': 'quattro'}]}]},
])
def test_invalid_input_does_not_partially_update(client, change):
    before = client.get('/api/computers/1').json()
    update = editable(client, 1)
    update.update(change)
    r = client.put('/api/computers/1', json=update)
    assert r.status_code == 422, r.text
    assert client.get('/api/computers/1').json() == before


def test_foreign_child_ids_cannot_move_records_between_computers(client):
    first = editable(client, 1)
    other = editable(client, 2)
    first['configurations'] = other['configurations']
    assert client.put('/api/computers/1', json=first).status_code == 422
    first = editable(client, 1)
    first['configurations'][0]['specifications'] = other['configurations'][0]['specifications']
    assert client.put('/api/computers/1', json=first).status_code == 422
    first = editable(client, 1)
    first['releases'] = other['releases']
    assert client.put('/api/computers/1', json=first).status_code == 422


def test_configuration_rename_swap_and_explicit_removal(client):
    data = payload(client)
    data['configurations'].append({'variant_name': 'Espansa', 'specifications': []})
    created = client.post('/api/computers', json=data).json()
    cid = created['id']
    update = editable(client, cid)
    update['configurations'][0]['variant_name'], update['configurations'][1]['variant_name'] = 'Espansa', 'Base'
    r = client.put(f'/api/computers/{cid}', json=update)
    assert r.status_code == 200, r.text
    update = editable(client, cid)
    update['configurations'] = [update['configurations'][1]]
    update['releases'] = []
    assert client.put(f'/api/computers/{cid}', json=update).status_code == 200
    result = client.get(f'/api/computers/{cid}').json()
    assert result['releases'] == []
    assert len(result['configurations']) == 1
    assert result['sources']


def test_references_sources_missing_rows_and_openapi(client):
    for route in ('manufacturers', 'categories', 'markets'):
        r = client.post('/api/' + route, json={'name': 'Nuovo riferimento'})
        assert r.status_code == 201
        assert client.post('/api/' + route, json={'name': 'Nuovo riferimento'}).status_code == 409
    assert client.get('/api/sources/99999').status_code == 404
    assert client.get('/api/admin/computers/99999').status_code == 404
    assert client.put('/api/sources/99999', json={'title': 'Missing'}).status_code == 404
    r = client.post('/api/sources', json={'title': '   '})
    assert r.status_code == 422
    schema = client.get('/openapi.json').json()
    assert 'post' in schema['paths']['/api/computers']
    assert 'put' in schema['paths']['/api/sources/{source_id}']


def test_unknown_dates_and_omitted_relationships_are_preserved(client):
    minimal = {'model_name': 'Scheda incompleta', 'manufacturer_id': 1}
    r = client.post('/api/computers', json=minimal)
    assert r.status_code == 201, r.text
    public = client.get(f"/api/computers/{r.json()['id']}").json()
    assert public['year'] is None and public['first_release'] is None
    assert public['releases'] == [] and public['configurations'] == []
    before = client.get('/api/computers/1').json()
    r = client.put('/api/computers/1', json={'model_name': 'Nome rivisto', 'manufacturer_id': before['manufacturer_id']})
    assert r.status_code == 200, r.text
    after = client.get('/api/computers/1').json()
    assert after['model_name'] == 'Nome rivisto'
    for field in ('categories', 'configurations', 'releases', 'sources'):
        assert after[field] == before[field]
