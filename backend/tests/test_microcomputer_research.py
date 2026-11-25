"""Scoped research adds native data without replacing curated catalog records."""
import importlib,json
from datetime import date
import pytest
from sqlalchemy import select,func
from app.main import SessionLocal
from app.models import Computer,Manufacturer,Configuration,Specification,Release,Market,Source,ComputerImage
from app.import_models import ImportJob,ImportClaim,CatalogReconciliation
from app.importing import microcomputer_research as research
from app.importing.engine import stage,apply_job
from app.importing.identity import computer_key,maker_key

@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'),'seed',lambda db:None)


def test_package_primary_evidence_distinguishes_rom_dates_currency_and_identity():
    data,_=research.load();rows={r['model_name']:r for r in data['records']}
    assert len(rows)==5 and len(data['manufacturer_profiles'])==2
    assert sum(len(r['configurations'][0]['specifications']) for r in rows.values())==87
    nb=rows['NewBrain']['configurations'][0]['specifications']
    assert next(s for s in nb if s['component_type']=='ROM')['numeric_value']==28
    assert all(s['source']['url'].startswith('https://archive.org/') for s in nb if s['component_type']=='ROM')
    assert '1982-08'==data['release_notes']['Micro-Professor I'][0]['price_reference_date']
    assert rows['A 5105']['releases'][0]['release_date']=='1989-09'
    assert {r['currency'] for c in rows.values() for r in c['releases'] if r.get('price') is not None}=={'USD','DDM'}
    assert computer_key('Grundy','NewBrain AD')==computer_key('Grundy Business Systems','NewBrain')
    assert computer_key('Multitech','MPF-I')==computer_key('Multitech','Micro-Professor I')
    assert computer_key('Robotron','Z9001')==computer_key('VEB Robotron','KC 85/1')
    assert computer_key('Robotron','KC85/2')!=computer_key('Robotron','KC85/1')
    assert maker_key('Acer')!=maker_key('Multitech')


def test_native_records_sources_offer_scopes_repeat_and_public_api(client):
    with SessionLocal() as db:
        maker=Manufacturer(name='Multitech',description='Keep company history')
        db.add(Computer(manufacturer=maker,model_name='Microprofessor II'));db.commit();mid=maker.id
        preview=research.preview(db)
        assert set(preview['manufacturers_to_create'])=={'Grundy Business Systems','Robotron'}
        assert not db.scalar(select(ImportJob.id))
        result=research.apply(db)
        assert result['created']==5 and result['photos_added']==5 and result['releases_added']==6
        assert db.scalar(select(func.count()).select_from(Computer))==6
        assert db.get(Manufacturer,mid).description=='Keep company history'
        models=list(db.scalars(select(Computer).where(Computer.model_name!='Microprofessor II')))
        assert all(c.description and c.images and c.sources and c.releases for c in models)
        assert all(len(c.configurations)==1 for c in models)
        k87=next(c for c in models if c.model_name=='KC 87')
        assert sorted(r.price for r in k87.releases)==[3005,3390]
        assert len({r.catalog_details['model_variant'] for r in k87.releases})==2
        assert all(r.currency=='DDM' for r in k87.releases)
        mf=next(c for c in models if c.model_name=='Micro-Professor I')
        assert mf.releases[0].release_date==date(1981,1,1)
        assert mf.releases[0].catalog_details['price_reference_date']=='1982-08'
        assert len(mf.releases[0].sources)==2  # Introduction and later advertised price are separate evidence.
        robotron=db.scalar(select(Manufacturer).where(Manufacturer.name=='Robotron'));rid=robotron.id
        assert robotron.founded==date(1969,4,1) and robotron.ceased==date(1990,7,1)
        assert robotron.logo_url.endswith('.svg') and robotron.sources
        assert not db.scalar(select(ImportClaim.id).where(ImportClaim.status=='verified'))
        assert research.apply(db)['already_applied']
        assert db.scalar(select(func.count()).select_from(ImportJob))==1
    assert client.get('/api/manufacturers/'+str(rid)+'/profile').json()['computer_count']==3
    # The successor also mentions Z9001 in its history; the alias still has one card.
    found=client.get('/api/computers',params={'q':'Z9001'}).json()['items']
    assert len([c for c in found if c['model_name']=='KC 85/1'])==1
    assert client.get('/api/computers',params={'q':'MPF-I'}).json()['total']==1


