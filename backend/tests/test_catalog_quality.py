"""Configuration consolidation and conservative, sourced RAM recovery."""
import json
import pytest
from sqlalchemy import select, func
from app.main import SessionLocal
from app.models import Computer, Manufacturer, Configuration, Specification, Release, Market
from app.import_models import ComputerAlias, ImportClaim, CatalogReconciliation
from app.history_models import HistoryItem
from app.importing.engine import stage, apply_job
from app.importing.variant_names import variant_name
from app.importing.vocabulary import normalize_spec
from app.importing.bit1000 import html_record


def pet_records():
    return [{'manufacturer': 'Commodore', 'model_name': f'PET 2001-{letter}{ram}', 'external_id': f'{letter}{ram}',
        'description': f'Contesto storico sintetico per la variante {letter}{ram}.',
        'source': {'title': 'Synthetic product catalogue', 'url': 'https://example.org/pet-fixture'},
        'configurations': [{'variant_name': 'Documented configuration', 'specifications': [
            {'component_type': 'RAM', 'property_name': 'Capacità', 'numeric_value': ram, 'unit': 'KB'},
            {'component_type': 'Tastiera', 'property_name': 'Variante', 'text_value': letter}]}],
        'releases': [{'market': 'Stati Uniti', 'release_date': '1979', 'price': 100 + ram, 'currency': 'USD'}]}
        for letter in ('B', 'N') for ram in (8, 16, 32)]


def add_pets():
    records = pet_records()
    with SessionLocal() as db:
        job = stage(db, 'manual', 'pets.json', 'json', json.dumps(records).encode(), options={'upload': True})
        apply_job(db, job.id)
        return records, [row.computer_id for row in job.rows]


def consolidate(client):
    preview = client.get('/api/admin/catalog-quality/variants').json()
    assert len(preview['groups']) == 1, preview
    result = client.post('/api/admin/catalog-quality/variants/apply', json={
        'token': preview['token'], 'target_ids': [preview['groups'][0]['target_id']]})
    assert result.status_code == 200, result.text
    return preview['groups'][0]['target_id'], result.json()


def test_pet_variants_become_configurations_preserving_prices_sources_ids_and_replay(client):
    records, ids = add_pets()
    originals = [client.get(f'/api/computers/{cid}').json() for cid in ids]
    client.post('/api/admin/history')  # no generated descriptions to research
    target, result = consolidate(client)
    assert result['removed'] == 5
    data = client.get(f'/api/computers/{target}').json()
    assert data['model_name'] == 'PET 2001'
    assert len(data['configurations']) == 6 and len(data['releases']) == 6
    assert {cfg['id'] for cfg in data['configurations']} == {cfg['id'] for c in originals for cfg in c['configurations']}
    assert {r['id'] for r in data['releases']} == {r['id'] for c in originals for r in c['releases']}
    assert len(data['display_releases']) == 6 and len(data['display_configurations']) == 6
    assert {r['model_variant'] for r in data['display_releases']} == {r['model_name'] for r in records}
    assert all(cfg['model_variant'] in cfg['display_name'] and cfg.get('variant_description') for cfg in data['configurations'])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ComputerAlias)) == 6
        # Same source, names and external IDs after the merge must not recreate models.
        job = stage(db, 'manual', 'replay.json', 'json', json.dumps(records).encode(), options={'upload': True})
        apply_job(db, job.id)
        assert all(row.status == 'unchanged' for row in job.rows), [(r.status,r.error) for r in job.rows]
        assert not db.scalar(select(ImportClaim).where(ImportClaim.row_id.in_([r.id for r in job.rows]), ImportClaim.status == 'conflict'))
    after = client.get(f'/api/computers/{target}').json()
    assert after['configurations'] == data['configurations'] and after['releases'] == data['releases']
    assert client.get('/api/admin/catalog-quality/variants').json()['removed'] == 0


def test_new_source_import_follows_approved_alias_and_scopes_new_price(client):
    records, ids = add_pets(); target, _ = consolidate(client)
    incoming = {**records[4], 'source': {'title': 'New synthetic source', 'url': 'https://example.org/new-pet-fixture'},
                'external_id': 'new-record', 'releases': [{'market': 'Italia', 'price': 250, 'currency': 'EUR'}]}
    with SessionLocal() as db:
        job = stage(db, 'manual', 'new.json', 'json', json.dumps([incoming]).encode(), options={'upload': True})
        assert job.rows[0].computer_id == target
        apply_job(db, job.id)
    data = client.get(f'/api/computers/{target}').json()
    assert len(data['configurations']) == 6 and data['model_name'] == 'PET 2001'
    new_price = next(r for r in data['releases'] if r['market'] == 'Italia')
    assert new_price['model_variant'] == 'PET 2001-N16'


