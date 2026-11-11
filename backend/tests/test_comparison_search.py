import pytest
from sqlalchemy import event

from app.main import SessionLocal, engine
from app.models import Computer


def test_suggestions_match_model_and_manufacturer_and_keep_year(client):
    r = client.get('/api/computers/suggestions?q=apple')
    assert r.status_code == 200, r.text
    assert {row['model_name'] for row in r.json()['items']} == {'Apple II', 'Macintosh 128K'}
    assert all(row['manufacturer'] == 'Apple' for row in r.json()['items'])
    assert {row['year'] for row in r.json()['items']} == {1977, 1984}
    assert client.get('/api/computers/suggestions?q=altair').json()['items'][0]['model_name'] == 'Altair 8800'
    assert client.get('/api/computers/suggestions?q=  ').json() == {'items': [], 'has_more': False}


def test_limit_exclusion_and_search_after_first_catalog_page(client):
    with SessionLocal() as db:
        db.add_all(Computer(manufacturer_id=1, model_name=f'Large archive {i:03}') for i in range(125))
        db.commit()
    r = client.get('/api/computers/suggestions?q=Large archive').json()
    assert len(r['items']) == 8 and r['has_more'] is True
    removed = r['items'][0]['id']
    filtered = client.get('/api/computers/suggestions', params={'q': 'Large archive', 'exclude_ids': removed}).json()
    assert len(filtered['items']) == 8 and removed not in [c['id'] for c in filtered['items']]
    last = client.get('/api/computers/suggestions?q=Large archive 124').json()
    assert len(last['items']) == 1 and last['items'][0]['model_name'] == 'Large archive 124'
    assert last['items'][0]['year'] is None
    assert last['has_more'] is False
    assert set(last['items'][0]) == {'id', 'model_name', 'manufacturer', 'year'}


def test_wildcards_are_literal_and_model_prefixes_rank_first(client):
    with SessionLocal() as db:
        db.add_all(Computer(manufacturer_id=1, model_name=name) for name in ['ZZ Demo', 'A ZZ Edition', 'Literal % Model', 'Literal _ Model'])
        db.commit()
    rows = client.get('/api/computers/suggestions?q=ZZ').json()['items']
    assert [c['model_name'] for c in rows] == ['ZZ Demo', 'A ZZ Edition']
    assert len(client.get('/api/computers/suggestions', params={'q': '%'}).json()['items']) == 1
    assert len(client.get('/api/computers/suggestions', params={'q': '_'}).json()['items']) == 1
    assert client.get('/api/computers/suggestions?q=zzzzzz').json() == {'items': [], 'has_more': False}


@pytest.mark.parametrize('query', ['q=', 'q=x&limit=0', 'q=x&limit=11', 'q=x&exclude_ids=-1', 'q=x&exclude_ids=abc', 'q=x&exclude_ids=1&exclude_ids=2&exclude_ids=3&exclude_ids=4&exclude_ids=5&exclude_ids=6'])
def test_invalid_suggestion_parameters(client, query):
    assert client.get('/api/computers/suggestions?' + query).status_code == 422


def test_suggestions_do_not_load_the_archival_graph(client):
    statements = []
    def track(conn, cursor, statement, parameters, context, many): statements.append(statement)
    event.listen(engine, 'before_cursor_execute', track)
    try:
        assert client.get('/api/computers/suggestions?q=IBM').status_code == 200
    finally:
        event.remove(engine, 'before_cursor_execute', track)
    assert len(statements) == 1
