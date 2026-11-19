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