def test_stale_preview_and_selected_group_validation(client):
    _, ids = add_pets()
    p = client.get('/api/admin/catalog-quality/variants').json()
    with SessionLocal() as db: db.get(Computer, ids[1]).description = 'New manual text'; db.commit()
    assert client.post('/api/admin/catalog-quality/variants/apply', json={'token': p['token'], 'target_ids': [p['groups'][0]['target_id']]}).status_code == 409
    p = client.get('/api/admin/catalog-quality/variants').json()
    assert client.post('/api/admin/catalog-quality/variants/apply', json={'token': p['token'], 'target_ids': [99999]}).status_code == 422
    assert client.get('/api/computers').json()['total'] == 16


@pytest.mark.parametrize('name', ['Macintosh 128K', 'Macintosh 512K', 'HP 85B', 'Atari 800XL', 'IBM System/360 Model 50', 'System (revision 2)', 'System (16 KB ROM)', 'System (16 KB)'])
def test_meaningful_model_numbers_and_unknown_hardware_revisions_stay_distinct(name):
    assert variant_name('Apple', name) is None


def test_explicit_ram_and_firmware_and_known_product_revision_rules():
    assert variant_name('Maker', 'System (16 KB RAM)')['name'] == 'System'
    assert variant_name('Maker', 'System (RAM 32 MB)')['name'] == 'System'
    assert variant_name('Maker', 'System (BIOS 2.1)')['name'] == 'System'
    assert variant_name('Apple', 'Apple //c (rev 4)')['name'] == 'Apple IIc'
    assert variant_name('Apple', 'Apple IIc Plus') is None
    assert variant_name('Acorn', 'BBC Micro Model B+ 128K')['name'] == 'BBC Micro Model B+'


def test_hp85_ram_range_is_sourced_and_not_applied_to_hp85b_or_over_existing_values(client):
    with SessionLocal() as db:
        maker = Manufacturer(name='HP'); db.add(maker); db.flush()
        hp = Computer(model_name='HP 85', manufacturer=maker)
        other = Computer(model_name='HP 85B', manufacturer=maker)
        db.add_all([hp,other]); db.commit(); cid, other_id = hp.id, other.id
    p = client.get('/api/admin/catalog-quality/ram').json()
    assert [r['computer_id'] for r in p['proposals']] == [cid]
    assert p['proposals'][0]['value'] == '16 - 32Kb'
    result = client.post('/api/admin/catalog-quality/ram/apply', json={'token':p['token']})
    assert result.status_code == 200, result.text
    data = client.get(f'/api/computers/{cid}').json()
    ram = next(s for cfg in data['configurations'] for s in cfg['specifications'] if s['component_type']=='RAM')
    assert ram['text_value'] == '16 - 32Kb' and ram['numeric_value'] is None
    assert ram['sources'][0]['url'].endswith('id=118')
    assert client.get(f'/api/computers/{other_id}').json()['configurations'] == []
    assert client.get('/api/admin/catalog-quality/ram').json()['proposals'] == []
    with SessionLocal() as db:
        assert not db.scalar(select(ImportClaim).where(ImportClaim.status == 'verified'))


def test_ram_text_normalization_does_not_guess_ranges_bits_or_maximum():
    values = lambda text: normalize_spec({'component_type':'RAM','property_name':'Capacità riportata','text_value':text})
    assert values('64KB')['numeric_value'] == 64 and values('64KB')['unit'] == 'KB'
    for text in ('16 - 32Kb', '2Mb - 16Mb', '64Kb', 'fino a 64 MB', '8 / 16 KB'):
        assert values(text).get('numeric_value') is None and values(text)['text_value'] == text


def test_1000bit_english_sheet_preserves_ram_and_rejects_discordant_language_fields():
    body = '<div id="tabDatiTecnici"><table>' + ''.join(f'<tr><td class="w3-indigo">{key}</td><td>{value}</td></tr>' for key,value in [('Name','HP 85'),('Manufacturer','Hewlett-Packard (USA)'),('RAM','16 - 32Kb')]) + '</table></div>'
    result = html_record(body.encode(), source_url='https://www.1000bit.it/scheda.asp?id=118')
    assert result['model_name'] == 'HP 85'
    assert result['configurations'][0]['specifications'][0]['text_value'] == '16 - 32Kb'
    bad = body.replace('</table>', '<tr><td class="w3-indigo">Nome</td><td>Unrelated</td></tr></table>')
    with pytest.raises(ValueError): html_record(bad.encode(), source_url='https://www.1000bit.it/scheda.asp?id=118')


