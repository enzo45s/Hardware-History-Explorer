import json
from copy import deepcopy

import pytest
from sqlalchemy import select

from app.main import SessionLocal
from app.models import (Computer, Manufacturer, Configuration, Specification, Source, spec_source)
from app.import_models import CatalogReconciliation, ComputerAlias
from app.catalog_revision import prepare, apply
from app.measurement_cleanup import normalize_measurement, quantity_text, split_cpu
from app.importing.catalog_aliases import alias_for
from app.technical_display import technical_sheets


@pytest.mark.parametrize('value,expected', [
    ('6502A - 1.79Mhz Mhz',('6502A',1.79,'MHz')),
    ('ARM 3 - 24 MHz Mhz',('ARM 3',24,'MHz')),
    ('8086 - 0,008 GHz',('8086',8,'MHz')),
])
def test_cpu_clocks_are_explicit_not_inferred_from_processor_codes(value,expected):
    name,freq=split_cpu(value)
    assert (name,freq['numeric_value'],freq['unit'])==expected
    assert split_cpu('Intel 8086') is None
    assert split_cpu('Z80 - Mhz') is None
    assert split_cpu('Z80 - 4 MHz GHz') is None


@pytest.mark.parametrize('value,expected', [('7501 - 0.89:1.76 Mhz','0.89 : 1.76 MHz'),
    ('8086 - 4.77, 7.14 Mhz','4.77 , 7.14 MHz'),('68000 - 8-16 Mhz','8 - 16 MHz')])
def test_alternative_clocks_remain_expressions_not_a_base_clock(value,expected):
    _,result=split_cpu(value)
    assert result=={'property_name':'Frequenze riportate','numeric_value':None,'text_value':expected,'unit':None}


def test_exact_units_are_converted_but_historical_prefixes_and_bits_are_preserved():
    base={'component_type':'RAM','component_name':None,'property_name':'Capacità riportata','numeric_value':1152,'text_value':None,'unit':'B'}
    after=normalize_measurement(base)
    assert (after['numeric_value'],after['unit'])==(1.125,'KiB')
    for unit in ('KB','MB','kb','Kb','mb'):
        old={**base,'unit':unit};assert normalize_measurement(old)==old
    old={**base,'numeric_value':None,'text_value':'2 MiB','unit':None}
    assert normalize_measurement(old)=={**old,'numeric_value':2048,'text_value':None,'unit':'KiB'}
    assert quantity_text('32Kb - 64Kb + 16Mb VRAM')=='32 Kb - 64 Kb + 16 Mb VRAM'
    assert normalize_measurement({**base,'component_type':'CPU','property_name':'Frequenza','unit':'mHz'})['unit']=='mHz'


