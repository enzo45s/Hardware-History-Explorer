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


def reference(identifier,year,base=False,**extra):
    return {**row(identifier,year=year), 'date_evidence':{'kind':'reference','base':base,'source_ids':[identifier]},**extra}


def test_bbc_base_and_regional_years_do_not_block_the_documented_launch_price():
    original=[reference(1,'1981',True),reference(2,'1982'),reference(3,'1984'),reference(4,'1983'),
        {**row(5,'Regno Unito',price=399,currency='GBP',price_type='prezzo riportato'),
         'documented_launch':{'date':'1981-12','source_id':5,'note':'Lancio nel dicembre 1981; consegne rinviate al 1982.'}}]
    before=deepcopy(original)
    expected,=release_summaries(original)
    assert (expected['market'],expected['release_date'],expected['price'])==('Europa','1981-12',399)
    assert expected['release_ids']==[1,2,3,4,5] and expected['field_sources']['release_date']==[5]
    assert expected['date_scope']=='model' and expected['date_evidence']['kind']=='documented_launch'
    assert expected['original_releases']==before and original==before
    assert all('non documentata' not in n for n in expected.get('commercialization_notes',[]))
    for order in permutations(original):assert release_summaries(order)==[expected]


def test_base_reference_is_used_instead_of_guessing_the_oldest_variant_year():
    result,=release_summaries([reference(1,'1985',True),reference(2,'1982'),row(3,'Stati Uniti',price=100,currency='USD')])
    assert result['release_date']=='1985' and result['date_scope']=='reference'
    assert result['reference_dates']==['1982','1985']
    assert result['field_sources']['release_date']==[1]


def test_missing_base_uses_an_explicit_reference_not_a_claimed_launch_date():
    result,=release_summaries([reference(1,'1986'),reference(2,'1989'),reference(3,'1987'),row(4,'Francia',price=100,currency='FRF')])
    assert result['release_date']=='1986' and result['date_scope']=='reference'
    assert 'Primo anno registrato' in result['reference_note']


def test_reference_variants_do_not_override_a_documented_date_or_a_later_list():
    refs=[reference(1,'1982',True),reference(2,'1984')]
    result=release_summaries([*refs,row(3,'Stati Uniti',year='1990',price=100,currency='USD')])
    assert any(r['release_date']=='1990' and r['price']==100 for r in result)
    assert any(r['date_scope']=='reference' and r['release_date']=='1982' for r in result)
    result=release_summaries([*refs,row(3,'Stati Uniti',price=100,currency='USD',price_type='listino successivo')])
    assert next(r for r in result if r['price'] is not None)['release_date'] is None


def test_different_priced_hardware_variants_keep_their_own_reference_dates():
    result=release_summaries([{**reference(1,'1982',True),'model_variant':'16K'},
        {**reference(2,'1984',True),'model_variant':'64K'},
        {**row(3,'Regno Unito',price=100,currency='GBP'),'model_variant':'16K'},
        {**row(4,'Regno Unito',price=200,currency='GBP'),'model_variant':'64K'}])
    assert {(r['model_variant'],r['release_date'],r['price']) for r in result}=={('16K','1982',100),('64K','1984',200)}


def test_new_variant_year_does_not_recreate_a_card_beside_a_documented_launch():
    price={**row(1,'Europa',year='1981-12',price=399,currency='GBP'),
        'date_evidence':{'kind':'documented_launch','source_ids':[1]},'date_scope':'model'}
    result,=release_summaries([price,reference(2,'1984')])
    assert result['release_date']=='1981-12' and result['price']==399 and result['release_ids']==[1,2]


def test_reference_context_can_be_recomputed_without_changing_prices():
    price={**row(1,'Stati Uniti',year='1983',price=100,currency='USD'),
        'date_evidence':{'kind':'reference','base':False,'source_ids':[1]},'date_scope':'reference'}
    result,=release_summaries([price,reference(2,'1981',True)])
    assert result['release_date']=='1981' and result['price']==100 and result['date_scope']=='reference'
    assert result['release_ids']==[1,2]
    result,=release_summaries([price,row(2,year='1982')])
    assert result['release_date']=='1982' and result['date_scope']=='model'
    assert 'reference_note' not in result