def test_aliases_remain_searchable_in_catalog_suggestions_and_assistant(client):
    from app.assistant_context import retrieve
    from app.main import EAGER, full
    add_pets(); target, _ = consolidate(client)
    assert client.get('/api/computers', params={'q':'B16'}).json()['items'][0]['id'] == target
    assert client.get('/api/computers/suggestions', params={'q':'N32'}).json()['items'][0]['id'] == target
    with SessionLocal() as db:
        item = next(c for c in retrieve(db, 'RAM N32', EAGER, full)['computers'] if c['id'] == target)
        assert any(claim['model_variant'] for claim in item['import_assertions'])
        assert item['configurations'][0]['model_variant'] == 'PET 2001-N32'
        assert item['releases'][0]['model_variant'] == 'PET 2001-N32'


def test_history_in_flight_does_not_overwrite_the_consolidated_description(client, monkeypatch):
    import asyncio
    from app import history_sources
    from app.history_models import HistoryJob
    _, ids = add_pets()
    with SessionLocal() as db:
        for cid in ids:
            c = db.get(Computer, cid); c.description = f'{c.model_name} è un calcolatore di Commodore.'
        db.commit()
    job = client.post('/api/admin/history').json(); jid = job['id']
    async def research(model, maker):
        await asyncio.to_thread(consolidate, client)
        return {'status':'no_match'}, {'query':{'pages':[]}}
    monkeypatch.setattr(history_sources, 'research', research)
    result = client.post(f'/api/admin/history/{jid}/step')
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'completed' and result.json()['counts']['changed'] == 6
    data = client.get('/api/computers', params={'q':'PET 2001'}).json()['items']
    assert len(data) == 1 and 'Chuck Peddle' in data[0]['description']


def test_normalized_regional_aliases_keep_every_configuration_and_old_description(client):
    with SessionLocal() as db:
        maker = db.scalar(select(Manufacturer).where(Manufacturer.name == 'Commodore'))
        ids = []
        for country in ('France', 'Germany'):
            c = Computer(manufacturer=maker, model_name=f'PET 2001-B8 ({country})', description='Manual history '+country)
            c.configurations = [Configuration(variant_name='Configuration '+country, specifications=[Specification(component_type='RAM',property_name='Capacità',numeric_value=8,unit='KB')])]
            db.add(c);db.flush();ids.append(c.id)
        db.commit()
    target, _ = consolidate(client)
    data = client.get(f'/api/computers/{target}').json()
    assert {c['variant_description'] for c in data['configurations']} == {'Manual history France','Manual history Germany'}
    assert {c['model_variant'] for c in data['configurations']} == {'PET 2001-B8'}
    with SessionLocal() as db: assert len(db.scalar(select(ComputerAlias)).original['configurations']) == 2


def test_hp_ram_recovery_survives_unrelated_description_edit_and_keeps_existing_ram(client):
    with SessionLocal() as db:
        m=Manufacturer(name='HP');c=Computer(manufacturer=m,model_name='HP 85');db.add(c);db.commit();cid=c.id
    plan=client.get('/api/admin/catalog-quality/ram').json()
    assert len(plan['proposals']) == 1
    with SessionLocal() as db:db.get(Computer,cid).description='Manual historical text';db.commit()
    result=client.post('/api/admin/catalog-quality/ram/apply',json={'token':plan['token']})
    assert result.status_code==200,result.text
    assert client.get(f'/api/computers/{cid}').json()['description']=='Manual historical text'
    assert client.post('/api/admin/catalog-quality/ram/apply',json={'token':plan['token']}).status_code==409


def test_ram_can_be_recovered_from_an_applied_original_not_an_unapproved_upload(client):
    record={'manufacturer':'Synthetic','model_name':'Memory recover','source':{'title':'Original technical reference','url':'https://example.org/ram'},'configurations':[{'variant_name':'Base','specifications':[{'component_type':'RAM','property_name':'Capacità','numeric_value':64,'unit':'KB'}]}]}
    with SessionLocal() as db:
        job=stage(db,'manual','ram.json','json',json.dumps([record]).encode(),options={'upload':True});apply_job(db,job.id)
        cid=job.rows[0].computer_id;c=db.get(Computer,cid);db.delete(c.configurations[0].specifications[0]);db.commit()
    plan=client.get('/api/admin/catalog-quality/ram').json()
    assert any(p['computer_id']==cid for p in plan['proposals'])
    assert client.post('/api/admin/catalog-quality/ram/apply',json={'token':plan['token']}).status_code==200
    assert client.get(f'/api/computers/{cid}').json()['configurations'][0]['specifications'][0]['numeric_value']==64


