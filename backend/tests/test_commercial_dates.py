from datetime import date
from sqlalchemy import select,func
from app.main import SessionLocal,engine
from app.models import Computer,Manufacturer,Release,Market,Source,CatalogDirty
from app.catalog_cleanup import prepare,apply
from app.catalog_store import refresh_pending,raw_payload
from app.catalog_schema import ensure_schema


def bbc(db):
    c=db.get(Computer,1);c.model_name='BBC Micro Model B';c.manufacturer=Manufacturer(name='Acorn')
    c.releases.clear();db.flush()
    unknown=Market(name='Non specificato dalla fonte');uk=Market(name='Regno Unito')
    for year,suffix in [(1981,''),(1982,' (German)'),(1984,' (Norway)'),(1983,' (US)')]:
        c.releases.append(Release(market=unknown,release_date=date(year,1,1),release_precision='year',sources=[
            Source(title='MAME — BBC Micro Model B'+suffix+' — anno registrato',publisher='MAME',source_type='dataset',url='https://example.org/year/'+str(year))]))
    c.releases.append(Release(market=uk,price=399,currency='GBP',price_type='prezzo riportato',sources=[
        Source(title='Ricerca prezzi — Acorn BBC Micro Model B',source_type='research_reference',url='https://www.computinghistory.org.uk/det/5853/Acorn-releases-the-BBC-Micro/')]))
    db.commit();return c


def test_real_source_roles_and_documented_price_work_in_api_and_primary_tables(client):
    with SessionLocal() as db:
        c=bbc(db);raw=raw_payload(c)
        assert [r.get('date_evidence',{}).get('base') for r in raw['releases'][:4]]==[True,False,False,False]
    data=client.get('/api/computers/1').json()
    result,=data['display_releases']
    assert result['release_date']=='1981-12' and result['price']==399 and result['market']=='Europa'
    with SessionLocal() as db:
        apply(db,prepare(db));c=db.get(Computer,1)
        assert len(c.releases)==1
        assert (c.releases[0].release_date,c.releases[0].release_precision)==(date(1981,12,1),'month')
        assert prepare(db)['summary']['affected_computers']==0
    data=client.get('/api/computers/1').json()
    assert len(data['releases'])==1 and data['display_releases'][0]['release_date']=='1981-12'


def test_rule_upgrade_requeues_all_cleaned_systems_once(client):
    with SessionLocal() as db:
        bbc(db);apply(db,prepare(db))
        total=db.scalar(select(func.count()).select_from(Computer))
    ensure_schema(engine)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(CatalogDirty))==total
        refresh_pending(db)
    ensure_schema(engine)
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(CatalogDirty))==0


def test_manual_date_edit_discards_stale_derived_date_context(client):
    with SessionLocal() as db:
        bbc(db);apply(db,prepare(db))
    data=client.get('/api/admin/computers/1').json();data.pop('id')
    data['releases'][0]['release_date']='1982-02'
    response=client.put('/api/computers/1',json=data)
    assert response.status_code==200,response.text
    result,=client.get('/api/computers/1').json()['display_releases']
    assert result['release_date']=='1982-02'
    assert not result.get('commercialization_notes') and not result.get('reference_note')


def test_reimported_variant_year_is_archived_without_recreating_an_offer(client):
    with SessionLocal() as db:
        c=bbc(db);apply(db,prepare(db))
        c=db.get(Computer,1)
        c.releases.append(Release(market=Market(name='Unknown'),release_date=date(1984,1,1),release_precision='year',sources=[
            Source(title='MAME — BBC Micro Model B (Norway) — anno registrato',publisher='MAME',source_type='dataset')]))
        db.commit();refresh_pending(db)
        c=db.get(Computer,1)
        assert len(c.releases)==1 and c.releases[0].price==399
        assert c.releases[0].release_date==date(1981,12,1)
        assert prepare(db)['summary']['affected_computers']==0


def test_base_role_survives_removal_of_a_former_variant_label(client):
    with SessionLocal() as db:
        c=db.get(Computer,1);c.model_name='Merged family';c.releases.clear();db.flush()
        c.releases.append(Release(market=Market(name='Unknown'),release_date=date(1985,1,1),release_precision='year',
            catalog_details={'model_variant':'Former base'},sources=[Source(title='MAME — Former base — anno registrato',publisher='MAME')]))
        db.commit();apply(db,prepare(db))
        assert c.releases[0].catalog_details['date_evidence']['base']
        assert prepare(db)['summary']['affected_computers']==0
