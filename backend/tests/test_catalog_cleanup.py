from copy import deepcopy
from datetime import date
import pytest
from sqlalchemy import select,func,update
from app.main import SessionLocal,engine,full
from app.models import (Computer,Configuration,Specification,Source,Release,Market,
    CatalogSnapshot,CatalogMetric,spec_source)
from app.import_models import CatalogReconciliation,ImportJob,ImportClaim
from app.catalog_cleanup import prepare,apply,physical_mode
from app.catalog_store import refresh_pending,status
from app.importing.engine import stage,apply_job


def test_canonical_import_enriches_a_current_sheet_reserved_by_old_aliases(client):
    from app.import_models import ComputerAlias
    from app.importing.identity import provider_computer_key
    with SessionLocal() as db:
        c=db.get(Computer,1);c.model_name='Current canonical model'
        c.configurations=[Configuration(variant_name='NTSC',specifications=[
            Specification(component_type='CPU',property_name='Modello',text_value='6502')])]
        db.flush()
        maker,name=provider_computer_key('historical_prices',c.manufacturer.name,'Former model')
        db.add(ComputerAlias(manufacturer_key=maker,model_key=name,original_name='Former model',computer_id=c.id,
            original={'configurations':[c.configurations[0].id],'configuration_names':{str(c.configurations[0].id):'NTSC'}}))
        db.commit();apply(db,prepare(db));db.refresh(c)
        assert len(c.configurations)==1 and c.configurations[0].variant_name=='Scheda tecnica'
        record={'manufacturer':c.manufacturer.name,'model_name':c.model_name,
            'source':{'title':'New technical manual','url':'https://example.org/canonical-technical'},
            'configurations':[{'variant_name':'Scheda tecnica','specifications':[
                {'component_type':'CPU','property_name':'Architettura','text_value':'8 bit'}]}]}
        import json
        job=stage(db,'manual','canonical.json','json',json.dumps([record]).encode())
        apply_job(db,job.id)
        assert job.status=='completed', [(r.status,r.error) for r in job.rows]
        db.refresh(c)
        assert len(c.configurations)==1
        assert any(s.property_name=='Architettura' and s.text_value=='8 bit' for s in c.configurations[0].specifications)


def fixture(db):
    c=db.get(Computer,1);c.model_name='Synthetic clean computer'
    c.configurations.clear();c.releases.clear();db.flush()
    source=Source(title='Technical manual',url='https://example.org/clean')
    c.configurations=[Configuration(variant_name=name,specifications=[
        Specification(component_type='CPU',component_name='maincpu',property_name='Modello emulato (MAME)',text_value='6502',sources=[source]),
        Specification(component_type='RAM',property_name='Capacità predefinita (MAME)',numeric_value=16,unit='KiB',sources=[source]),
        Specification(component_type='RAM',property_name='Opzioni RAM emulatore (MAME)',text_value='16 KiB / 32 KiB',sources=[source]),
        Specification(component_type='Video',property_name='Frequenza video emulata (MAME)',numeric_value=hz,unit='Hz',sources=[source])]) for name,hz in [('NTSC',60),('PAL',50)]]
    c.configurations.append(Configuration(variant_name='Scheda tecnica',specifications=[
        Specification(component_type='RAM',property_name='Capacità riportata',numeric_value=8,unit='KiB',sources=[source])]))
    c.releases=[Release(market=Market(name='Non specificato dalla fonte'),release_date=date(1982,1,1),release_precision='year',sources=[source]),
        Release(market=Market(name='Stati Uniti'),price=3298,currency='USD',price_type='prezzo riportato',sources=[source])]
    db.commit();return c.id


