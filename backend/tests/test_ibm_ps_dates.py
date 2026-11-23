"""The chronology upgrade must work after the already-published IBM package."""
import importlib
from datetime import date

import pytest
from sqlalchemy import select, func

from app.main import SessionLocal, overview, full
from app.models import Computer, Manufacturer, Release, Market, Source, release_source
from app.import_models import ImportJob, ImportClaim
from app.importing import ibm_ps_dates as dates, ibm_ps_research as research


@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'), 'seed', lambda db: None)


def test_sourced_package():
    data, checksum = dates.load()
    assert len(data['records']) == 14 and len(checksum) == 64
    assert all(row['evidence'] and row['source']['url'] for row in data['records'])
    rows = {r['model_name']: r for r in data['records']}
    assert rows['PS/2 Model 35 SX']['release_date'] == '1991'
    assert rows['PS/2 Model 35 SX']['announcement_date'] == '1991-06-11'
    assert rows['PS/2 Model 80']['offers'][1]['release_date'] == '1987-11'


def test_existing_import_is_upgraded_without_replaying_specs(client, monkeypatch):
    actual_apply = dates.apply
    # Simulate the original, already-applied package without the date supplement.
    with monkeypatch.context() as patch:
        patch.setattr(dates, 'apply', lambda *a, **kw: {})
        with SessionLocal() as db:
            research.apply(db)
    with SessionLocal() as db:
        names = {c.id: c.model_name for c in db.scalars(select(Computer))}
        assert db.scalar(select(Computer).where(Computer.model_name == 'PS/1 Model 2121')).releases == []
        result = research.apply(db)
        assert result['already_applied'] and result['created'] == 0
        assert result['dates']['release_rows_created'] == 3
        assert names == {c.id: c.model_name for c in db.scalars(select(Computer))}
        assert all(overview(c)['year'] is not None for c in db.scalars(select(Computer)))
        jobs = db.scalar(select(func.count()).select_from(ImportJob))
        assert actual_apply(db)['already_applied']
        assert db.scalar(select(func.count()).select_from(ImportJob)) == jobs
        c = db.scalar(select(Computer).where(Computer.model_name == 'PS/1 Model 2121'))
        db.delete(c); db.commit()
        assert actual_apply(db)['already_applied']
        assert not db.scalar(select(Computer.id).where(Computer.model_name == 'PS/1 Model 2121'))


def test_offer_scope_precision_and_prices_survive(client):
    with SessionLocal() as db:
        maker = Manufacturer(name='IBM'); market = Market(name='Stati Uniti')
        price_source = Source(title='Price evidence', url='https://example.org/price')
        def offer(code, price):
            return Release(market=market, price=price, currency='USD', sources=[price_source],
                           catalog_details={'model_variant': 'IBM PS/2 ' + code})
        c = Computer(manufacturer=maker, model_name='PS/2 Model 80',
                     releases=[offer('8580-071', 8495), offer('8580-111', 10995)])
        other = Computer(manufacturer=maker, model_name='PS/2 Model 35 SX', releases=[offer('8535-043', 2525)])
        db.add_all([c, other]); db.commit(); cid = c.id
        result = dates.apply(db)
        assert result['release_dates'] == 3 and result['release_rows_created'] == 0
        db.expire_all(); c = db.get(Computer, cid)
        assert c.announcement_date == date(1987, 4, 2)
        offers = sorted(c.releases, key=lambda r: r.price)
        assert [dates.date_text(r, 'release_date') for r in offers] == ['1987-07', '1987-11']
        assert [r.price for r in offers] == [8495, 10995]
        assert all(r.currency == 'USD' and r.market.name == 'Stati Uniti' for r in offers)
        assert all(price_source in r.sources and len(r.catalog_details['date_sources']) == 1 for r in offers)
        assert overview(other)['first_release'] == '1991'
        assert other.announcement_date == date(1991, 6, 11)
        assert len(full(c)['releases']) == 2
        assert not db.scalar(select(ImportClaim.id).where(ImportClaim.status == 'verified'))
        assert dates.apply(db)['already_applied']


def test_curated_incompatible_and_more_precise_dates_are_preserved(client):
    with SessionLocal() as db:
        maker = Manufacturer(name='IBM'); market = Market(name='Europa')
        rows = [Release(market=market, release_date=date(1990, 1, 1), release_precision='year'),
                Release(market=market, release_date=date(1988, 9, 15), release_precision='day'),
                Release(market=market, catalog_details={'date_manual': True}),
                Release(market=market, release_date=date(1988, 1, 1), release_precision='year')]
        c = Computer(manufacturer=maker, model_name='PS/2 Model 30-286', releases=rows)
        db.add(c); db.commit()
        result = dates.apply(db)
        assert result['release_dates'] == 1 and len(result['preserved']) == 3
        assert [dates.date_text(r, 'release_date') for r in rows] == ['1990', '1988-09-15', None, '1988-09-13']
        assert len(c.releases) == 4


def test_verified_date_and_ambiguous_models_are_not_changed(client):
    with SessionLocal() as db:
        maker = Manufacturer(name='IBM'); market = Market(name='Europa')
        source = Source(title='Curated chronology', url='https://example.org/curated')
        c = Computer(manufacturer=maker, model_name='PS/2 Model 50', releases=[
            Release(market=market, release_date=date(1987, 1, 1), release_precision='year', sources=[source])])
        db.add_all([c, Computer(manufacturer=maker, model_name='PS/2 8580-071'),
                    Computer(manufacturer=maker, model_name='PS/2 8580-111')]); db.commit()
        db.execute(release_source.update().values(verification_status='verified')); db.commit()
        result = dates.apply(db)
        assert result['release_dates'] == 0
        assert dates.date_text(c.releases[0], 'release_date') == '1987'
        assert any(i['model_name'] == 'PS/2 Model 80' for i in result['skipped'])


def test_late_failure_rolls_back_chronology_sources_and_jobs(client, monkeypatch):
    with SessionLocal() as db:
        c = Computer(manufacturer=Manufacturer(name='IBM'), model_name='PS/2 Model 50')
        db.add(c); db.commit(); cid = c.id
        def fail(*a, **kw):
            raise RuntimeError('late failure')
        monkeypatch.setattr('app.catalog_store.refresh_pending', fail)
        with pytest.raises(RuntimeError, match='late failure'):
            dates.apply(db)
        db.expire_all(); c = db.get(Computer, cid)
        assert c.announcement_date is None and c.releases == [] and c.sources == []
        assert not db.scalar(select(ImportJob.id))
        assert not db.scalar(select(Source.id))


def test_unscoped_offer_does_not_infer_variant_from_price(client):
    with SessionLocal() as db:
        c = Computer(manufacturer=Manufacturer(name='IBM'), model_name='PS/2 Model 80',
                     releases=[Release(market=Market(name='Stati Uniti'), price=8495, currency='USD')])
        db.add(c); db.commit()
        dates.apply(db)
        assert dates.date_text(c.releases[0], 'release_date') == '1987'
        assert c.releases[0].price == 8495


def test_supplement_failure_also_rolls_back_first_technical_import(client, monkeypatch):
    original = dates.apply
    def fail(db, **kwargs):
        original(db, **kwargs)
        raise RuntimeError('failure after chronology')
    monkeypatch.setattr(dates, 'apply', fail)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match='failure after chronology'):
            research.apply(db)
        assert not db.scalar(select(Computer.id))
        assert not db.scalar(select(ImportJob.id))
        assert not db.scalar(select(Source.id))
