import json
import pytest
from sqlalchemy import select
from app.main import SessionLocal
from app.models import Computer,Manufacturer,ComputerImage,Configuration,Specification
from app.photo_jobs import PhotoItem
from app.importing.identity import computer_key
from app.importing.regional_names import regional_name
from app.importing.normalize import Record
from app.importing.enrichment import bundle


@pytest.mark.parametrize('name,expected', [('Apple //c (rev 4, France)','Apple //c (rev 4)'),
    ('Apple //c (UniDisk 3.5, Germany)','Apple //c (UniDisk 3.5)'),
    ('Commodore 128 (Sweden/Finland)','Commodore 128'), ('System (16 KB, Germany)','System (16 KB)'),
    ('System (MSX2, USSR)','System (MSX2)'), ('Macintosh SE (FDHD)','Macintosh SE (FDHD)'),
    ('IBM System/360 Model 50','IBM System/360 Model 50'),('System (revision 2)','System (revision 2)')])
def test_regional_qualifiers_only(name,expected):assert regional_name(name)==expected


def test_identity_keeps_revisions_and_hardware_distinct():
    assert computer_key('Apple','Apple //c (rev 4, France)')==computer_key('Apple','Apple //c (rev 4, Germany)')
    assert computer_key('Apple','Apple //c')!=computer_key('Apple','Apple //c (rev 4)')
    assert computer_key('Apple','Macintosh SE')!=computer_key('Apple','Macintosh SE (FDHD)')
    assert computer_key('Other maker','System (France)')!=computer_key('Apple','System (Germany)')


def regional_pair():
    with SessionLocal() as db:
        maker=db.scalar(select(Manufacturer).where(Manufacturer.name=='Apple'))
        base=Computer(manufacturer=maker,model_name='Synthetic system (rev 4)',description='Keep manual text')
        other=Computer(manufacturer=maker,model_name='Synthetic system (rev 4, France)')
        cfg=Configuration(variant_name='Synthetic France configuration',computer=other)
        cfg.specifications=[Specification(component_type='RAM',property_name='Capacity',numeric_value=4,unit='KB')]
        other.images=[ComputerImage(remote_url='https://example.org/regional.jpg',is_primary=True)]
        db.add_all([base,other]);db.commit()
        return base.id,other.id,cfg.id


def test_bulk_regional_merge_preserves_children_queue_audit_and_replay(client):
    target,source,cfg=regional_pair()
    client.post('/api/admin/photos')
    preview=client.get('/api/admin/regional/preview').json()
    assert preview['removed']==1
    result=client.post('/api/admin/regional/apply',json={'token':preview['token']})
    assert result.status_code==200,result.text
    assert result.json()['remaining']==11
    c=client.get(f'/api/computers/{target}').json()
    assert c['description']=='Keep manual text' and c['configurations'][0]['id']==cfg and len(c['images'])==1
    assert client.get(f'/api/computers/{source}').status_code==404
    audit=client.get('/api/admin/imports/reconciliation/history/'+str(result.json()['reconciliation_ids'][0])).json()
    assert audit['computer'][0]['id'] in [target,source]
    with SessionLocal() as db:assert not db.scalar(select(PhotoItem.id).where(PhotoItem.computer_id==source))
    again=client.get('/api/admin/regional/preview').json();assert again['removed']==0
    assert client.post('/api/admin/regional/apply',json={'token':again['token']}).json()['removed']==0


def test_regional_preview_detects_later_edit(client):
    target,source,cfg=regional_pair()
    preview=client.get('/api/admin/regional/preview').json()
    with SessionLocal() as db:db.get(Computer,target).description='Changed after preview';db.commit()
    assert client.post('/api/admin/regional/apply',json={'token':preview['token']}).status_code==409
    assert client.get(f'/api/computers/{source}').status_code==200


def test_regional_canonical_name_when_no_countryless_record(client):
    target,source,cfg=regional_pair()
    with SessionLocal() as db:db.get(Computer,target).model_name='Synthetic system (rev 4, Germany)';db.commit()
    p=client.get('/api/admin/regional/preview').json()
    result=client.post('/api/admin/regional/apply',json={'token':p['token']})
    assert result.status_code==200,result.text
    kept=p['groups'][0]['target_id']
    assert client.get(f'/api/computers/{kept}').json()['model_name']=='Synthetic system (rev 4)'


def test_real_bundle_valid_and_prices_have_exact_scope_and_sources():
    data,index,sha=bundle()
    for record in data['records']:Record.model_validate(record)
    prices=[(r,x) for r in data['records'] for x in r.get('releases',[]) if x.get('price') is not None]
    assert len(prices)==5
    assert all(r['model_name'].startswith('IBM RT PC Model ') and x['currency']=='USD' and x['market']=='Stati Uniti' for r,x in prices)
    assert any('ENUS' in x['evidence'] for r,x in prices)
    assert not any(s.get('text_value') in ('Speaker','Floppy sound','Cassette') for r in data['records'] for v in r['configurations'] for s in v['specifications'])
    assert 'AppleDB-MIT' in data['metadata']['licenses']
    classic=next(r for r in data['records'] if r['model_name']=='Macintosh Classic')
    codes=[s['text_value'] for v in classic['configurations'] for s in v['specifications'] if s['property_name']=='Codice modello']
    assert codes==['M0420 / M1420']