def test_physical_tables_are_clean_not_only_display_with_archived_originals(client):
    with SessionLocal() as db:
        cid=fixture(db)
        before=prepare(db)
        raw=next(r for r in before['changes'] if r['computer_id']==cid)['original']
        result=apply(db,before)
        assert result['audit_id'] and physical_mode(db)
    with SessionLocal() as db:
        c=db.get(Computer,cid)
        assert len(c.configurations)==1 and len(c.releases)==1
        cfg=c.configurations[0]
        assert cfg.variant_name=='Scheda tecnica'
        assert [s.property_name for s in cfg.specifications if s.component_type=='RAM']==['Capacità','Opzioni di memoria']
        ram=next(s for s in cfg.specifications if s.property_name=='Capacità')
        assert ram.numeric_value==8 and ram.unit=='KiB'
        assert ram.catalog_details['resolution_state']=='reported'
        assert '16 KB' in ' '.join(ram.catalog_details['notes'])
        assert c.releases[0].price==3298 and c.releases[0].release_date.year==1982
        assert c.releases[0].market.name=='Stati Uniti'
        assert db.scalar(select(func.count()).select_from(CatalogSnapshot))==0
        assert db.scalar(select(func.count()).select_from(CatalogMetric))==0
        audit=db.get(CatalogReconciliation,result['audit_id'])
        archived=next(r for r in audit.snapshot['computers'] if r['computer_id']==cid)
        assert archived['original']==raw
        second=prepare(db)
        assert second['summary']['affected_computers']==0
        assert apply(db,second)['audit_id'] is None
    data=client.get('/api/computers/1').json()
    assert data['catalog_data']['storage']=='primary_tables'
    assert len(data['configurations'])==len(data['display_configurations'])==1
    view=next(s for s in data['display_configurations'][0]['specifications'] if s.get('catalog_metric')=='ram.capacity')
    assert view['normalized']['text_value']=='8 KB'


def test_substantial_memory_variants_and_missing_values_are_preserved(client):
    with SessionLocal() as db:
        c=db.get(Computer,1);c.configurations.clear();db.flush()
        c.configurations=[Configuration(variant_name=name,specifications=[Specification(component_type='RAM',property_name='Capacità',numeric_value=n,unit='KiB')]) for name,n in [('16 KB',16),('48 KB',48)]]
        db.commit();apply(db,prepare(db))
    with SessionLocal() as db:
        c=db.get(Computer,1)
        assert len(c.configurations)==2
        assert sorted(s.numeric_value for cfg in c.configurations for s in cfg.specifications)==[16,48]
        assert prepare(db)['summary']['affected_computers']==0


def test_stale_plan_rejected_without_cleanup(client):
    with SessionLocal() as db:
        cid=fixture(db);plan=prepare(db)
        db.get(Computer,cid).configurations[0].specifications[0].text_value='Other CPU';db.commit()
        with pytest.raises(ValueError,match='cambiato'):apply(db,plan)
        db.rollback();assert not physical_mode(db)


def test_incremental_changes_clean_primary_tables_without_recreating_cache(client):
    with SessionLocal() as db:
        cid=fixture(db);apply(db,prepare(db))
        c=db.get(Computer,cid)
        c.configurations.append(Configuration(variant_name='Scheda tecnica aggiuntiva',specifications=[
            Specification(component_type='Porte',property_name='Nome',text_value='Seriale')]))
        db.commit();assert refresh_pending(db)['processed']==1
        assert status(db)['storage']=='primary_tables'
        assert db.scalar(select(func.count()).select_from(CatalogSnapshot))==0


def test_reimport_original_profiles_does_not_recreate_retired_records(client):
    import json
    with SessionLocal() as db:
        cid=fixture(db);c=db.get(Computer,cid)
        manufacturer=c.manufacturer.name
        apply(db,prepare(db))
        before=(db.scalar(select(func.count()).select_from(Configuration)),db.scalar(select(func.count()).select_from(Specification)),db.scalar(select(func.count()).select_from(Release)))
        record={'manufacturer':manufacturer,'model_name':c.model_name,'source':{'title':'Technical manual','url':'https://example.org/clean'},
            'configurations':[{'variant_name':name,'specifications':[{'component_type':'CPU','component_name':'maincpu','property_name':'Modello emulato (MAME)','text_value':'6502'},
                {'component_type':'RAM','property_name':'Capacità predefinita (MAME)','numeric_value':16,'unit':'KiB'},
                {'component_type':'Video','property_name':'Frequenza video emulata (MAME)','numeric_value':hz,'unit':'Hz'}]} for name,hz in [('NTSC',60),('PAL',50)]],
            'releases':[{'market':'Non specificato dalla fonte','release_date':'1982'}, {'market':'Stati Uniti','price':3298,'currency':'USD','price_type':'prezzo riportato'}]}
        raw=json.dumps([record]).encode()
        job=stage(db,'manual','original.json','json',raw)
        apply_job(db,job.id);assert job.status=='completed'
        refresh_pending(db)
        after=(db.scalar(select(func.count()).select_from(Configuration)),db.scalar(select(func.count()).select_from(Specification)),db.scalar(select(func.count()).select_from(Release)))
        assert before==after
        assert next(s for cfg in db.get(Computer,cid).configurations for s in cfg.specifications if s.component_type=='RAM' and s.property_name=='Capacità').numeric_value==8