def test_reimport_alternate_names_does_not_create_models_or_extra_technical_sheets(client):
    with SessionLocal() as db:
        research.apply(db)
        for maker,name,ram in [('VEB Robotron','Z9001',16),('Robotron','KC85/1',16),('Multitech Industrial Corporation','MPF-1',2),('Grundy','NewBrain AD',32)]:
            record={'manufacturer':maker,'model_name':name,'source':{'title':'Synthetic later source','url':'https://example.org/later'},
                'configurations':[{'variant_name':'Scheda tecnica','specifications':[{'component_type':'RAM','property_name':'Capacità','numeric_value':ram,'unit':'KB'}]}]}
            job=stage(db,'1000bit','later.json','json',json.dumps([record]).encode(),records=[record]);apply_job(db,job.id)
            assert job.status=='completed',job.rows[0].error
        assert db.scalar(select(func.count()).select_from(Computer))==5
        assert db.scalar(select(func.count()).select_from(Configuration))==5
        assert db.scalar(select(func.count()).select_from(Release))==6


def test_curated_profile_specs_prices_description_and_cover_are_preserved(client):
    with SessionLocal() as db:
        maker=Manufacturer(name='VEB Robotron',description='Manual company history',logo_url='https://example.org/logo.svg')
        c=Computer(manufacturer=maker,model_name='KC87',description='Manual computer history',
            configurations=[Configuration(variant_name='Original manual configuration',specifications=[Specification(component_type='RAM',property_name='Capacità',numeric_value=32,unit='KB')])],
            releases=[Release(market=Market(name='Europa'),release_date=date(1988,2,3),release_precision='day',price=1234,currency='DDM')],
            images=[ComputerImage(remote_url='https://example.org/manual.jpg',caption='Manual cover',license_name='Synthetic permission',source_url='https://example.org',is_primary=True)])
        db.add(c);db.commit();cid=c.id;mid=maker.id
        result=research.apply(db);db.expire_all();c=db.get(Computer,cid);maker=db.get(Manufacturer,mid)
        assert result['created']==4 and result['updated']==1
        assert c.description=='Manual computer history' and maker.description=='Manual company history'
        assert maker.logo_url=='https://example.org/logo.svg' and maker.logo_author is None
        assert len(c.releases)==1 and c.releases[0].price==1234 and c.releases[0].release_date==date(1988,2,3)
        assert len(c.configurations)==1
        assert any(s.numeric_value==32 for s in c.configurations[0].specifications if s.component_type=='RAM')
        assert next(i for i in c.images if i.is_primary).remote_url=='https://example.org/manual.jpg'
        assert db.scalar(select(ImportClaim.id).where(ImportClaim.computer_id==cid,ImportClaim.status=='conflict'))


def test_ambiguous_manufacturer_aborts_all_and_duplicate_models_are_skipped(client):
    with SessionLocal() as db:
        db.add_all([Manufacturer(name='Robotron'),Manufacturer(name='VEB Robotron')]);db.commit()
        with pytest.raises(ValueError,match='ambiguo'):research.apply(db)
        assert not db.scalar(select(Source.id)) and not db.scalar(select(ImportJob.id))
    with SessionLocal() as db:
        for maker in db.scalars(select(Manufacturer)):db.delete(maker)
        db.commit();maker=Manufacturer(name='Robotron')
        db.add_all([Computer(manufacturer=maker,model_name='KC85/1'),Computer(manufacturer=maker,model_name='Z9001')]);db.commit()
        result=research.apply(db)
        assert result['created']==4 and result['skipped'][0]['model_name']=='KC 85/1'
        assert db.scalar(select(func.count()).select_from(Computer))==6


@pytest.mark.parametrize('stage_name', ['stage','refresh_pending'])
def test_early_and_late_failure_roll_back_everything(client,monkeypatch,stage_name):
    def fail(*a,**kw):raise RuntimeError('synthetic import failure')
    if stage_name=='stage':monkeypatch.setattr(research,'stage',fail)
    else:monkeypatch.setattr('app.catalog_store.refresh_pending',fail)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError,match='synthetic import failure'):research.apply(db)
        for model in (Manufacturer,Computer,ComputerImage,Release,Source,ImportJob,CatalogReconciliation):
            assert db.scalar(select(func.count()).select_from(model))==0


def test_deleted_model_is_not_recreated_by_repeat(client):
    with SessionLocal() as db:
        research.apply(db)
        c=db.scalar(select(Computer).where(Computer.model_name=='NewBrain'));db.delete(c);db.commit()
        assert research.apply(db)['already_applied']
        assert db.scalar(select(func.count()).select_from(Computer))==4
