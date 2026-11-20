"""All-catalog date/price context stays correct after successive Excel imports."""
from datetime import date

from sqlalchemy import select

from app.main import SessionLocal
from app.models import Computer, Manufacturer, Market, Release, Source
from price_workbook_fixture import entry, workbook


def test_successive_workbooks_normalize_all_models_without_editing_raw_evidence(client):
    with SessionLocal() as db:
        maker = db.scalar(select(Manufacturer).where(Manufacturer.name == 'IBM'))
        unknown = db.scalar(select(Market).where(Market.name == 'Non specificato dalla fonte')) or Market(name='Non specificato dalla fonte')
        citation = Source(title='Synthetic independent model chronology', url='https://example.org/synthetic-launch-date')
        models = [Computer(manufacturer=maker, model_name=f'Synthetic Commercialization {year}', releases=[
            Release(market=unknown, release_date=date(year, 1, 1), release_precision='year', sources=[citation])]) for year in (1982, 1985)]
        db.add_all(models); db.commit()
        ids = [c.id for c in models]; source_id = citation.id
    def import_prices(records):
        response = client.post('/api/admin/imports/upload', files={'file': ('synthetic-prices.xlsx', workbook(records))},
            data={'provider': 'historical_prices', 'rights_confirmed': 'true'})
        assert response.status_code == 201, response.text
        applied = client.post(f'/api/admin/imports/{response.json()["id"]}/apply')
        assert applied.status_code == 200 and applied.json()['status'] == 'completed', applied.text
    first = [entry(**{'Modello': f'Synthetic Commercialization {year}'}) for year in (1982, 1985)]
    import_prices(first)
    for cid in ids:
        before = client.get(f'/api/computers/{cid}').json()
        assert len(before['display_releases']) == 1
    # The research sheet's model-year cell is deliberately different. It must
    # not replace the independent chronology or become a regional launch date.
    second = [entry(**{'Modello': f'Synthetic Commercialization {year}', 'Anno lancio': '2026',
        'Mercato / Paese': market, 'Valuta': currency, 'Prezzo al lancio': amount})
        for year in (1982, 1985) for market, currency, amount in [('Giappone', 'JPY', '200000'), ('Regno Unito', 'GBP', '1450')]]
    import_prices(second)
    snapshots = {}
    for cid, year in zip(ids, (1982, 1985)):
        data = client.get(f'/api/computers/{cid}').json()
        assert len(data['display_releases']) == 3
        assert len({r['id'] for r in data['display_releases']}) == 3
        assert {r['market'] for r in data['display_releases']} == {'Stati Uniti', 'Giappone', 'Europa'}
        assert all(r['release_date'] == str(year) and r['date_scope'] == 'model' for r in data['display_releases'])
        assert all(r['field_sources']['release_date'] == [source_id] for r in data['display_releases'])
        assert len(data['releases']) == 4
        assert all(r['release_date'] is None for r in data['releases'] if r['price'] is not None)
        assert data['year'] == year
        compared = client.get('/api/compare', params={'ids': ','.join(map(str, ids))}).json()
        assert next(c for c in compared if c['id'] == cid)['display_releases'] == data['display_releases']
        editor = client.get(f'/api/admin/computers/{cid}').json()
        assert sum(r['release_date'] is None for r in editor['releases']) == 3
        snapshots[cid] = data['releases']
    import_prices(second)
    for cid in ids:
        assert client.get(f'/api/computers/{cid}').json()['releases'] == snapshots[cid]
    with SessionLocal() as db:
        assert all(r.release_date is None for r in db.scalars(select(Release).where(Release.computer_id.in_(ids), Release.price.is_not(None))))


def test_reported_lc_precision_refinement_is_global_in_api_comparison_and_editor(client):
    with SessionLocal() as db:
        maker = db.scalar(select(Manufacturer).where(Manufacturer.name == 'Apple'))
        # Use the actual placeholder understood by the importers.
        unknown = db.scalar(select(Market).where(Market.name == 'Non specificato dalla fonte')) or Market(name='Non specificato dalla fonte')
        apple_unknown = db.scalar(select(Market).where(Market.name == 'Non specificato dalla fonte (AppleDB)')) or Market(name='Non specificato dalla fonte (AppleDB)')
        us = db.scalar(select(Market).where(Market.name == 'Stati Uniti')) or Market(name='Stati Uniti')
        sources = [Source(title=f'Synthetic LC reported source {i}', url=f'https://example.org/lc-{i}') for i in range(3)]
        computer = Computer(manufacturer=maker, model_name='Macintosh LC', releases=[
            Release(market=unknown, release_date=date(1990, 1, 1), release_precision='year', sources=[sources[0]]),
            Release(market=apple_unknown, release_date=date(1990, 10, 15), release_precision='day', sources=[sources[1]]),
            Release(market=us, price=2499, currency='USD', price_type='prezzo riportato', sources=[sources[2]])])
        db.add(computer); db.commit(); cid = computer.id
        ids = [r.id for r in computer.releases]
        day_source = sources[1].id
    data = client.get(f'/api/computers/{cid}').json()
    summary, = data['display_releases']
    assert summary['release_date'] == '1990-10-15' and summary['price'] == 2499
    assert summary['release_ids'] == ids and summary['field_sources']['release_date'] == [day_source]
    assert summary['date_scope'] == 'model'
    assert [r['release_date'] for r in data['releases']] == ['1990', '1990-10-15', None]
    compared = client.get('/api/compare', params={'ids': f'{cid},1'}).json()
    assert next(c for c in compared if c['id'] == cid)['display_releases'] == [summary]
    editor = client.get(f'/api/admin/computers/{cid}').json()
    assert [r['release_date'] for r in editor['releases']] == ['1990', '1990-10-15', None]
