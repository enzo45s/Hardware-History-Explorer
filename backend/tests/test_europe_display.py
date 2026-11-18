"""Geographic summaries preserve hardware variants, regional prices and originals."""
from copy import deepcopy
from datetime import date
from itertools import permutations

import pytest
from sqlalchemy import select

from app.configuration_display import configuration_summaries
from app.geography import european_countries
from app.main import SessionLocal
from app.models import Computer, Configuration, Market, Release, Specification
from app.release_display import release_summaries


@pytest.mark.parametrize('country', ['Spain', 'Spagna', 'Italia', 'Italy', 'UK', 'U.K.', 'United Kingdom',
    'France', 'Francia', 'Germany', 'Germania', 'Sweden', 'Svezia', 'Norway', 'Norvegia', 'Switzerland',
    'Svizzera', 'Poland', 'Netherlands', 'Greece', 'Ireland', 'Portugal', 'Finland', 'Iceland', 'Belarus',
    'Ukraine', 'Czechoslovakia', 'Yugoslavia', 'Serbia and Montenegro', 'Kosovo', 'Gibraltar', 'Europe',
    'Europa', 'France/Germany', 'Sweden/Finland', 'Italy, Spain, UK'])
def test_geographic_europe_includes_non_eu_countries_and_regional_aliases(country):
    assert european_countries(country)


@pytest.mark.parametrize('country', ['USA', 'Japan', 'Canada', 'Australia', 'Brazil', 'Greenland', 'French Guiana',
    'Canary Islands', 'Russia', 'Turkey', 'Kazakhstan', 'USSR', 'Georgia', 'Azerbaijan', 'Armenia', 'Cyprus',
    'Cipro', 'USA/France', 'Europe/Japan', 'French', 'Spanish', 'English', 'Portuguese', 'PAL', 'NTSC',
    'EUR', 'EMEA', 'Worldwide', 'Unknown', 'Synthetic Europe computer'])
def test_ambiguous_transcontinental_non_european_and_non_geographic_labels_are_not_inferred(country):
    assert not european_countries(country)


def config(identifier, name, ram=64, *, description=None, unit='KiB', model='Z80', role='Capacità'):
    specs = [{'id': identifier * 10, 'component_type': 'RAM', 'component_name': None,
              'property_name': role, 'numeric_value': ram, 'text_value': None, 'unit': unit,
              'sources': [{'id': identifier, 'title': 'Synthetic technical source'}]},
             {'id': identifier * 10 + 1, 'component_type': 'CPU', 'component_name': 'maincpu',
              'property_name': 'Modello', 'numeric_value': None, 'text_value': model, 'unit': None, 'sources': []}]
    return {'id': identifier, 'variant_name': name, 'display_name': name, 'description': description,
            'display_description': description, 'specifications': specs}


def test_equal_european_configurations_collapse_once_and_keep_all_original_ids_sources_and_values():
    rows = [config(1, 'MAME test_es — Spain'), config(2, 'MAME test_it — Italy'),
            config(3, 'MAME test_uk — UK'), config(4, 'MAME test_fr — France'), config(5, 'USA')]
    before = deepcopy(rows)
    result = configuration_summaries(rows, 'Synthetic computer')
    assert rows == before and len(result) == 2
    europe = result[0]
    assert europe['display_name'] == 'Europa' and europe['countries'] == ['Francia', 'Italia', 'Regno Unito', 'Spagna']
    assert europe['configuration_ids'] == [1, 2, 3, 4]
    assert europe['specifications'][0]['specification_ids'] == [10, 20, 30, 40]
    assert [source['id'] for source in europe['specifications'][0]['sources']] == [1, 2, 3, 4]
    assert result[1]['display_name'] == 'USA'
    assert configuration_summaries(list(reversed(rows)), 'Synthetic computer') == result