def test_accepting_archived_reference_does_not_overwrite_reported_ram(client):
    import json
    from app.importing.engine import review_claim
    with SessionLocal() as db:
        cid=fixture(db);c=db.get(Computer,cid);maker=c.manufacturer.name
        apply(db,prepare(db))
        record={'manufacturer':maker,'model_name':c.model_name,'source':{'title':'Technical manual','url':'https://example.org/clean'},
            'configurations':[{'variant_name':'NTSC','specifications':[{'component_type':'RAM','property_name':'Capacità predefinita (MAME)','numeric_value':16,'unit':'KiB'}]}]}
        job=stage(db,'manual','replay.json','json',json.dumps([record]).encode());apply_job(db,job.id)
        claim=db.scalar(select(ImportClaim).where(ImportClaim.row_id==job.rows[0].id,ImportClaim.field=='quantity'))
        assert claim.status=='pending'
        review_claim(db,claim,'accept','Controllata la dichiarazione originale di riferimento.')
        ram=db.get(Specification,claim.target_id)
        assert ram.numeric_value==8 and ram.catalog_details['resolution_state']=='reported'


def test_new_reported_ram_supersedes_a_reference_without_discarding_it(client):
    import json
    with SessionLocal() as db:
        c=db.get(Computer,1);c.configurations.clear();db.flush()
        c.configurations=[Configuration(variant_name='Base',specifications=[Specification(component_type='RAM',property_name='Capacità di riferimento',numeric_value=16,unit='KiB')])]
        db.commit();apply(db,prepare(db));maker=c.manufacturer.name
        record={'manufacturer':maker,'model_name':c.model_name,'source':{'title':'Nuovo manuale','url':'https://example.org/new'},
            'configurations':[{'variant_name':'Base','specifications':[{'component_type':'RAM','property_name':'Capacità riportata','numeric_value':8,'unit':'KiB'}]}]}
        job=stage(db,'manual','new.json','json',json.dumps([record]).encode());apply_job(db,job.id);refresh_pending(db)
        c=db.get(Computer,1);ram=next(s for cfg in c.configurations for s in cfg.specifications if s.component_type=='RAM')
        assert ram.numeric_value==8 and ram.catalog_details['resolution_state']=='reported'
        assert '16 KB' in ' '.join(ram.catalog_details['notes'])
        assert sum(s.component_type=='RAM' for cfg in c.configurations for s in cfg.specifications)==1


def test_physical_cleanup_failure_rolls_back_all_rows_and_audit(client,monkeypatch):
    import app.catalog_cleanup as module
    with SessionLocal() as db:
        fixture(db);plan=prepare(db);original=deepcopy(plan['changes'][0]['original'])
        write=module.write_computer
        def fail(db,row):
            write(db,row);raise RuntimeError('interruzione')
        monkeypatch.setattr(module,'write_computer',fail)
        with pytest.raises(RuntimeError):apply(db,plan)
        db.rollback();assert not physical_mode(db)
        assert prepare(db)['changes'][0]['original']==original


def test_review_old_market_does_not_restore_unknown_market_on_merged_offer(client):
    import json
    from app.importing.engine import review_claim
    with SessionLocal() as db:
        cid=fixture(db);c=db.get(Computer,cid);maker=c.manufacturer.name;apply(db,prepare(db))
        record={'manufacturer':maker,'model_name':c.model_name,'source':{'title':'Technical manual','url':'https://example.org/clean'},
            'releases':[{'market':'Non specificato dalla fonte','release_date':'1982'}]}
        job=stage(db,'manual','old-date.json','json',json.dumps([record]).encode());apply_job(db,job.id)
        claims=db.scalars(select(ImportClaim).where(ImportClaim.row_id==job.rows[0].id,ImportClaim.entity=='Release')).all()
        assert claims and all(c.status=='pending' for c in claims)
        for claim in claims:review_claim(db,claim,'accept','Confermata la dichiarazione storica della fonte.')
        release=db.get(Computer,cid).releases[0]
        assert release.market.name=='Stati Uniti' and release.price==3298




