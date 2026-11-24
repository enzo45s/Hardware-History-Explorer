"""Sourced revisions on disposable copies; never the user's database."""
import importlib
from datetime import date
import pytest
from sqlalchemy import select, func, update
from app.main import SessionLocal
from app.models import Computer, Manufacturer, Category, Configuration, Specification, Release, Market, Source, ComputerImage, spec_source
from app.import_models import ImportJob, ImportClaim, CatalogReconciliation
from app.importing import earthstation_mistrum as research
from app.importing.vocabulary import spec_values

@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'), 'seed', lambda db: None)


def seed():
    data, _ = research.load(); ids = {}
    with SessionLocal() as db:
        old = Source(title='Synthetic previous evidence', url='https://example.org/old')
        market = Market(name='Stati Uniti')
        for record in data['records']:
            name = record['model_name']; maker = Manufacturer(name=record['manufacturer'])
            specs = [Specification(**r['before'], sources=[old]) for r in data['corrections'] if r['model_name'] == name]
            specs.append(Specification(component_type='CPU', property_name='Frequenza', numeric_value=8 if name == 'EarthStation-I' else 3.5, unit='MHz', sources=[old]))
            c = Computer(manufacturer=maker, model_name=name, description=f'{name} è un calcolatore di {maker.name}.',
                         categories=[Category(name='Personal computer' if name == 'EarthStation-I' else 'Home computer')],
                         configurations=[Configuration(variant_name='Scheda tecnica', specifications=specs)],
                         releases=[Release(market=market, price=1234, currency='USD', release_date=date(1987, 1, 1), release_precision='year', sources=[old])],
                         images=[ComputerImage(remote_url='https://example.org/'+name+'.jpg', caption='Scelta automatica Commons · esempio', source_url=data['wrong_automatic_photos'][name][0], is_primary=True)])
            db.add(c); db.flush(); ids[name] = c.id
        db.add(Computer(manufacturer=Manufacturer(name='Other'), model_name='Mistrum', description='Keep'))
        db.commit()
    return ids


def test_package_documents_physical_memory_photos_and_limits():
    data, _ = research.load()
    assert sum(len(r['configurations'][0]['specifications']) for r in data['records']) == 44
    assert all(not r.get('releases') and not r.get('announcement_date') for r in data['records'])
    for record, value in zip(data['records'], [256, 64]):
        ram = [s for s in record['configurations'][0]['specifications'] if s['component_type'] == 'RAM' and s['property_name'] == 'Capacità']
        assert len(ram) == 1 and ram[0]['numeric_value'] == value and ram[0]['unit'] == 'KB'
    assert 'autorizzato' in data['photos']['EarthStation-I'][0]['license_name']
    assert 'Replica moderna' in data['photos']['Mistrum'][0]['caption']
    assert data['photos']['Mistrum'][0]['license_name'] == 'CC BY-NC-SA 4.0'


def test_preview_apply_prices_identity_attribution_and_repeat(client):
    ids = seed()
    with SessionLocal() as db:
        assert len(research.preview(db)['existing_models']) == 2 and not db.scalar(select(ImportJob.id))
        result = research.apply(db)
        assert result['updated'] == 2 and result['specifications_corrected'] == 7 and result['specifications_retired'] == 1
        assert result['descriptions_updated'] == 2 and result['photos_added'] == 4
        assert result['wrong_automatic_photos_removed'] == 2 and result['categories_corrected'] == 1
        assert db.scalar(select(func.count()).select_from(Computer)) == 3
        for name, cid in ids.items():
            c = db.get(Computer, cid)
            assert c.description.startswith('L’EarthStation-I' if name == 'EarthStation-I' else 'Il Mistrum')
            assert len(c.configurations) == 1 and len(c.releases) == 1
            assert c.releases[0].price == 1234 and c.releases[0].release_date == date(1987, 1, 1)
            assert sum(bool(i.is_primary) for i in c.images) == 1
            assert all(s.sources for cfg in c.configurations for s in cfg.specifications)
        assert [cat.name for cat in db.get(Computer, ids['EarthStation-I']).categories] == ['Workstation']
        assert not db.scalar(select(ImportClaim.id).where(ImportClaim.status == 'verified'))
        count = db.scalar(select(func.count()).select_from(Specification))
        assert research.apply(db)['already_applied'] and db.scalar(select(func.count()).select_from(Specification)) == count
        assert db.scalar(select(func.count()).select_from(ImportJob)) == 1
        audit = db.scalar(select(CatalogReconciliation).where(CatalogReconciliation.entity == research.ENTITY))
        assert len([i for i in audit.snapshot['photo_changes'] if i['action'] == 'retire_unrelated_automatic_image']) == 2
    for cid in ids.values():
        response = client.get(f'/api/computers/{cid}')
        assert response.status_code == 200 and response.json()['sources']
        assert response.json()['images'][0]['source_url'].startswith('https://')