def test_enrichment_preserves_manual_descriptions_and_never_adds_models(client):
    before=client.get('/api/computers/5').json()
    with SessionLocal() as db:db.get(Computer,3).description='   ';db.commit()
    p=client.get('/api/admin/enrichment/preview').json()
    result=client.post('/api/admin/enrichment/apply',json={k:p[k] for k in ('token','after_id','upper_id')})
    assert result.status_code==200,result.text
    assert client.get('/api/computers').json()['total']==10
    after=client.get('/api/computers/5').json()
    assert after['description']==before['description']
    assert set(v['id'] for v in before['configurations']).issubset(v['id'] for v in after['configurations'])
    assert client.get('/api/computers/3').json()['description'].startswith('Apple II')
    job=client.get('/api/admin/imports/'+str(result.json()['job']['id'])).json()
    assert not job['verification_counts'].get('verified')
    second=client.get('/api/admin/enrichment/preview').json()
    r=client.post('/api/admin/enrichment/apply',json={k:second[k] for k in ('token','after_id','upper_id')})
    assert r.status_code==200 and not r.json()['job']['counts'].get('imported')
    assert not r.json()['job']['counts'].get('updated')


def test_existing_only_job_skips_deleted_record_instead_of_recreating(client):
    from app.importing.engine import stage,apply_job
    record={'manufacturer':'Synthetic','model_name':'Removed','description':'Do not recreate','source':{'title':'Synthetic source'}}
    with SessionLocal() as db:
        job=stage(db,'manual','synthetic.json','json',json.dumps([record]).encode(),options={'upload':True,'existing_only':True})
        job.rows[0].computer_id=None;db.commit();apply_job(db,job.id)
        assert job.rows[0].status=='skipped'
    assert client.get('/api/computers').json()['total']==10


def test_changed_description_invalidates_enrichment_preview(client):
    with SessionLocal() as db:db.get(Computer,3).description=None;db.commit()
    p=client.get('/api/admin/enrichment/preview').json()
    with SessionLocal() as db:db.get(Computer,3).description='Manual correction';db.commit()
    assert client.post('/api/admin/enrichment/apply',json={k:p[k] for k in ('token','after_id','upper_id')}).status_code==409


def test_before_regional_merge_shared_data_attaches_to_only_one_existing_record(client):
    with SessionLocal() as db:
        original=db.get(Computer,5)
        regional=Computer(manufacturer_id=original.manufacturer_id,model_name=original.model_name+' (France)')
        db.add(regional);db.commit();regional_id=regional.id
    p=client.get('/api/admin/enrichment/preview').json()
    r=client.post('/api/admin/enrichment/apply',json={k:p[k] for k in ('token','after_id','upper_id')})
    assert r.status_code==200,r.text
    assert r.json()['job']['status']=='completed'
    assert client.get('/api/computers').json()['total']==11
    assert client.get(f'/api/computers/{regional_id}').json()['configurations']==[]


def test_reimport_after_regional_merge_reuses_release_and_renamed_configuration_ids(client):
    from app.importing.engine import stage,apply_job
    with SessionLocal() as db:
        maker=db.scalar(select(Manufacturer).where(Manufacturer.name=='Apple'))
        pair=[Computer(manufacturer=maker,model_name='Synthetic replay ('+region+')') for region in ('France','Germany')]
        db.add_all(pair);db.commit();ids=[c.id for c in pair]
        records=[{'manufacturer':'Apple','model_name':c.model_name,'external_id':str(c.id),
            'source':{'title':'Synthetic regional source','url':'https://example.org/regional-fixture'},
            'configurations':[{'variant_name':'Same original configuration','specifications':[{'component_type':'RAM','property_name':'Capacity','numeric_value':4,'unit':'KB'}]}],
            'releases':[{'market':'Synthetic market','release_date':'1980','price':100,'currency':'USD'}]} for c in pair]
        job=stage(db,'manual','legacy.json','json',json.dumps(records).encode(),options={'upload':True})
        for row,cid in zip(job.rows,ids):row.computer_id=cid;row.status='ready'
        db.commit();apply_job(db,job.id)
    p=client.get('/api/admin/regional/preview').json()
    r=client.post('/api/admin/regional/apply',json={'token':p['token']});assert r.status_code==200,r.text
    kept=p['groups'][0]['target_id'];before=client.get(f'/api/computers/{kept}').json()
    with SessionLocal() as db:
        job=stage(db,'manual','replay.json','json',json.dumps(records).encode(),options={'upload':True});apply_job(db,job.id)
        assert [row.status for row in job.rows]==['unchanged','unchanged']
    after=client.get(f'/api/computers/{kept}').json()
    assert after['releases']==before['releases'] and after['configurations']==before['configurations']
