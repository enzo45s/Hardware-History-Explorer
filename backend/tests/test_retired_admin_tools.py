import pytest
from sqlalchemy import MetaData, Table, Column, Integer, String, JSON, ForeignKey, inspect, select, func
from app.main import engine, SessionLocal
from app.models import Base, Computer, Source, Specification
from app.import_models import ImportJob, CatalogReconciliation
from migrations.retire_admin_tools import migrate


def legacy_tables():
    meta = MetaData()
    jobs = Table('history_research_jobs', meta, Column('id', Integer, primary_key=True))
    items = Table('history_research_items', meta, Column('id', Integer, primary_key=True),
                  Column('job_id', ForeignKey(jobs.c.id)), Column('computer_id', Integer),
                  Column('import_job_id', Integer), Column('status', String(20)), Column('result', JSON))
    meta.create_all(engine)
    return jobs, items


@pytest.mark.parametrize('path', ['/api/admin/history', '/api/admin/history/1/step',
    '/api/admin/catalog-quality/ram', '/api/admin/catalog-quality/variants/apply',
    '/api/admin/catalog-quality/units', '/api/admin/catalog-quality/physical/apply',
    '/api/admin/catalog-quality/consolidated/rebuild'])
def test_removed_admin_endpoints_have_no_routes_or_tables(client, path):
    assert client.get(path).status_code == 404
    assert client.post(path, json={}).status_code == 404
    assert not any(p.startswith(('/api/admin/history', '/api/admin/catalog-quality')) for p in client.get('/openapi.json').json()['paths'])
    assert not {'history_research_jobs', 'history_research_items'} & Base.metadata.tables.keys()
    assert not {'history_research_jobs', 'history_research_items'} & set(inspect(engine).get_table_names())


def test_legacy_queue_is_dropped_atomically_and_attribution_survives(client):
    jobs, items = legacy_tables()
    try:
        with SessionLocal() as db:
            computer = db.get(Computer, 1)
            text = 'Testo storico sintetico conservato dopo il ritiro.'
            computer.description = text
            source = Source(title='Synthetic Italian article', url='https://it.wikipedia.org/wiki/Synthetic')
            computer.sources.append(source)
            job = ImportJob(provider='italian_history', filename='synthetic.json', format='json', checksum='0'*64,
                            raw_payload='{"synthetic_original":true}', status='completed', request_options={'managed_history': True, 'existing_only': True})
            db.add(job); db.flush(); jid = job.id
            result = {'description': text, 'title': source.title, 'url': source.url,
                      'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/', 'method': 'estratto italiano sintetico'}
            db.commit()
        with engine.begin() as conn:
            conn.execute(jobs.insert().values(id=1))
            conn.execute(items.insert().values(id=1, job_id=1, computer_id=1, import_job_id=jid, status='updated', result=result))
        report = migrate(engine)
        assert report['attributions'] == 1 and len(report['removed_tables']) == 2
        assert migrate(engine) == {'removed_tables': [], 'attributions': 0}
        assert not {'history_research_jobs', 'history_research_items'} & set(inspect(engine).get_table_names())
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(CatalogReconciliation).where(CatalogReconciliation.entity=='admin_retirement')) == 1
            job = db.get(ImportJob, jid)
            assert job.raw_payload == '{"synthetic_original":true}' and job.status == 'completed'
            assert job.request_options == {'existing_only': True, 'retired_feature': 'description_research'}
        data = client.get('/api/computers/1').json()
        assert data['description'] == text
        assert data['description_attribution'] == {k: result[k] for k in ('title', 'url', 'license_url', 'method')}
        assert any(s['url'] == result['url'] for s in data['sources'])
        assert client.post(f'/api/admin/imports/{jid}/retry').status_code == 410
        with SessionLocal() as db:
            db.get(Computer, 1).description = 'Testo successivamente curato a mano.'; db.commit()
        assert client.get('/api/computers/1').json()['description_attribution'] is None
    finally:
        items.drop(engine, checkfirst=True); jobs.drop(engine, checkfirst=True)