def test_additive_columns_migrate_existing_rows_and_foreign_keys(client):
    from app.catalog_schema import ensure_schema
    from sqlalchemy import text,inspect
    with engine.begin() as conn:
        before=conn.execute(text('SELECT id,property_name,numeric_value,text_value,unit FROM specifications ORDER BY id')).all()
        for table in ('configurations','specifications','releases'):
            conn.exec_driver_sql('ALTER TABLE '+table+' DROP COLUMN catalog_details')
    ensure_schema(engine);ensure_schema(engine)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT id,property_name,numeric_value,text_value,unit FROM specifications ORDER BY id')).all()==before
        for table in ('configurations','specifications','releases'):
            assert 'catalog_details' in {r['name'] for r in inspect(conn).get_columns(table)}
        if engine.dialect.name=='sqlite':assert conn.exec_driver_sql('PRAGMA foreign_key_check').all()==[]


def test_sqlite_cli_engine_cascades_retired_source_links(tmp_path):
    from sqlalchemy import create_engine,delete,text
    from app.models import Base,Manufacturer
    from app.catalog_schema import ensure_schema
    other=create_engine('sqlite:///'+str(tmp_path/'cli.db'))
    Base.metadata.create_all(other);ensure_schema(other)
    with SessionLocal(bind=other) as db:
        c=Computer(model_name='CLI fixture',manufacturer=Manufacturer(name='CLI maker'))
        s=Specification(component_type='RAM',property_name='Capacità',numeric_value=16,unit='KiB',sources=[Source(title='Manuale')])
        c.configurations=[Configuration(variant_name='Base',specifications=[s])]
        db.add(c);db.commit();sid=s.id
        db.execute(delete(Specification).where(Specification.id==sid));db.commit()
        assert db.scalar(select(func.count()).select_from(spec_source))==0
        assert db.execute(text('PRAGMA foreign_key_check')).all()==[]
    other.dispose()


def test_current_rule_cleanup_survives_schema_restart_without_changing_rows(client):
    from app.models import Base
    from app.catalog_schema import ensure_schema
    def snapshot():
        with engine.connect() as conn:
            return {table.name:sorted(repr(r) for r in conn.execute(select(table))) for table in Base.metadata.sorted_tables}
    with SessionLocal() as db:
        fixture(db);apply(db,prepare(db))
    before=snapshot()
    ensure_schema(engine)
    assert snapshot()==before


def test_release_only_normalization_does_not_rewrite_unchanged_technical_tables(client):
    from sqlalchemy import event
    statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement.lower())
    with SessionLocal() as db:
        cid=fixture(db);apply(db,prepare(db));c=db.get(Computer,cid)
        c.releases.append(Release(market=Market(name='Unknown'),release_date=date(1982,1,1),release_precision='year'))
        db.commit()
        event.listen(engine,'before_cursor_execute',capture)
        try:assert refresh_pending(db)['updated']==1
        finally:event.remove(engine,'before_cursor_execute',capture)
        assert len(db.get(Computer,cid).releases)==1
    for statement in statements:
        assert not statement.startswith(('update configurations ','update specifications ','delete from specification_sources','insert into specification_sources'))


def test_unquantified_claim_stays_visible_even_with_a_reference_capacity(client):
    import json
    with SessionLocal() as db:
        c=db.get(Computer,1);c.configurations.clear();db.flush()
        note='Capacità non quantificata nella fonte originale.'
        c.configurations=[Configuration(variant_name='Base',specifications=[
            Specification(component_type='RAM',property_name='Capacità di riferimento',numeric_value=16,unit='KiB'),
            Specification(component_type='RAM',property_name='Annotazione sulla memoria',text_value=note)])]
        db.commit();apply(db,prepare(db))
        retained=[{'text':s.text_value,'details':s.catalog_details} for cfg in db.get(Computer,1).configurations for s in cfg.specifications]
        assert note in json.dumps(retained,ensure_ascii=False)