def test_verified_values_manual_changes_and_curated_cover_survive(client):
    ids = seed()
    with SessionLocal() as db:
        c = db.get(Computer, ids['EarthStation-I'])
        cpu = next(s for s in c.configurations[0].specifications if s.component_type == 'CPU' and s.property_name == 'Modello')
        db.execute(update(spec_source).where(spec_source.c.target_id == cpu.id).values(verification_status='verified'))
        ram = next(s for s in c.configurations[0].specifications if s.component_type == 'RAM' and s.property_name == 'Capacità')
        ram.numeric_value = 512; c.description = 'Introduzione curata a mano.'
        for photo in c.images: photo.is_primary = False
        manual = ComputerImage(remote_url='https://example.org/curated.jpg', caption='Foto scelta a mano.', is_primary=True)
        c.images.append(manual); db.commit(); mid = manual.id
        result = research.apply(db); db.refresh(cpu); db.refresh(ram)
        assert result['protected'] and result['curated_descriptions_preserved'] == 1
        assert cpu.text_value == 'NEC V20' and ram.numeric_value == 512
        assert c.description == 'Introduzione curata a mano.' and db.get(ComputerImage, mid).is_primary
        assert db.scalar(select(ImportClaim.id).where(ImportClaim.entity == 'Specification', ImportClaim.target_id == cpu.id, ImportClaim.status == 'conflict'))


def test_absent_ambiguous_and_substantial_configurations_do_not_create_models(client):
    with SessionLocal() as db:
        result = research.apply(db)
        assert result['updated'] == 0 and len(result['skipped']) == 2 and not db.scalar(select(ImportJob.id))
        maker = Manufacturer(name='Alloy')
        db.add_all([Computer(manufacturer=maker, model_name='EarthStation-I'), Computer(manufacturer=maker, model_name='EarthStation-I')])
        db.add(Computer(manufacturer=Manufacturer(name='Amaterske RADIO'), model_name='Mistrum', configurations=[Configuration(variant_name='A'), Configuration(variant_name='B')]))
        db.commit(); assert research.apply(db)['updated'] == 0 and not db.scalar(select(ImportJob.id))


def test_stage_failure_rolls_back_corrections_and_category(client, monkeypatch):
    seed()
    with SessionLocal() as db:
        before = [(s.id, spec_values(s)) for s in db.scalars(select(Specification).order_by(Specification.id))]
        def fail(*a, **kw): raise RuntimeError('staging failure')
        monkeypatch.setattr(research, 'stage', fail)
        with pytest.raises(RuntimeError, match='staging failure'): research.apply(db)
        assert before == [(s.id, spec_values(s)) for s in db.scalars(select(Specification).order_by(Specification.id))]
        assert db.scalar(select(func.count()).select_from(ComputerImage)) == 2 and not db.scalar(select(ImportJob.id))


def test_late_failure_rolls_back_new_photos_claims_and_removed_images(client, monkeypatch):
    seed()
    import app.catalog_store as store
    original = store.refresh_pending; calls = []
    def fail(db, **kw):
        calls.append(True)
        if len(calls) == 2: raise RuntimeError('late photo failure')
        return original(db, **kw)
    monkeypatch.setattr(store, 'refresh_pending', fail)
    with SessionLocal() as db:
        photos = {i.id: i.remote_url for i in db.scalars(select(ComputerImage))}
        with pytest.raises(RuntimeError, match='late photo failure'): research.apply(db)
        assert photos == {i.id: i.remote_url for i in db.scalars(select(ComputerImage))}
        assert not db.scalar(select(ImportJob.id)) and not db.scalar(select(ImportClaim.id))