def test_audited_apply_preserves_ids_sources_review_states_and_manufacturer_aliases(client):
    with SessionLocal() as db:
        first=Manufacturer(name='HP');second=Manufacturer(name='Hewlett-Packard')
        source=Source(title='Synthetic source',source_type='website',url='https://example.org/spec')
        comp=Computer(manufacturer=second,model_name='Synthetic HP model',description='Testo da conservare.',
            configurations=[Configuration(variant_name='Base',specifications=[
                Specification(component_type='CPU',property_name='Modello',text_value='Z80A - 4Mhz Mhz'),
                Specification(component_type='RAM',property_name='Capacità riportata',numeric_value=1024,unit='B')])])
        db.add_all([first,comp,source]);db.flush()
        cpu,ram=comp.configurations[0].specifications
        db.execute(spec_source.insert().values(target_id=cpu.id,source_id=source.id,evidence='Original evidence',verification_status='pending'))
        old_maker=second.id;c_id=comp.id;ids=[cpu.id,ram.id];src_id=source.id
        db.add(ComputerAlias(manufacturer_key='hewlett-packard',model_key='formermodel',original_name='Former model',computer_id=c_id,original={}))
        db.commit()
    with SessionLocal() as db:
        plan=prepare(db)
        assert plan['summary']['cpu_fields_to_split']==1
        assert len(plan['manufacturer_merges'])==1
        # Operations in the uploaded plan are never trusted.
        fake=deepcopy(plan);fake['changes']=[];fake['manufacturer_merges']=[]
        result=apply(db,fake)
        assert result['created']==1 and result['manufacturers_merged']==1
        comp=db.get(Computer,c_id)
        assert comp.description=='Testo da conservare.' and comp.manufacturer.name=='HP'
        assert db.get(Manufacturer,old_maker) is None
        assert db.get(Specification,ids[0]).text_value=='Z80A'
        assert db.get(Specification,ids[1]).numeric_value==1 and db.get(Specification,ids[1]).unit=='KiB'
        added=next(s for s in comp.configurations[0].specifications if s.id not in ids)
        assert (added.numeric_value,added.unit)==(4,'MHz')
        link=db.execute(select(spec_source).where(spec_source.c.target_id==added.id)).one()._mapping
        assert link['source_id']==src_id and link['verification_status']=='pending' and link['evidence']=='Original evidence'
        assert alias_for(db,'HP','Former model').computer_id==c_id
        audit=db.get(CatalogReconciliation,result['audit_id'])
        assert next(r for r in audit.snapshot['specifications'] if r['id']==ids[0])['before']['text_value']=='Z80A - 4Mhz Mhz'
        second=prepare(db)
        assert second['summary']['specifications_to_normalize']==0 and second['summary']['cpu_fields_to_split']==0
        assert apply(db,second)['audit_id'] is None


def test_stale_plan_and_conflicting_clock_do_not_overwrite_curated_values(client):
    with SessionLocal() as db:
        c=Computer(manufacturer=db.get(Computer,1).manufacturer,model_name='Synthetic dual clock',configurations=[Configuration(variant_name='Base',specifications=[
            Specification(component_type='CPU',property_name='Modello',text_value='Z80 - 4 MHz'),
            Specification(component_type='CPU',property_name='Frequenza',numeric_value=8,unit='MHz')])])
        db.add(c);db.commit()
        plan=prepare(db)
        assert plan['summary']['cpu_fields_to_split']==0
        assert any('diversa' in r['reason'] for r in plan['review'])
        c.model_name='Changed manually';db.commit()
        with pytest.raises(ValueError,match='cambiato'):apply(db,plan)
        db.rollback()


def test_equal_ram_option_is_displayed_once_with_all_original_ids_and_sources():
    def spec(id,prop):return {'id':id,'component_type':'RAM','component_name':None,'property_name':prop,
        'numeric_value':64,'text_value':None,'unit':'KiB','sources':[{'id':id}]}
    rows=[{'id':1,'variant_name':'Base','description':None,'specifications':[spec(1,'Capacità predefinita (MAME)'),spec(2,'Opzioni RAM emulatore (MAME)')]}]
    before=deepcopy(rows);sheets=technical_sheets(rows,'Synthetic')
    assert rows==before and len(sheets)==1
    assert len(sheets[0]['specifications'])==1
    merged=sheets[0]['specifications'][0]
    assert merged['specification_ids']==[1,2] and [s['id'] for s in merged['sources']]==[1,2]
    # Equal banks are physical multiplicity, not duplicate statements.
    rows[0]['specifications']=[spec(1,'Capacità'),spec(2,'Capacità')]
    assert len(technical_sheets(rows,'Synthetic')[0]['specifications'])==2
    # A historical "64 Kb" is not proof of 64 KiB, even on the same system.
    ambiguous={**spec(2,'Capacità riportata'),'numeric_value':None,'text_value':'64 Kb','unit':None}
    rows[0]['specifications']=[spec(1,'Capacità predefinita (MAME)'),ambiguous]
    assert len(technical_sheets(rows,'Synthetic')[0]['specifications'])==2
