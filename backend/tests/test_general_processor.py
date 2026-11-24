"""General Processor research on disposable catalogs, with real package evidence."""
import importlib,json
from datetime import date
import pytest
from sqlalchemy import select,func
from app.main import SessionLocal
from app.models import Computer,Manufacturer,Configuration,Specification,Release,Market,Source,ComputerImage,manufacturer_source
from app.import_models import ImportJob,ImportClaim,ComputerAlias
from app.importing import general_processor as research
from app.importing.engine import stage,apply_job
from app.importing.identity import computer_key,maker_key

@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'),'seed',lambda db:None)


def test_package_has_sources_prices_memory_and_honest_gaps():
    data,_=research.load()
    assert len(data['records'])==5
    assert sum(len(r['configurations']) for r in data['records'])==6
    assert sum(len(c['specifications']) for r in data['records'] for c in r['configurations'])==79
    assert all(s.get('evidence') and s['source']['url'] for r in data['records'] for c in r['configurations'] for s in c['specifications'])
    offers=[r for c in data['records'] for r in c['releases'] if r.get('price') is not None]
    assert len(offers)==5 and {r['currency'] for r in offers}=={'ITL'}
    assert not any(r['model_name']=='G5' for r in data['records'])
    gps4=next(r for r in data['records'] if r['model_name']=='GPS4')
    assert not any(s['component_type'] in ('CPU','RAM') for s in gps4['configurations'][0]['specifications'])
    assert maker_key('General Processor S.r.l.')==maker_key('General Processor')
    assert maker_key('Data General')!=maker_key('General Processor')
    assert computer_key('General Processor','GPS-5')==computer_key('General Processor','GPS5')


def test_apply_native_profile_prices_scopes_sources_and_repeat(client):
    with SessionLocal() as db:
        other=Computer(manufacturer=Manufacturer(name='Data General'),model_name='Data General/One',description='Keep')
        db.add(other);db.commit();other_id=other.id
        assert research.preview(db)['manufacturer_to_create'] and not db.scalar(select(ImportJob.id))
        result=research.apply(db)
        assert result['manufacturer_created'] and result['created']==5 and result['updated']==0
        assert result['releases_added']==10 and result['photos_added']==4
        assert db.scalar(select(func.count()).select_from(Computer))==6
        assert db.get(Computer,other_id).description=='Keep'
        maker=db.scalar(select(Manufacturer).where(Manufacturer.name=='General Processor'));mid=maker.id
        assert maker.country=='Italia' and maker.founded==date(1977,1,1) and maker.founded_precision=='year'
        assert maker.logo_source_url.endswith('id=95') and maker.sources
        assert all(r.verification_status=='pending' for r in db.execute(select(manufacturer_source).where(manufacturer_source.c.target_id==mid)))
        model=db.scalar(select(Computer).where(Computer.model_name=='Modello T'));cid=model.id
        assert len(model.configurations)==2
        prices=[r for r in model.releases if r.price is not None]
        assert sorted(r.price for r in prices)==[1731000,2212000,3289000,4572000,8722000]
        assert len({r.catalog_details['model_variant'] for r in prices})==5
        assert all(r.currency=='ITL' and r.catalog_details['price_reference_date']=='1979-10' and r.sources for r in prices)
        assert len({a.computer_id for a in db.scalars(select(ComputerAlias))})==1
        assert not db.scalar(select(ImportClaim.id).where(ImportClaim.status=='verified'))
        assert research.apply(db)['already_applied']
        assert db.scalar(select(func.count()).select_from(ImportJob))==1
    results=client.get('/api/computers',params={'q':'Model T MKIII'}).json()['items']
    assert any(c['id']==cid for c in results)
    profile=client.get(f'/api/manufacturers/{mid}/profile').json()
    assert profile['computer_count']==5 and profile['logo_url'] and profile['sources']


