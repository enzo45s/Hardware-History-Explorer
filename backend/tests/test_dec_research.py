"""Run the researched DEC package against disposable catalogs, never the user DB."""
import importlib
import json

import pytest
from sqlalchemy import select, func, update

from app.main import SessionLocal
from app.models import Computer, Manufacturer, Category, Configuration, Specification, Source, spec_source
from app.import_models import CatalogReconciliation, ImportJob, ImportClaim
from app.importing import dec_research
from app.importing.identity import computer_key
from app.importing.vocabulary import spec_values


@pytest.fixture(autouse=True)
def no_demo_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'), 'seed', lambda db: None)


def seed_catalog():
    data, _ = dec_research.load_package()
    identifiers = {}
    with SessionLocal() as db:
        maker = Manufacturer(name='Digital Equipment Corporation')
        old_source = Source(title='Precedente fonte di catalogo', url='https://example.org/old-dec-data', source_type='dataset')
        db.add(old_source)
        for row in data['records']:
            if row['model_name'] in dec_research.NEW_MODELS:
                continue
            specs = [Specification(**rule['before'], sources=[old_source]) for rule in data['corrections']
                     if rule['model_name'] == row['model_name']]
            c = Computer(manufacturer=maker, model_name=row['model_name'],
                         description='Testo curato dall’operatore.' if row['model_name'] == 'PDP-1' else None,
                         configurations=[Configuration(variant_name='Scheda tecnica', specifications=specs)])
            if row['model_name']=='DEC 2000 Model 300 AXP':c.categories=[Category(name='Workstation')]
            db.add(c); db.flush(); identifiers[c.model_name] = c.id
        db.add(Computer(manufacturer=Manufacturer(name='Microdigital'), model_name='TK-85', description='Da conservare.'))
        db.commit()
    return identifiers


def test_package_has_evidence_and_does_not_inherit_decmate_ii_ram():
    data, _ = dec_research.load_package()
    assert len(data['records']) == 22
    assert sum(len(c['specifications']) for r in data['records'] for c in r['configurations']) == 181
    records = {r['model_name']:r for r in data['records']}
    assert {r['model_name'] for r in data['records'] if r.get('releases')} == dec_research.NEW_MODELS
    assert not any(s['component_type'] == 'RAM' for s in records['DECmate III']['configurations'][0]['specifications'])
    ram = next(s for s in records['DECmate II']['configurations'][0]['specifications'] if s['component_type'] == 'RAM')
    assert ram['text_value'] == '65536 parole da 12 bit'
    assert '64K words' in ram['evidence']
    cache=next(s for s in records['VAX-11/780']['configurations'][0]['specifications'] if s['component_type']=='Cache')
    assert cache['numeric_value']==8 and cache['unit']=='KiB'
    assert '2048 longword' in cache['evidence'] and 'EK-MM780' in cache['source']['url']
    assert all('sources' not in r and r['source']['url'].startswith('https://') for r in data['records'])


@pytest.mark.parametrize('maker,model,canonical', [
    ('DEC','VAX 11/780','VAX-11/780'), ('Digital','VAX 11-750','VAX-11/750'),
    ('Digital Equipment Corp.','VK-100','GIGI'), ('DEC','VK 100','GIGI'),
])
def test_spelling_aliases_only(maker, model, canonical):
    assert computer_key(maker, model) == computer_key('Digital Equipment Corporation', canonical)
    assert computer_key('Microdigital', model) != computer_key(maker, model)
    assert computer_key('DEC','VAX-11/750') != computer_key('DEC','VAX-11/780')


def test_preview_is_read_only_and_apply_is_sourced_and_idempotent(client):
    ids = seed_catalog()
    photo = client.post(f"/api/computers/{ids['PDP-1']}/images", json={'image_url':'https://example.org/pdp1.jpg'})
    assert photo.status_code == 201
    old_photo = client.get(f"/api/computers/{ids['PDP-1']}").json()['images']
    with SessionLocal() as db:
        counts = {model.__name__:db.scalar(select(func.count()).select_from(model))
                  for model in (Computer, Source, ImportJob, CatalogReconciliation)}
        preview = dec_research.preview(db)
        assert preview['existing_models'] == 19 and len(preview['new_models']) == 3
        assert preview['applicable_corrections'] == 23
        assert counts == {model.__name__:db.scalar(select(func.count()).select_from(model))
                          for model in (Computer, Source, ImportJob, CatalogReconciliation)}
        report = dec_research.apply(db)
        assert report['created'] == 3 and report['updated'] == 19
        assert report['corrected_assertions'] == 7 and report['retired_assertions'] == 16
        assert report['categories_corrected']==1
        assert [c.name for c in db.get(Computer,ids['DEC 2000 Model 300 AXP']).categories]==['Server']
        assert report['curated_descriptions_preserved'] == 1
        assert db.scalar(select(func.count()).select_from(Computer)) == 23
        assert db.scalar(select(Computer.description).where(Computer.model_name == 'TK-85')) == 'Da conservare.'
        assert {c.model_name:c.id for c in db.scalars(select(Computer)) if c.model_name in ids} == ids
        specs = db.scalars(select(Specification).join(Configuration).where(Configuration.computer_id == ids['VAX-11/785'])).all()
        assert any(s.property_name == 'Modello' and 'KA785' in s.text_value for s in specs)
        assert not any(s.component_type == 'Video' for s in specs)
        claims = db.scalars(select(ImportClaim)).all()
        assert claims and not any(c.status == 'verified' for c in claims)
        assert all(s.sources for s in db.scalars(select(Specification)))
        for name in ('Rainbow 100-A','Rainbow 100-B','Rainbow 190-B'):
            assert any(s.text_value=='Zilog Z80A' for cfg in db.get(Computer,ids[name]).configurations for s in cfg.specifications)
        count = db.scalar(select(func.count()).select_from(Specification))
        assert dec_research.apply(db)['already_applied'] is True
        assert db.scalar(select(func.count()).select_from(Specification)) == count
        assert db.scalar(select(func.count()).select_from(ImportJob)) == 1
    pdp = client.get(f"/api/computers/{ids['PDP-1']}").json()
    assert pdp['description'] == 'Testo curato dall’operatore.' and pdp['images'] == old_photo
    results = client.get('/api/computers', params={'q':'GIGI'}).json()['items']
    assert len(results) == 1
    gigi = client.get(f"/api/computers/{results[0]['id']}").json()
    assert 'VK100' in gigi['description'] and gigi['description_attribution']['url'].startswith('https://en.wikipedia.org/')
    assert gigi['year'] == 1981 and gigi['categories'] == ['Terminale programmabile']


