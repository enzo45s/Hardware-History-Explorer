"""Commercialization summaries combine evidence without altering the archive."""
from copy import deepcopy
from datetime import date
from itertools import permutations

import pytest
from sqlalchemy import select

from app.main import SessionLocal
from app.models import Computer, Market, Release, Source
from app.release_display import release_summaries


UNKNOWN = 'Non specificato dalla fonte'


def row(identifier, market=UNKNOWN, year=None, price=None, currency=None, price_type=None, end=None):
    return {'id': identifier, 'market': market, 'release_date': year, 'discontinuation_date': end,
            'price': price, 'currency': currency, 'price_type': price_type,
            'sources': [{'id': identifier, 'title': f'Synthetic citation {identifier}', 'url': f'https://example.org/{identifier}'}]}


def test_requested_example_preserves_originals_and_field_provenance():
    original = [row(1, year='1982', price_type='launch'),
                row(2, market='Stati Uniti', price=3298, currency='USD', price_type='prezzo riportato')]
    before = deepcopy(original)
    summary, = release_summaries(original)
    assert original == before
    assert (summary['market'], summary['release_date'], summary['price'], summary['currency']) == ('Stati Uniti', '1982', 3298, 'USD')
    assert summary['original_releases'] == original and summary['merged']
    assert summary['date_scope'] == 'model'
    assert summary['field_sources'] == {'market': [2], 'release_date': [1], 'discontinuation_date': [],
                                       'price': [2], 'currency': [2], 'price_type': [2]}
    assert [s['id'] for s in summary['sources']] == [1, 2]


def test_same_documented_market_has_regional_date_scope_and_zero_price():
    summary, = release_summaries([row(1, 'Stati Uniti', year='1982'), row(2, 'Stati Uniti', price=0, currency='USD')])
    assert summary['date_scope'] == 'market' and summary['price'] == 0


@pytest.mark.parametrize('entries', [
    [row(1, year='1982'), row(2, 'Stati Uniti', year='1983', price=3298, currency='USD')],
    [row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD'), row(3, 'Giappone', price=200000, currency='JPY')],
    [row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD'), row(3, 'Stati Uniti', price=3998, currency='USD')],
    # Equal amounts can describe different configurations; they are not duplicates.
    [row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD'), row(3, 'Stati Uniti', price=3298, currency='USD')],
    [row(1, 'Stati Uniti', year='1982'), row(2, price=3298, currency='USD')],
    [row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD', price_type='listino successivo')],
    [row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD', end='1981')],
    [row(1, year='1982'), row(2, 'Stati Uniti', year='1982-05', price=3298, currency='USD')],
    [row(1, year='1982', currency='EUR'), row(2, 'Stati Uniti', price=3298, currency='USD')],
    [row(1, 'Globale', year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD')],
])
def test_ambiguous_or_conflicting_releases_remain_distinct(entries):
    result = release_summaries(entries)
    assert len(result) == len(entries) and not any(item['merged'] for item in result)
    assert sorted(identifier for item in result for identifier in item['release_ids']) == [row['id'] for row in entries]


def test_disagreeing_date_sources_do_not_choose_a_year_by_input_order():
    rows = [row(1, year='1982'), row(2, 'Stati Uniti', year='1983'), row(3, 'Stati Uniti', price=3298, currency='USD')]
    expected = release_summaries(rows)
    assert len(expected) == 3
    for ordering in permutations(rows):
        assert release_summaries(ordering) == expected


def test_consistent_date_sources_merge_with_one_price_independent_of_order():
    rows = [row(1, year='1982'), row(2, 'Stati Uniti', year='1982'), row(3, 'Stati Uniti', price=3298, currency='USD')]
    expected = release_summaries(rows)
    assert len(expected) == 1 and expected[0]['date_scope'] == 'market'
    for ordering in permutations(rows):
        assert release_summaries(ordering) == expected


def test_duplicate_date_only_rows_deduplicate_citations_without_changing_precision():
    rows = [row(1, year='1982'), row(2, 'Non specificato dalla fonte (AppleDB)', year='1982')]
    summary, = release_summaries(rows)
    assert summary['market'] == 'Mercato non documentato' and summary['release_date'] == '1982'
    assert summary['release_ids'] == [1, 2] and [source['id'] for source in summary['sources']] == [1, 2]


def test_no_region_is_inferred_from_currency_and_missing_data_is_retained():
    rows = [row(1, year='1982'), row(2, price=3298, currency='USD'), row(3)]
    summary, missing = release_summaries(rows)
    assert summary['market'] == missing['market'] == 'Mercato non documentato'
    assert summary['release_date'] == '1982' and missing['release_date'] is None
    assert summary['release_ids'] == [1, 2] and missing['release_ids'] == [3]


def test_api_editor_comparison_and_assistant_preserve_undated_original(client):
    with SessionLocal() as db:
        computer = db.get(Computer, 1)
        model_name = computer.model_name
        computer.releases.clear()
        db.flush()
        dated_source = Source(title='Synthetic model date', url='https://example.org/date')
        priced_source = Source(title='Synthetic regional price', url='https://example.org/price')
        computer.releases = [Release(market=Market(name=UNKNOWN), release_date=date(1982, 1, 1),
            release_precision='year', sources=[dated_source]), Release(market=Market(name='Synthetic United States'),
            price=3298, currency='USD', price_type='prezzo riportato', sources=[priced_source])]
        db.commit()
        ids = [release.id for release in computer.releases]
    data = client.get('/api/computers/1').json()
    assert len(data['releases']) == 2 and len(data['display_releases']) == 1
    assert data['releases'][1]['release_date'] is None
    assert data['display_releases'][0]['release_date'] == '1982'
    assert data['display_releases'][0]['release_ids'] == ids
    assert data['year'] == 1982
    compared = client.get('/api/compare?ids=1,2').json()[0]
    assert compared['display_releases'] == data['display_releases']
    editor = client.get('/api/admin/computers/1').json()
    assert len(editor['releases']) == 2 and editor['releases'][1]['release_date'] is None
    from app.assistant_context import retrieve
    from app.main import EAGER, full
    with SessionLocal() as db:
        context = retrieve(db, model_name, EAGER, full)
        model = next(row for row in context['computers'] if row['id'] == 1)
        assert len(model['releases']) == 2 and model['releases'][1]['release_date'] is None
        saved = db.scalars(select(Release).where(Release.computer_id == 1).order_by(Release.id)).all()
        assert [release.id for release in saved] == ids and saved[1].release_date is None
