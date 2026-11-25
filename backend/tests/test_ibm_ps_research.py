import importlib,json
import pytest
from sqlalchemy import select,func,update
from app.main import SessionLocal
from app.models import Computer,Manufacturer,Configuration,Specification,Source,Release,Market,ComputerImage,spec_source
from app.import_models import ImportJob,ImportClaim,ComputerAlias
from app.importing import ibm_ps_research as research
from app.importing.ibm_ps_names import commercial_name
from app.importing.identity import computer_key
from app.importing.engine import stage,apply_job
from app.catalog_cleanup import prepare,apply as cleanup

@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'),'seed',lambda db:None)

def seed():
    data,_=research.load();ids={}
    with SessionLocal() as db:
        maker=Manufacturer(name='IBM');source=Source(title='Original data',url='https://example.org/previous');market=Market(name='Stati Uniti')
        for name in sorted({r['model_name'] for r in data['corrections']}):
            specs=[Specification(**r['before'],sources=[source]) for r in data['corrections'] if r['model_name']==name]
            if any(k in name for k in ('8530','30-286','8550')):
                specs += [Specification(component_type='CPU',property_name='Modello',text_value='Intel 80286',sources=[source]),Specification(component_type='CPU',property_name='Frequenza',numeric_value=10,unit='MHz',sources=[source])]
            c=Computer(manufacturer=maker,model_name=name,description='Testo curato.' if 'Model 30' in name else None,
                configurations=[Configuration(variant_name='Scheda tecnica',specifications=specs)],
                releases=[Release(market=market,price=1000+100*len(ids),currency='USD',sources=[source])],
                images=[ComputerImage(remote_url='https://example.org/'+name.split()[-1]+'.jpg',is_primary=True)])
            db.add(c);db.flush();ids[name]=c.id
        db.add(Computer(manufacturer=Manufacturer(name='Other'),model_name='PS/2 8580-071',description='Unchanged'))
        db.commit();cleanup(db,prepare(db))
    return ids

def test_package_names_and_evidence():
    data,_=research.load();assert len(data['records'])==14
    assert sum(len(c['specifications']) for r in data['records'] for c in r['configurations'])==143
    assert commercial_name('IBM PS/2 8580-071')=='PS/2 Model 80'
    assert commercial_name('IBM PS/2 8550-061')=='PS/2 Model 50 Z'
    assert commercial_name('IBM PS/2 8550-021')=='PS/2 Model 50'
    assert commercial_name('IBM PS/2 8530-021') is None
    assert commercial_name('IBM PS/2 8580-XYZ') is None
    assert computer_key('IBM','ThinkPad 350')==computer_key('IBM','PS/note 425')
    assert computer_key('IBM','ThinkPad 350C')!=computer_key('IBM','PS/note 425')
    assert computer_key('IBM','IBM PS/1 2011')==computer_key('IBM','PS/1 Model 2011')
    assert computer_key('IBM','IBM PS/2 Model N33 SX')==computer_key('IBM','PS/2 Note N33 SX')
    assert not any(s['component_type']=='RAM' for r in data['records'] if r['model_name']=='PS/note 182' for c in r['configurations'] for s in c['specifications'])

def test_apply_preserves_photos_prices_curated_text_and_old_reimports(client):
    ids=seed()
    with SessionLocal() as db:
        prices=sorted(db.scalars(select(Release.price).where(Release.price.is_not(None))));photos=sorted(db.scalars(select(ComputerImage.remote_url)))
        p=research.preview(db);assert len(p['rename'])==8 and len(p['consolidate'])==2 and len(p['new_models'])==8
        assert not db.scalar(select(ImportJob.id))
        report=research.apply(db)
        assert (report['created'],report['updated'],report['merged'],report['corrected'])==(8,6,2,24)
        assert sorted(db.scalars(select(Release.price).where(Release.price.is_not(None))))==prices
        assert sorted(db.scalars(select(ComputerImage.remote_url)))==photos
        c=db.get(Computer,ids['IBM PS/2 Model 30-286']);assert c.description=='Testo curato.' and len(c.configurations)==1
        c=db.scalar(select(Computer).where(Computer.model_name=='PS/2 Model 80'));cid=c.id
        assert len(c.configurations)==2
        assert sorted(s.numeric_value for cfg in c.configurations for s in cfg.specifications if s.property_name=='Frequenza')==[16,20]
        assert db.scalar(select(func.count()).select_from(Computer))==15
        assert not db.scalar(select(ImportClaim.id).where(ImportClaim.status=='verified'))
        assert research.apply(db)['already_applied']
        row={'manufacturer':'IBM','model_name':'IBM PS/2 8580-071','source':{'title':'New manual','url':'https://example.org/new'},'configurations':[{'variant_name':'Scheda tecnica','specifications':[{'component_type':'CPU','property_name':'Frequenza','numeric_value':16,'unit':'MHz'}]}]}
        job=stage(db,'manual','old.json','json',json.dumps([row]).encode());apply_job(db,job.id)
        assert job.status=='completed' and job.rows[0].computer_id==cid
        db.refresh(c);assert len(c.configurations)==2
    assert any(c['id']==cid for c in client.get('/api/computers?q=8580-071').json()['items'])

def test_transaction_rolls_back_names_and_merges(client,monkeypatch):
    seed()
    with SessionLocal() as db:
        names={c.id:c.model_name for c in db.scalars(select(Computer))};count=db.scalar(select(func.count()).select_from(Source))
        def fail(*args,**kw):raise RuntimeError('simulated failure after merges')
        monkeypatch.setattr(research,'stage',fail)
        with pytest.raises(RuntimeError):research.apply(db)
        db.commit()
        assert names=={c.id:c.model_name for c in db.scalars(select(Computer))}
        assert count==db.scalar(select(func.count()).select_from(Source))
        assert not db.scalar(select(ComputerAlias.id)) and not db.scalar(select(ImportJob.id))

def test_verified_values_are_protected(client):
    seed()
    with SessionLocal() as db:
        c=db.scalar(select(Computer).where(Computer.model_name=='IBM PS/2 8550-021'))
        s=next(s for cfg in c.configurations for s in cfg.specifications if s.component_type=='RAM' and s.property_name=='Capacità');sid=s.id
        db.execute(update(spec_source).where(spec_source.c.target_id==sid).values(verification_status='verified'));db.commit()
        report=research.apply(db);db.expire_all()
        assert report['protected'] and db.get(Specification,sid).numeric_value==1664
        assert db.scalar(select(ImportClaim.id).where(ImportClaim.target_id==sid,ImportClaim.status=='conflict'))

def test_existing_notebook_and_explicit_deletion_are_respected(client):
    with SessionLocal() as db:
        c=Computer(manufacturer=Manufacturer(name='IBM'),model_name='ThinkPad 350',description='Testo curato.');db.add(c);db.commit();cid=c.id
        r=research.apply(db);assert r['created']==7 and r['updated']==1
        assert db.get(Computer,cid).description=='Testo curato.'
        c=db.scalar(select(Computer).where(Computer.model_name=='PS/note 182'));db.delete(c);db.commit()
        assert research.apply(db)['already_applied']
        assert not db.scalar(select(Computer.id).where(Computer.model_name=='PS/note 182'))
