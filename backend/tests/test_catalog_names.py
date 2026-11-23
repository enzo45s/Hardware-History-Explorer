"""Whole-catalog name cleanup, safe merge/rename/replay and plain research names."""
import json
from copy import deepcopy
import pytest
from contextlib import nullcontext
from unittest.mock import patch
from sqlalchemy import select
from app.catalog_names import catalog_name
from app.commons import photo_query
from app.importing.variant_names import variant_name
from app.importing.engine import stage, apply_job
from app.main import SessionLocal
from app.models import Computer, Specification
from app.import_models import CatalogReconciliation
from app.technical_display import technical_sheets
from test_technical_display import config, spec


@pytest.mark.parametrize('original,expected', [
    ('System-80 (50 Hz)', 'System-80'), ('System-80 (60 Hz)', 'System-80'),
    ('PDP-11 [Q-BUS] (M7195 - MXV11-B)', 'PDP-11'), ('PDP-11 [Unibus](M9301-YA)', 'PDP-11'),
    ('Unlisted model (128 KB RAM)', 'Unlisted model'), ('Unlisted (revision 2)', 'Unlisted'),
    ('Another [optional board] (BIOS (v2)) Plus', 'Another Plus'),
    ('Desktop NTSC', 'Desktop'), ('Desktop PAL', 'Desktop'), ('Desktop 60Hz', 'Desktop'),
    (r'Unlisted \(board\)', 'Unlisted'), ('Apple ][', 'Apple ]['),
    ('Macintosh 128K', 'Macintosh 128K'), ('HP 85B', 'HP 85B'), ('Atari 800XL', 'Atari 800XL'),
    ('PDP-11/20', 'PDP-11/20'), ('Unbalanced (board', 'Unbalanced (board'), ('(Only a name)', '(Only a name)'),
])
def test_generic_name_rule_for_all_manufacturers_keeps_unqualified_model_numbers(original, expected):
    assert catalog_name(original) == expected
    assert catalog_name(catalog_name(original)) == expected


def records():
    names = [('EACA', 'System-80 (50 Hz)'), ('EACA', 'System-80 (60 Hz)'),
        ('DEC', 'PDP-11 [Q-BUS] (M7195 - MXV11-B)'), ('DEC', 'PDP-11 [Unibus](M9301-YA)'),
        ('DEC', 'PDP-11 [Unibus](M9312)'), ('Unlisted manufacturer', 'Desktop (CPU A)'),
        ('Unlisted manufacturer', 'Desktop (CPU B)'), ('Unlisted manufacturer', 'Solo (optional board)')]
    return [{'manufacturer': maker, 'model_name': name, 'external_id': f'name-fixture-{i}',
        'description': f'Curated synthetic history of {name}.', 'source': {'title':'Synthetic original data','url':'https://example.org/name-fixture'},
        'configurations':[{'variant_name':'Base', 'specifications':[
            {'component_type':'CPU','property_name':'Modello','text_value':f'CPU {i}' if maker == 'Unlisted manufacturer' else 'CPU'},
            {'component_type':'Video','property_name':'Frequenza di aggiornamento','numeric_value':50 if i%2 else 60,'unit':'Hz'}]}]}
        for i,(maker,name) in enumerate(names)]


def import_records(data, *, legacy=False):
    # Reproduce archives made before the generic naming rule existed.
    with patch('app.importing.engine.catalog_name', lambda value: value) if legacy else nullcontext(), SessionLocal() as db:
        job=stage(db,'manual','names.json','json',json.dumps(data).encode(),options={'upload':True})
        apply_job(db,job.id)
        return [(r.computer_id,r.status) for r in job.rows]










def test_searches_for_any_model_use_the_plain_name_even_before_local_cleanup():
    for maker,name in [(r['manufacturer'],r['model_name']) for r in records()]:
        clean=catalog_name(name)
        assert '(' not in photo_query(maker,name) and '[' not in photo_query(maker,name)
        assert variant_name(maker,name)['name']==clean


def test_regional_video_noise_is_hidden_but_real_hardware_fields_and_originals_remain():
    rows=[config(1,'System-80 (50 Hz)',[spec(1,'CPU','Modello','Z80'),spec(2,'CPU','Frequenza',1.74,'MHz'),spec(3,'Video','Frequenza di aggiornamento',50,'Hz')]),
          config(2,'System-80 (60 Hz)',[spec(4,'CPU','Modello','Z80'),spec(5,'CPU','Frequenza',1.77,'MHz'),spec(6,'Video','Frequenza di aggiornamento',60,'Hz')])]
    before=deepcopy(rows);sheet,=technical_sheets(rows,'System-80')
    assert rows==before and sheet['regional_variants']==[]
    assert not any(s['component_type']=='Video' for s in sheet['specifications'])
    assert next(s for s in sheet['specifications'] if s['display']['property_name']=='Frequenza')['text_value']=='1.74 MHz / 1.77 MHz'
    assert technical_sheets([config(1,'Base',[spec(1,'Video','Frequenza di aggiornamento',144,'Hz')])],'Modern')[0]['specifications'][0]['numeric_value']==144


def test_new_imports_follow_the_general_rule_without_recreating_attributes_or_sharing_cpus(client):
    data=records()
    for i in (5,6):
        data[i]['sales']=[{'market':'Italy','units_sold':i,'metric_type':'units_sold'}]
        data[i]['facts']=[{'fact_type':'Synthetic scope','statement':'Shared words with a variant-specific source.'}]
    first=import_records(data)
    for name, count in [('System-80',1),('PDP-11',1),('Desktop',1),('Solo',1)]:
        found=client.get('/api/computers',params={'q':name}).json()['items']
        assert len(found)==count and found[0]['model_name']==name
    assert first[0][0]==first[1][0] and first[2][0]==first[3][0]==first[4][0]
    assert first[5][0]==first[6][0]
    desktop=client.get(f'/api/computers/{first[5][0]}').json()
    assert len(desktop['display_configurations'])==2
    assert {s['units_sold'] for s in desktop['sales']}=={5,6}
    assert len(desktop['facts'])==2
    assert all(s.get('model_variant') for s in desktop['sales']+desktop['facts'])
    assert all(status=='unchanged' for _,status in import_records(data))


def test_country_spelling_does_not_create_an_alias_that_captures_the_base_model(client):
    data=records()[-1]
    data={**data,'model_name':'Country model (France)','manufacturer':'Country maker'}
    cid=import_records([data])[0][0]
    plain={**data,'model_name':'Country model','external_id':'plain-model','description':'New plain-model history'}
    assert import_records([plain])[0][0]==cid
    assert client.get(f'/api/computers/{cid}').json()['model_name']=='Country model'


def test_plain_source_does_not_bind_a_variant_price_or_fail_on_identical_markets(client):
    base={**records()[-1], 'model_name':'Shared model','external_id':'shared-base',
        'releases':[{'market':'Italy','release_date':'1985','price':100,'currency':'EUR'}]}
    board={**base,'model_name':'Shared model (optional board)','external_id':'shared-board',
        'releases':[{'market':'Italy','release_date':'1985','price':200,'currency':'EUR'}]}
    country={**base,'model_name':'Shared model (Sweden/Finland)','external_id':'shared-country'}
    rows=import_records([base,board,country]);assert len({cid for cid,_ in rows})==1
    data=client.get(f'/api/computers/{rows[0][0]}').json()
    assert sorted(r['price'] for r in data['releases'])==[100,200]
    assert all(status=='unchanged' for _,status in import_records([base,board,country]))