@pytest.mark.parametrize('different', [config(2, 'Italy', ram=128), config(2, 'Italy', model='Z80A'),
    config(2, 'Italy', unit='KB'), config(2, 'Italy', role='Capacità predefinita (MAME)'),
    config(2, 'Italy', description='Different board revision')])
def test_genuinely_different_hardware_quantities_units_scopes_and_notes_are_distinct(different):
    groups = configuration_summaries([config(1, 'France'), different], 'Synthetic computer')
    assert len(groups) == 2 and len({row['display_name'] for row in groups}) == 2
    assert all(row['display_name'].startswith('Europa') for row in groups)


def test_keyboard_and_revision_qualifiers_are_preserved_and_mixed_regions_are_not_guessed():
    rows = [config(1, 'Synthetic (France, AZERTY Keyboard)'), config(2, 'Synthetic (UK, QWERTY Keyboard)'),
            config(3, 'ROM 01 (Spain)'), config(4, 'ROM 03 (Germany)'), config(5, 'Synthetic (France, Japan)'),
            config(6, 'Turkey'), config(7, 'French')]
    result = configuration_summaries(rows, 'Synthetic')
    assert [row['display_name'] for row in result[:4]] == ['Europa · AZERTY Keyboard', 'Europa · QWERTY Keyboard',
                                                       'Europa · ROM 01', 'Europa · ROM 03']
    assert [row['display_name'] for row in result[4:]] == [row['display_name'] for row in rows[4:]]


def test_country_codes_do_not_turn_pc_at_or_special_editions_into_european_variants():
    rows = [config(1, 'AT'), config(2, 'IBM PC (AT)'), config(3, 'SE'), config(4, 'ME'), config(5, 'France (SECAM)')]
    result = configuration_summaries(rows, 'Synthetic computer')
    assert [row['display_name'] for row in result[:4]] == [row['variant_name'] for row in rows[:4]]
    assert result[4]['display_name'] == 'Europa · SECAM'


def test_actual_apple_regional_firmware_variants_group_without_losing_enhanced_platinum_or_unidisk():
    rows = [config(1, 'MAME ee_fr — Apple //e (enhanced, France)'),
            config(2, 'MAME ee_de — Apple //e (enhanced, Germany)'),
            config(3, 'MAME ep_uk — Apple //e (Platinum, UK)'), config(4, 'MAME uk2086 — UK-2086 ver. 1.2')]
    result = configuration_summaries(rows, 'Apple //e')
    assert len(result) == 3
    assert result[0]['display_name'] == 'Europa · enhanced' and result[0]['configuration_ids'] == [1, 2]
    assert result[1]['display_name'] == 'Europa · Platinum'
    assert result[2]['display_name'] == 'MAME uk2086 — UK-2086 ver. 1.2'
    rows = [config(1, 'MAME c_de — Apple //c (UniDisk 3.5, Germany)'),
            config(2, 'MAME c_fr — Apple //c (UniDisk 3.5, France)')]
    profile, = configuration_summaries(rows, 'Apple //c')
    assert profile['display_name'] == 'Europa · UniDisk 3.5' and profile['configuration_ids'] == [1, 2]


def release(identifier, market, *, year='1982', price=None, currency=None, kind=None):
    return {'id': identifier, 'market': market, 'release_date': year, 'discontinuation_date': None,
            'price': price, 'currency': currency, 'price_type': kind,
            'sources': [{'id': identifier, 'title': 'Synthetic release source'}]}


def test_repeated_regional_dates_and_identical_offers_merge_as_europe_without_rewriting_originals():
    rows = [release(1, 'Spain', price=1000, currency='EUR'), release(2, 'France', price=1000, currency='EUR'),
            release(3, 'UK', price=1000, currency='EUR')]
    original = deepcopy(rows)
    summary, = release_summaries(rows)
    assert summary['market'] == 'Europa' and summary['price'] == 1000 and summary['release_date'] == '1982'
    assert summary['release_ids'] == [1, 2, 3] and summary['original_releases'] == original and rows == original
    assert summary['original_markets'] == ['Spain', 'France', 'UK']
    assert summary['price_countries'] == ['Francia', 'Regno Unito', 'Spagna']
    assert summary['field_sources']['price'] == [1, 2, 3]