def test_release_summaries_do_not_cross_configuration_scope():
    from app.release_display import release_summaries
    rows=[{'id':1,'model_variant':'PET 2001-B8','market':'Non specificato dalla fonte','release_date':'1979','discontinuation_date':None,'price':None,'currency':None,'price_type':None,'sources':[]},
          {'id':2,'model_variant':'PET 2001-B32','market':'Stati Uniti','release_date':None,'discontinuation_date':None,'price':200,'currency':'USD','price_type':'prezzo riportato','sources':[]}]
    assert len(release_summaries(rows))==2 and next(r for r in release_summaries(rows) if r['price'])['release_date'] is None
    rows.append({**rows[1], 'id':3, 'model_variant':'PET 2001-B8', 'market':'Italia', 'currency':'EUR'})
    summaries=release_summaries(rows)
    assert len(summaries)==2
    assert next(r for r in summaries if r['model_variant']=='PET 2001-B8')['release_date']=='1979'
    assert next(r for r in summaries if r['model_variant']=='PET 2001-B32')['release_date'] is None


def test_firmware_family_keeps_manual_text_of_existing_unqualified_model(client):
    with SessionLocal() as db:
        maker=db.scalar(select(Manufacturer).where(Manufacturer.name=='Apple'))
        base=Computer(manufacturer=maker,model_name='Apple //c',description='A manually curated family history.')
        rev=Computer(manufacturer=maker,model_name='Apple //c (rev 4)',description='A manual revision history.')
        for c in (base,rev):c.configurations=[Configuration(variant_name='Base')]
        db.add_all([base,rev]);db.commit();cid=base.id
    target,_=consolidate(client)
    assert target==cid
    data=client.get(f'/api/computers/{target}').json()
    assert data['model_name']=='Apple IIc' and data['description']=='A manually curated family history.'
    assert any(c.get('variant_description')=='A manual revision history.' for c in data['configurations'])


def test_additive_alias_migration_repeats_and_reset_clears_live_aliases(client):
    from migrations.historical_imports import migrate
    from app.main import engine
    add_pets();target,_=consolidate(client)
    migrate(engine);migrate(engine)
    preview=client.get('/api/admin/archive/preview').json()
    response=client.post('/api/admin/archive/reset',json={'token':preview['token'],'confirmation':'SVUOTA ARCHIVIO','backup_confirmed':True,'note':'Synthetic quality reset test'})
    assert response.status_code==200,response.text
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(ComputerAlias))==0


def test_running_1000bit_import_binds_the_original_variant_after_consolidation(client):
    from app.importing.bulk1000bit import BulkJob, BulkTarget, BulkPage, import_page
    _,ids=add_pets()
    with SessionLocal() as db:
        job=BulkJob(active_key='1000bit');db.add(job);db.flush();jid=job.id
        for cid in ids:
            c=db.get(Computer,cid);db.add(BulkTarget(job_id=jid,original_id=cid,computer_id=cid,model_name=c.model_name,manufacturer=c.manufacturer.name))
        db.commit()
    target,_=consolidate(client)
    fields=[('Name','PET 2001-N16'),('Manufacturer','Commodore'),('RAM','16KB')]
    raw=('<div id="tabDatiTecnici"><table>'+''.join(f'<tr><td class="w3-indigo">{k}</td><td>{v}</td></tr>' for k,v in fields)+'</table></div>').encode()
    with SessionLocal() as db:
        job=db.get(BulkJob,jid);page=BulkPage(job_id=jid,url='https://www.1000bit.it/scheda.asp?id=900116');db.add(page);db.flush()
        import_page(db,job,page,raw,'text/html');db.commit()
        assert page.status=='updated'
        targets=db.scalars(select(BulkTarget).where(BulkTarget.job_id==jid)).all()
        assert next(t for t in targets if t.original_id==ids[4]).status=='updated'
        assert next(t for t in targets if t.original_id==ids[0]).status=='pending'
    data=client.get(f'/api/computers/{target}').json()
    documented=[cfg for cfg in data['configurations'] if 'Scheda tecnica' in cfg['variant_name']]
    assert len(documented)==1 and documented[0]['model_variant']=='PET 2001-N16'
    assert not data['facts']  # no additional generated description in the notes