def test_reimport_of_both_english_names_keeps_one_card_and_two_configuration_scopes(client):
    with SessionLocal() as db:
        research.apply(db)
        c=db.scalar(select(Computer).where(Computer.model_name=='Modello T'));cid=c.id
        cfg_ids={cfg.id for cfg in c.configurations}
        price_scopes={r.id:r.catalog_details.get('model_variant') for r in c.releases}
        for name,value in [('Model T',16),('Model T MKIII',64)]:
            record={'manufacturer':'General Processor (Italy)','model_name':name,
                    'source':{'title':'Synthetic later GP source','url':'https://example.org/later-gp'},
                    'configurations':[{'variant_name':'Scheda tecnica','specifications':[{'component_type':'RAM','property_name':'Capacità','numeric_value':value,'unit':'KB'}]}]}
            job=stage(db,'1000bit','later.json','json',json.dumps([record]).encode(),records=[record]);apply_job(db,job.id)
            assert job.status=='completed' and job.rows[0].computer_id==cid
        db.expire_all();c=db.get(Computer,cid)
        assert {cfg.id for cfg in c.configurations}==cfg_ids
        assert price_scopes=={r.id:r.catalog_details.get('model_variant') for r in c.releases}
        assert db.scalar(select(func.count()).select_from(Computer))==5


def test_existing_manufacturer_curated_fields_and_existing_offers_are_preserved(client):
    with SessionLocal() as db:
        maker=Manufacturer(name='General Processor S.r.l.',country='Italia',description='Testo curato.',logo_url='https://example.org/manual-logo.png')
        c=Computer(manufacturer=maker,model_name='GPS-5',description='Storia curata.',
                   configurations=[Configuration(variant_name='Scheda tecnica',specifications=[Specification(component_type='RAM',property_name='Capacità',numeric_value=512,unit='KB')])],
                   releases=[Release(market=Market(name='Stati Uniti'),price=777,currency='USD',release_date=date(1984,1,1),release_precision='year')])
        db.add(c);db.commit();cid=c.id;mid=maker.id
        result=research.apply(db);db.expire_all()
        assert not result['manufacturer_created'] and result['created']==4 and result['updated']==1
        maker=db.get(Manufacturer,mid);c=db.get(Computer,cid)
        assert maker.description=='Testo curato.' and maker.logo_url.endswith('manual-logo.png') and maker.logo_author is None
        assert c.description=='Storia curata.' and len(c.releases)==1 and c.releases[0].price==777
        assert c.releases[0].currency=='USD' and c.releases[0].release_date==date(1984,1,1)
        assert any(s.numeric_value==512 for cfg in c.configurations for s in cfg.specifications if s.component_type=='RAM')
        assert db.scalar(select(ImportClaim.id).where(ImportClaim.computer_id==cid,ImportClaim.status=='conflict'))


def test_stage_failure_rolls_back_profile_sources_and_company(client,monkeypatch):
    with SessionLocal() as db:
        db.add(Manufacturer(name='Data General'));db.commit()
        def fail(*a,**kw):raise RuntimeError('staging failure')
        monkeypatch.setattr(research,'stage',fail)
        with pytest.raises(RuntimeError,match='staging failure'):research.apply(db)
        db.commit()
        assert list(db.scalars(select(Manufacturer.name)))==['Data General']
        assert not db.scalar(select(Source.id)) and not db.scalar(select(ImportJob.id))


def test_late_failure_rolls_back_prices_photos_aliases_and_models(client,monkeypatch):
    def fail(*a,**kw):raise RuntimeError('late catalog failure')
    monkeypatch.setattr('app.catalog_store.refresh_pending',fail)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError,match='late catalog failure'):research.apply(db)
        assert not db.scalar(select(Computer.id)) and not db.scalar(select(Manufacturer.id))
        assert not db.scalar(select(Release.id)) and not db.scalar(select(ComputerImage.id))
        assert not db.scalar(select(ComputerAlias.id)) and not db.scalar(select(ImportJob.id))


def test_repeat_does_not_recreate_a_deleted_model(client):
    with SessionLocal() as db:
        research.apply(db)
        c=db.scalar(select(Computer).where(Computer.model_name=='GPS4'));db.delete(c);db.commit()
        assert research.apply(db)['already_applied']
        assert not db.scalar(select(Computer.id).where(Computer.model_name=='GPS4'))


def test_ambiguous_company_does_not_modify_anything(client):
    with SessionLocal() as db:
        db.add_all([Manufacturer(name='General Processor'),Manufacturer(name='General Processor Srl')]);db.commit()
        with pytest.raises(ValueError,match='ambiguo'):research.apply(db)
        assert not db.scalar(select(Computer.id)) and not db.scalar(select(Source.id))