def test_incomplete_attribution_rolls_back_table_retirement(client):
    jobs, items = legacy_tables()
    try:
        with engine.begin() as conn:
            conn.execute(jobs.insert().values(id=1))
            conn.execute(items.insert().values(id=1, job_id=1, computer_id=1, status='updated', result={'description':'Synthetic missing attribution'}))
        with pytest.raises(ValueError, match='Attribuzione'):
            migrate(engine)
        assert {'history_research_jobs', 'history_research_items'} <= set(inspect(engine).get_table_names())
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(CatalogReconciliation).where(CatalogReconciliation.entity=='admin_retirement')) == 0
    finally:
        items.drop(engine, checkfirst=True); jobs.drop(engine, checkfirst=True)


def test_drop_failure_rolls_back_both_tables_and_audit(client):
    from sqlalchemy import event
    jobs, items = legacy_tables()
    def fail_second_drop(conn, cursor, statement, parameters, context, executemany):
        if statement.strip().lower().startswith('drop table history_research_jobs'):
            raise RuntimeError('Synthetic DDL failure')
    try:
        with engine.begin() as conn:
            conn.execute(jobs.insert().values(id=1))
            conn.execute(items.insert().values(id=1, job_id=1, computer_id=1, status='pending', result={}))
        event.listen(engine, 'before_cursor_execute', fail_second_drop)
        try:
            with pytest.raises(RuntimeError, match='Synthetic DDL failure'):
                migrate(engine)
        finally:
            event.remove(engine, 'before_cursor_execute', fail_second_drop)
        assert {'history_research_jobs', 'history_research_items'} <= set(inspect(engine).get_table_names())
        with engine.connect() as conn:
            assert conn.scalar(select(func.count()).select_from(items)) == 1
            assert conn.scalar(select(func.count()).select_from(CatalogReconciliation).where(CatalogReconciliation.entity=='admin_retirement')) == 0
    finally:
        items.drop(engine, checkfirst=True); jobs.drop(engine, checkfirst=True)


@pytest.mark.parametrize('maker,model,other_maker,other_model', [
    ('Sun Microsystems', 'Sun Ultra 1', 'Sun', 'Ultra 1'),
    ('NeXT Software Inc', 'NeXTcube', 'NeXT', 'NeXTcube'),
    ('Apple Computer', 'Macintosh PowerBook 180', 'Apple', 'PowerBook 180'),
])
def test_shared_catalog_identity_remains_available_without_network_research(maker, model, other_maker, other_model):
    from app.catalog_identity import model_key
    assert model_key(maker, model) == model_key(other_maker, other_model)


def test_old_unit_audit_still_protects_withdrawn_capacity_on_reimport(client):
    from app.importing.reviewed_units import reviewed_import_target
    from app.importing.vocabulary import spec_values
    with SessionLocal() as db:
        cfg=db.get(Computer,1).configurations[0]
        note=Specification(component_type='RAM',property_name='Annotazione sulla memoria',text_value='Quantità non documentata.')
        cfg.specifications.append(note);db.flush()
        before={'component_type':'RAM','component_name':None,'property_name':'Capacità riportata',
                'numeric_value':64,'text_value':None,'unit':'kB'}
        citation={'url':'https://example.org/previously-reviewed'}
        db.add(CatalogReconciliation(entity='unit_review',source_id=0,target_id=0,note='Decisione sintetica già applicata.',
            snapshot={'changes':[{'id':note.id,'action':'annotate','original_source_url':citation['url'],'before':before,'after':spec_values(note)}]}))
        db.commit()
        assert reviewed_import_target(db,cfg.specifications,before,citation) is note
        assert reviewed_import_target(db,cfg.specifications,before,{'url':'https://example.org/another-source'}) is None
