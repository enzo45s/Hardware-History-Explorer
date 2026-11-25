from datetime import date
import pytest
from sqlalchemy import create_engine,text,inspect,select
from app.main import SessionLocal
from app.models import Manufacturer,Source,manufacturer_source
from app.manufacturer_profiles import ensure_schema


def test_company_profile_precision_sources_and_catalog_without_fabricated_metadata(client):
    citation=client.post('/api/sources',json={'title':'Synthetic company history','url':'https://example.org/company'}).json()
    payload={'name':'Synthetic Company','description':'Storia sintetica in italiano.','country':'Italia','founded':'1978','ceased':'1995-06',
        'legal_name':'Synthetic Company S.p.A.','headquarters':'Ivrea','founders':'Fondatore sintetico',
        'logo_url':'https://example.org/logo.png','logo_source_url':'https://example.org/logo',
        'logo_author':'Autore sintetico','logo_license':'Condizioni di prova','source_ids':[citation['id']]}
    response=client.post('/api/manufacturers',json=payload);assert response.status_code==201,response.text
    mid=response.json()['id']
    unknown=client.get('/api/manufacturers/1/profile').json()
    assert unknown['description'] is None and unknown['logo_url'] is None
    assert unknown['founded'] is None and unknown['sources']==[]
    a=client.post('/api/computers',json={'model_name':'Synthetic Model A','manufacturer_id':mid,'releases':[{'market_id':client.get('/api/meta').json()['markets'][0]['id'],'release_date':'1981'}]}).json()
    b=client.post('/api/computers',json={'model_name':'Synthetic Model B','manufacturer_id':mid}).json()
    profile=client.get(f'/api/manufacturers/{mid}/profile').json()
    assert profile['founded']=='1978' and profile['ceased']=='1995-06'
    assert profile['computer_count']==2 and profile['catalog_year_range']==[1981,1981]
    assert profile['sources'][0]['id']==citation['id']
    assert {c['id'] for c in client.get(f'/api/computers?manufacturer_id={mid}').json()['items']}=={a['id'],b['id']}
    with SessionLocal() as db:
        m=db.get(Manufacturer,mid)
        assert (m.founded,m.founded_precision)==(date(1978,1,1),'year')
        assert (m.ceased,m.ceased_precision)==(date(1995,6,1),'month')
        assert db.execute(select(manufacturer_source.c.verification_status).where(manufacturer_source.c.target_id==mid)).scalar()=='pending'
    response=client.put(f'/api/manufacturers/{mid}',json={'name':'Renamed Company'})
    assert response.status_code==200 and response.json()['description']==payload['description']
    assert response.json()['source_ids']==[citation['id']]
    assert client.delete(f'/api/manufacturers/{mid}').status_code==409


@pytest.mark.parametrize('changes',[
    {'logo_url':'javascript:alert(1)'},{'logo_url':'data:image/png;base64,aaa'},
    {'logo_source_url':'file:///tmp/logo'},{'logo_license_url':'https://user:pass@example.org'},
    {'founded':'1980','ceased':'1979'},{'ceased':'1900'},{'source_ids':[999999]},
])
def test_invalid_profile_updates_are_atomic(client,changes):
    created=client.post('/api/manufacturers',json={'name':'Synthetic validation','founded':'1980'}).json()
    before=client.get(f"/api/manufacturers/{created['id']}").json()
    response=client.put(f"/api/manufacturers/{created['id']}",json={'name':'Must not change',**changes})
    assert response.status_code==422,response.text
    assert client.get(f"/api/manufacturers/{created['id']}").json()==before


def test_profile_columns_upgrade_legacy_database_repeatably():
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE manufacturers(id INTEGER PRIMARY KEY,name VARCHAR(160),country VARCHAR(100),founded DATE,website VARCHAR(500))'))
        conn.execute(text("INSERT INTO manufacturers VALUES(7,'Legacy manufacturer','Italia','1980-02-03','https://example.org')"))
    ensure_schema(engine);ensure_schema(engine)
    with engine.connect() as conn:
        row=conn.execute(text('SELECT * FROM manufacturers')).mappings().one()
        assert row['id']==7 and row['founded']=='1980-02-03'
        assert row['description'] is None and row['founded_precision'] is None
    assert len(inspect(engine).get_columns('manufacturers'))==len(Manufacturer.__table__.columns)


def test_profile_sources_survive_manufacturer_merge(client):
    from app.importing.reconcile import prepare,apply
    with SessionLocal() as db:
        source=Manufacturer(name='Apple Computer',description='Storia sintetica originale',founded=date(1980,1,1),founded_precision='year',sources=[Source(title='Synthetic reference')])
        target=db.scalar(select(Manufacturer).where(Manufacturer.name=='Apple'))
        db.add_all([source,target]);db.commit();target_id=target.id
        _,_,_,preview=prepare(db,'manufacturer',source.id,target.id)
        apply(db,'manufacturer',source.id,target.id,preview['token'],'Revisione sintetica')
        current=db.get(Manufacturer,target_id)
        assert current.description=='Storia sintetica originale' and current.founded_precision=='year'
        assert len(current.sources)==1