def test_verified_assertions_and_manual_changes_are_preserved(client):
    ids = seed_catalog()
    with SessionLocal() as db:
        cpu = db.scalar(select(Specification).join(Configuration).where(Configuration.computer_id == ids['VAX-11/785'], Specification.property_name == 'Modello'))
        db.execute(update(spec_source).where(spec_source.c.target_id == cpu.id).values(verification_status='verified'))
        clock = db.scalar(select(Specification).join(Configuration).where(Configuration.computer_id == ids['MicroVAX II'], Specification.property_name == 'Frequenza'))
        clock.numeric_value = 6
        db.commit()
        report = dec_research.apply(db)
        assert len(report['protected']) == 1
        db.refresh(cpu); db.refresh(clock)
        assert cpu.text_value == 'DEC T11' and clock.numeric_value == 6
        assert db.scalar(select(ImportClaim.id).where(ImportClaim.target_id == cpu.id, ImportClaim.status == 'conflict'))


def test_existing_aliases_do_not_create_duplicates_or_second_configuration(client):
    with SessionLocal() as db:
        maker = Manufacturer(name='DEC')
        gigi = Computer(manufacturer=maker, model_name='VK100', configurations=[Configuration(variant_name='Allestimento originale')])
        vax = Computer(manufacturer=maker, model_name='VAX 11/780')
        db.add_all([gigi, vax]); db.commit(); ids = [gigi.id, vax.id]
        report = dec_research.apply(db)
        assert report['created'] == 1 and report['updated'] == 2
        assert db.scalar(select(func.count()).select_from(Computer)) == 3
        assert db.scalar(select(func.count()).select_from(Manufacturer)) == 1
        assert db.get(Computer, ids[0]).configurations[0].variant_name == 'Allestimento originale'
        assert len(db.get(Computer, ids[0]).configurations) == 1


def test_failure_rolls_back_corrections_sources_and_new_records(client, monkeypatch):
    seed_catalog()
    with SessionLocal() as db:
        before = [(s.id,spec_values(s)) for s in db.scalars(select(Specification).order_by(Specification.id))]
        source_count = db.scalar(select(func.count()).select_from(Source))
        def fail(*args, **kwargs):
            raise RuntimeError('Interruzione simulata dopo le rettifiche')
        monkeypatch.setattr(dec_research, 'stage', fail)
        with pytest.raises(RuntimeError):dec_research.apply(db)
        db.commit()  # Caller cannot accidentally persist a partial failed application.
        assert before == [(s.id,spec_values(s)) for s in db.scalars(select(Specification).order_by(Specification.id))]
        assert db.scalar(select(func.count()).select_from(Source)) == source_count
        assert db.scalar(select(func.count()).select_from(Computer)) == 20
        assert db.scalar(select(func.count()).select_from(ImportJob)) == 0


def test_ambiguous_models_and_substantial_configurations_are_skipped(client):
    with SessionLocal() as db:
        maker = Manufacturer(name='DEC')
        db.add_all([Computer(manufacturer=maker, model_name='VAX 11/780'),
                    Computer(manufacturer=maker, model_name='VAX-11/780'),
                    Computer(manufacturer=maker, model_name='MicroVAX II', configurations=[
                        Configuration(variant_name='A'),Configuration(variant_name='B')])])
        db.commit()
        report = dec_research.apply(db)
        assert report['created'] == 2
        assert {r['model_name'] for r in report['skipped']} >= {'VAX-11/780','MicroVAX II'}


def test_repeated_package_does_not_resurrect_a_deleted_requested_model(client):
    with SessionLocal() as db:
        dec_research.apply(db)
        computer=db.scalar(select(Computer).where(Computer.model_name=='GIGI'))
        db.delete(computer);db.commit()
        assert dec_research.apply(db)['already_applied'] is True
        assert db.scalar(select(Computer.id).where(Computer.model_name=='GIGI')) is None


def test_normal_reimport_after_research_keeps_new_models_and_current_sheets(client):
    from app.importing.engine import stage, apply_job
    from app.models import Fact
    with SessionLocal() as db:
        dec_research.apply(db)
        payload=[row for row in dec_research.load_package()[0]['records'] if row['model_name'] in dec_research.NEW_MODELS]
        # Spelling aliases are identities, not scoped historical variants.
        next(row for row in payload if row['model_name']=='GIGI')['model_name']='VK100'
        next(row for row in payload if row['model_name']=='VAX-11/780')['model_name']='VAX 11/780'
        job=stage(db,'manual','dec-reimport.json','json',json.dumps(payload).encode())
        apply_job(db,job.id)
        assert job.status=='completed',[(row.status,row.error) for row in job.rows]
        assert db.scalar(select(func.count()).select_from(Computer))==3
        assert db.scalar(select(func.count()).select_from(Configuration))==3
        assert db.scalar(select(func.count()).select_from(Fact))==0