def test_same_documented_market_has_regional_date_scope_and_zero_price():
    summary, = release_summaries([row(1, 'Stati Uniti', year='1982'), row(2, 'Stati Uniti', price=0, currency='USD')])
    assert summary['date_scope'] == 'market' and summary['price'] == 0


@pytest.mark.parametrize('entries', [
    [row(1, year='1982'), row(2, 'Stati Uniti', year='1983', price=3298, currency='USD')],
    [row(1, 'Stati Uniti', year='1982'), row(2, price=3298, currency='USD')],
    [row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD', price_type='listino successivo')],
    [row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD', end='1981')],
    [row(1, year='1982', currency='EUR'), row(2, 'Stati Uniti', price=3298, currency='USD')],
    [row(1, 'Globale', year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD')],
])
def test_ambiguous_or_conflicting_releases_remain_distinct(entries):
    result = release_summaries(entries)
    assert len(result) == len(entries) and not any(item['merged'] for item in result)
    assert sorted(identifier for item in result for identifier in item['release_ids']) == [row['id'] for row in entries]


def test_reported_macintosh_lc_year_day_and_price_form_one_summary():
    rows = [row(1, year='1990'), row(2, year='1990-10-15'),
        row(3, 'Stati Uniti', price=2499, currency='USD', price_type='prezzo riportato')]
    before = deepcopy(rows)
    summary, = release_summaries(rows)
    assert (summary['market'], summary['release_date'], summary['price'], summary['currency']) == ('Stati Uniti', '1990-10-15', 2499, 'USD')
    assert summary['date_scope'] == 'model' and summary['release_ids'] == [1, 2, 3]
    assert summary['field_sources']['release_date'] == [2]  # The year-only source never supports the day.
    assert summary['field_sources']['price'] == [3] and summary['original_releases'] == before
    assert rows == before
    for ordering in permutations(rows):
        assert release_summaries(ordering) == [summary]


@pytest.mark.parametrize('dates,expected', [
    (['1990', '1990-10'], '1990-10'),
    (['1990', '1990-10', '1990-10-15'], '1990-10-15'),
    (['2000', '2000-02', '2000-02-29'], '2000-02-29'),
])
def test_date_only_refinements_coalesce_without_inventing_precision(dates, expected):
    rows = [row(i, year=value) for i, value in enumerate(dates, 1)]
    summary, = release_summaries(rows)
    assert summary['release_date'] == expected
    assert summary['field_sources']['release_date'] == [len(dates)]
    assert summary['original_releases'] == rows


@pytest.mark.parametrize('dates', [
    ['1990', '1991'], ['1990', '1990-10', '1990-11'],
    ['1990', '1990-10', '1990-10-15', '1990-10-16'],
])
def test_actual_date_disagreements_do_not_pick_the_first_or_last_date(dates):
    rows = [row(i, year=value) for i, value in enumerate(dates, 1)]
    rows.append(row(len(rows) + 1, 'Stati Uniti', price=2499, currency='USD'))
    expected = release_summaries(rows)
    assert len(expected) == len(rows) and expected[-1]['release_date'] is None
    for ordering in permutations(rows):
        assert release_summaries(ordering) == expected


def test_shared_precision_refinements_keep_unique_offer_ids_and_original_regional_precision():
    rows = [row(1, year='1990'), row(2, year='1990-10-15'),
        row(3, 'Stati Uniti', price=2499, currency='USD'), row(4, 'Giappone', price=200000, currency='JPY')]
    summaries = release_summaries(rows)
    assert [r['id'] for r in summaries] == [3, 4]
    assert all(r['release_date'] == '1990-10-15' and r['field_sources']['release_date'] == [2] for r in summaries)
    regional, = release_summaries([row(1, year='1990-10-15'), row(2, 'Stati Uniti', year='1990', price=2499, currency='USD')])
    assert regional['release_date'] == '1990' and regional['date_scope'] == 'market'
    assert regional['field_sources']['release_date'] == [2]


def test_partial_discontinuation_date_can_contain_a_later_month_without_creating_a_day():
    summary, = release_summaries([row(1, year='1990-10-15'), row(2, 'Stati Uniti', price=2499, currency='USD', end='1990')])
    assert summary['release_date'] == '1990-10-15' and summary['discontinuation_date'] == '1990'
    separate = release_summaries([row(1, year='1990-10-15'), row(2, 'Stati Uniti', price=2499, currency='USD', end='1990-10-14')])
    assert len(separate) == 2


@pytest.mark.parametrize('offers', [
    [row(2, 'Stati Uniti', price=3298, currency='USD'), row(3, 'Giappone', price=200000, currency='JPY')],
    [row(2, 'Stati Uniti', price=3298, currency='USD'), row(3, 'Stati Uniti', price=3998, currency='USD')],
    # Equal amounts may describe different configurations: retain both offers.
    [row(2, 'Stati Uniti', price=3298, currency='USD'), row(3, 'Stati Uniti', price=3298, currency='USD')],
    [row(2, 'Francia', price=1000, currency='FRF'), row(3, 'Regno Unito', price=1000, currency='GBP')],
])
def test_model_date_completes_all_launch_offers_without_collapsing_prices(offers):
    original = [row(1, year='1982'), *offers]
    before = deepcopy(original)
    result = release_summaries(original)
    assert original == before and len(result) == 2
    assert [item['id'] for item in result] == [2, 3]
    assert all(item['release_date'] == '1982' and item['date_scope'] == 'model' for item in result)
    assert [item['price'] for item in result] == [offer['price'] for offer in offers]
    for item, offer in zip(result, offers):
        assert item['currency'] == offer['currency'] and item['release_ids'] == [1, offer['id']]
        assert item['field_sources']['release_date'] == [1]
        assert item['field_sources']['price'] == [offer['id']]
    for ordering in permutations(original):
        assert release_summaries(ordering) == result


def test_shared_market_date_does_not_leak_to_another_country_or_variant():
    rows = [row(1, 'Stati Uniti', year='1982'),
        row(2, 'Stati Uniti', price=3298, currency='USD'), row(3, 'Stati Uniti', price=3998, currency='USD'),
        row(4, 'Giappone', price=200000, currency='JPY'),
        {**row(5, 'Stati Uniti', price=4998, currency='USD'), 'model_variant': 'Synthetic hardware revision'}]
    result = {item['id']: item for item in release_summaries(rows)}
    assert set(result) == {2, 3, 4, 5}
    assert result[2]['release_date'] == result[3]['release_date'] == '1982'
    assert result[2]['date_scope'] == result[3]['date_scope'] == 'market'
    assert result[4]['release_date'] is None and result[5]['release_date'] is None


def test_disagreeing_shared_years_and_later_price_lists_remain_undated():
    rows = [row(1, year='1982'), row(2, year='1983'), row(3, 'Stati Uniti', price=3298, currency='USD'),
        row(4, 'Giappone', price=200000, currency='JPY')]
    for ordering in permutations(rows):
        result = release_summaries(ordering)
        assert len(result) == 4 and all(item['release_date'] is None for item in result if item['price'] is not None)
    result = release_summaries([row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD'),
        row(3, 'Giappone', price=200000, currency='JPY', price_type='listino successivo')])
    assert result[0]['release_date'] == '1982'
    assert result[1]['release_date'] is None and result[1]['price_type'] == 'listino successivo'


def test_documented_regional_date_and_currencies_are_preserved_with_shared_year():
    rows = [row(1, year='1982'), row(2, 'Stati Uniti', price=3298, currency='USD'),
        row(3, 'Giappone', year='1983-05', price=200000, currency='JPY')]
    result = {item['market']: item for item in release_summaries(rows)}
    assert result['Stati Uniti']['release_date'] == '1982'
    assert result['Stati Uniti']['date_scope'] == 'model'
    assert result['Giappone']['release_date'] == '1983-05' and result['Giappone']['date_scope'] == 'market'
    assert result['Giappone']['original_releases'] == [rows[2]]


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
        assert model['releases'] == data['display_releases']
        assert model['releases'][0]['original_releases'][1]['release_date'] is None
        saved = db.scalars(select(Release).where(Release.computer_id == 1).order_by(Release.id)).all()
        assert [release.id for release in saved] == ids and saved[1].release_date is None


def test_documented_source_wins_over_equal_reference_year_regardless_of_ids():
    for ref_id,doc_id in [(1,2),(2,1)]:
        result,=release_summaries([reference(ref_id,'1982',True),row(doc_id,year='1982'),row(3,'Stati Uniti',price=100,currency='USD')])
        assert result['date_scope']=='model' and result['release_date']=='1982'
        assert 'reference_note' not in result
        assert result['field_sources']['release_date']==[doc_id]