def test_european_date_only_duplicates_merge_and_unique_model_date_can_complete_one_regional_offer():
    dated, = release_summaries([release(1, 'Italy'), release(2, 'UK')])
    assert dated['market'] == 'Europa' and dated['release_ids'] == [1, 2]
    rows = [release(1, 'Non specificato dalla fonte'), release(2, 'France', year=None, price=1000, currency='EUR'),
            release(3, 'Spain', year=None, price=1000, currency='EUR')]
    summary, = release_summaries(rows)
    assert (summary['market'], summary['release_date'], summary['price']) == ('Europa', '1982', 1000)
    assert summary['release_ids'] == [1, 2, 3] and summary['date_scope'] == 'model'
    for ordering in permutations(rows):
        assert release_summaries(ordering) == [summary]


@pytest.mark.parametrize('rows', [
    [release(1, 'France', price=1000, currency='FRF'), release(2, 'UK', price=1000, currency='GBP')],
    [release(1, 'France', price=1000, currency='EUR'), release(2, 'Italy', price=2000, currency='EUR')],
    [release(1, 'France', year='1982'), release(2, 'Italy', year='1983')],
    [release(1, 'France', price=1000), release(2, 'Italy', price=1000)],
    [release(1, 'France', price=1000, currency='EUR'), release(2, 'FR', price=1000, currency='EUR')],
    [release(1, 'France', price=1000, currency='EUR', kind='prezzo riportato'),
     release(2, 'Italy', price=1000, currency='EUR', kind='listino successivo')],
])
def test_different_prices_dates_currencies_unknown_currency_and_same_country_variants_are_not_lost(rows):
    result = release_summaries(rows)
    assert len(result) == 2 and all(row['market'] == 'Europa' for row in result)
    assert sorted(identifier for row in result for identifier in row['release_ids']) == [1, 2]


def test_non_european_release_labels_are_unchanged():
    rows = [release(1, 'Russia'), release(2, 'Japan'), release(3, 'Cyprus'), release(4, 'Australia')]
    assert [row['market'] for row in release_summaries(rows)] == [row['market'] for row in rows]


def test_api_has_european_profiles_but_editor_and_saved_data_preserve_every_country_and_configuration(client):
    with SessionLocal() as db:
        computer = db.get(Computer, 1)
        computer.configurations.clear(); computer.releases.clear(); db.flush()
        for country in ['Spain', 'Italy', 'UK', 'France']:
            computer.configurations.append(Configuration(variant_name=country, specifications=[Specification(
                component_type='RAM', property_name='Capacità', numeric_value=64, unit='KiB')]))
            computer.releases.append(Release(market=Market(name=country), release_date=date(1982, 1, 1), release_precision='year'))
        db.commit()
        original_configs = [(cfg.id, cfg.variant_name) for cfg in computer.configurations]
        original_markets = [(r.id, r.market.name) for r in computer.releases]
    data = client.get('/api/computers/1').json()
    assert len(data['configurations']) == 4 and len(data['display_configurations']) == 1
    assert data['display_configurations'][0]['display_name'] == 'Europa'
    assert len(data['releases']) == 4 and len(data['display_releases']) == 1
    assert data['display_releases'][0]['market'] == 'Europa'
    assert client.get('/api/compare?ids=1,2').json()[0]['display_configurations'] == data['display_configurations']
    editor = client.get('/api/admin/computers/1').json()
    assert len(editor['configurations']) == 4 and len(editor['releases']) == 4
    with SessionLocal() as db:
        computer = db.scalar(select(Computer).where(Computer.id == 1))
        assert [(cfg.id, cfg.variant_name) for cfg in computer.configurations] == original_configs
        assert [(r.id, r.market.name) for r in computer.releases] == original_markets
