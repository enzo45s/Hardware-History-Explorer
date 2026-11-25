"""Research is scoped, transactional, sourced and safe for curated catalog data."""
import importlib
import json
from datetime import date

import pytest
from sqlalchemy import select, func, update
from app.main import SessionLocal
from app.models import (Computer, Manufacturer, Configuration, Specification, ComputerImage,
                        Source, Release, Market, spec_source)
from app.import_models import CatalogReconciliation, ImportClaim, ImportJob, ImportRow, ComputerAlias
from app.importing import catalog_research as research
from app.importing.catalog_aliases import alias_for
from app.description_attribution import attribution


@pytest.fixture(autouse=True)
def no_seed(monkeypatch):
    monkeypatch.setattr(importlib.import_module('app.main'), 'seed', lambda db: None)


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def card(db, model, maker, description=None, configs=None):
    m = db.scalar(select(Manufacturer).where(Manufacturer.name == maker))
    if m is None: m = Manufacturer(name=maker)
    c = Computer(manufacturer=m, model_name=model, description=description,
                 configurations=configs or [Configuration(variant_name='Scheda tecnica')])
    db.add(c); db.flush()
    return c


def test_package_exact_model_evidence_no_fake_regional_profiles_or_prices():
    data, checksum = research.load()
    assert len(data['records']) == 103 and len(checksum) == 64
    assert len(data['photos']) == 32
    rows = {r['model_name']: r for r in data['records']}
    assert {r['model_name'] for r in data['records'] if r.get('releases')} == {'Sol-20', 'Laser 500'}
    assert not any('price' in release for r in data['records'] for release in r.get('releases', []))
    for name, expected in [('PC-8801MA', 192), ('PC-8801FA', 64), ('IQ-1000 DPC-180', 64), ('Laser 500', 64)]:
        specs = rows[name]['configurations'][0]['specifications']
        assert next(s['numeric_value'] for s in specs if s['component_type'] == 'RAM' and s['property_name'] == 'Capacità') == expected
    assert any(c['model_name'] == 'NeXTcube' and c['after']['text_value'] == 'Motorola 68040' for c in data['corrections'] if c['after'])
    assert not any(c['model_name'] in ['PC-9821V20', 'PC-9821Xa16'] and c['before']['component_type'] == 'CPU' for c in data['corrections'])
    assert next(s['numeric_value'] for s in rows['PC-9801F']['configurations'][0]['specifications'] if s['component_type']=='RAM' and s['property_name']=='Capacità') == 128
    assert next(s['text_value'] for s in rows['PC-9821Ra20']['configurations'][0]['specifications'] if s['component_type']=='CPU' and s['property_name']=='Modello') == 'Intel Pentium Pro'
    assert not any('MAME' in r['description'] for r in data['records'] if r.get('description'))


def test_preview_and_apply_create_only_requested_models_with_sources_and_repeat(client):
    with SessionLocal() as db:
        assert set(research.preview(db)['new_models']) == {'Sol-20', 'Laser 500'}
        assert count(db, ImportJob) == 0 and count(db, Computer) == 0
        result = research.apply(db)
        assert result['created'] == 2 and result['photographs_added'] == 2
        assert count(db, Computer) == 2
        sol = db.scalar(select(Computer).where(Computer.model_name == 'Sol-20')); cid = sol.id
        assert sol.configurations[0].specifications and sol.sources and sol.description
        assert sol.releases[0].release_date == date(1976, 1, 1)
        assert sol.releases[0].release_precision == 'year'
        assert not sol.releases[0].price
        assert all(s.sources for s in sol.configurations[0].specifications)
        assert sol.manufacturer.description and sol.manufacturer.sources
        assert not db.scalar(select(ImportClaim.id).where(ImportClaim.status == 'verified'))
        assert research.apply(db)['already_applied']
        assert count(db, ImportJob) == 1
        db.delete(sol); db.commit()
        assert research.apply(db)['already_applied'] and count(db, Computer) == 1
    # The new native rows use the existing catalog and comparison data APIs.
    laser = client.get('/api/computers', params={'q': 'Laser 500'}).json()
    assert laser['total'] == 1 and laser['items'][0]['description']


def test_curated_description_ram_cover_and_commercialization_are_preserved(client):
    with SessionLocal() as db:
        c = card(db, 'Laser 500', 'Video Technology', 'Descrizione scritta a mano')
        c.configurations[0].specifications.append(Specification(component_type='RAM', property_name='Capacità', numeric_value=128, unit='KB', sources=[Source(title='Manual source', url='https://example.org/manual')]))
        c.images.append(ComputerImage(remote_url='https://example.org/photo.jpg', is_primary=True, display_order=0))
        c.releases.append(Release(market=Market(name='Europa'), release_date=date(1986, 4, 1), release_precision='month', price=99, currency='GBP'))
        db.commit(); cid = c.id
        result = research.apply(db); db.expire_all(); c = db.get(Computer, cid)
        assert result['created'] == 1 and c.description == 'Descrizione scritta a mano'
        ram = [s for s in c.configurations[0].specifications if s.component_type == 'RAM' and s.property_name == 'Capacità']
        assert len(ram) == 1 and ram[0].numeric_value == 128 and len(ram[0].sources) == 1
        assert next(i for i in c.images if i.is_primary).remote_url == 'https://example.org/photo.jpg'
        assert len(c.releases) == 1 and c.releases[0].price == 99
        assert any(c.status == 'conflict' for c in db.scalars(select(ImportClaim).where(ImportClaim.computer_id == cid)))


@pytest.mark.parametrize('protection', ['legacy', 'verified', 'manual', 'mixed', 'edited_legacy'])
def test_exact_legacy_correction_requires_unverified_exclusively_legacy_support(client, protection):
    data, _ = research.load()
    rule = next(r for r in data['corrections'] if r['model_name'] == 'NeXTcube' and r['before']['property_name'] == 'Modello')
    with SessionLocal() as db:
        c = card(db, 'NeXTcube', 'Next Software Inc')
        src = Source(title='MAME legacy source' if protection != 'manual' else 'Manual source', url='https://example.org/base')
        s = Specification(**rule['before'], sources=[src]); c.configurations[0].specifications.append(s); db.commit()
        if protection == 'edited_legacy':
            job = ImportJob(provider='manual', filename='synthetic.json', format='json', checksum='0'*64, raw_payload='[]')
            row = ImportRow(position=0, raw={}, computer_id=c.id, status='updated', candidates=[c.id])
            job.rows.append(row); db.add(job); db.flush()
            row.claims.append(ImportClaim(computer_id=c.id, source_id=src.id, entity='Specification', target_id=s.id,
                field='quantity', value={'text_value':'Older value before manual edit','numeric_value':None,'unit':None}, previous={}, status='pending'))
            db.commit()
        if protection == 'mixed': s.sources.append(Source(title='Manual correction source', url='https://example.org/curated')); db.commit()
        if protection == 'verified':
            db.execute(update(spec_source).where(spec_source.c.target_id == s.id).values(verification_status='verified')); db.commit()
        sid = s.id
        result = research.apply(db); db.expire_all(); s = db.get(Specification, sid)
        if protection == 'legacy':
            assert s.text_value == 'Motorola 68040'
            assert result['specifications_corrected'] == 1
            assert all('MAME' not in source.title for source in s.sources)
        else:
            assert s.text_value == rule['before']['text_value'] and result['specifications_corrected'] == 0
            assert result['protected'] and result['conflicts']
        audit = db.scalar(select(CatalogReconciliation).where(CatalogReconciliation.entity == research.ENTITY))
        assert audit.snapshot['changes']


def test_indy_multiple_cpu_configurations_get_only_shared_general_specs(client):
    with SessionLocal() as db:
        variants = [Configuration(variant_name='Indy R4600', specifications=[Specification(component_type='CPU', property_name='Frequenza', numeric_value=100, unit='MHz')]),
                    Configuration(variant_name='Indy R5000', specifications=[Specification(component_type='CPU', property_name='Frequenza', numeric_value=150, unit='MHz')]),
                    Configuration(variant_name='Dati generali del sistema')]
        c = card(db, 'Indy', 'Silicon Graphics', configs=variants); db.commit(); cid = c.id
        original = {v.id: [(s.id, s.numeric_value) for s in v.specifications] for v in variants[:2]}
        result = research.apply(db); db.expire_all(); c = db.get(Computer, cid)
        assert not any(x['model_name'] == 'Indy' for x in result['skipped'])
        assert len(c.configurations) == 3
        for cfg in [v for v in c.configurations if v.id in original]: assert [(s.id, s.numeric_value) for s in cfg.specifications] == original[cfg.id]
        assert len(research.configuration(c).specifications) == 4
        assert not any(s.property_name == 'Capacità' for s in research.configuration(c).specifications)


def test_rename_keeps_identity_alias_sources_and_wikipedia_attribution(client):
    with SessionLocal() as db:
        pc = card(db, 'PC', 'Kaypro Corporation'); cid = pc.id
        color = card(db, 'NeXTcubeTurboColor', 'Next Software Inc')
        # The actual scoped model name is defined by the package, never guessed here.
        rule = next(r for r in research.load()[0]['renames'] if r['manufacturer'] == 'Next Software Inc')
        color.model_name = rule['model_name']; color.description = None
        db.commit(); colorid = color.id
        research.apply(db); db.expire_all()
        pc = db.get(Computer, cid); color = db.get(Computer, colorid)
        assert pc.model_name == 'Kaypro PC' and color.model_name == rule['new_name']
        assert alias_for(db, 'Kaypro Corporation', 'PC').computer_id == cid
        assert alias_for(db, 'Next Software Inc', rule['model_name']).computer_id == colorid
        assert attribution(color)['license_url'].endswith('/by-sa/4.0/')


def test_ambiguous_existing_model_is_skipped_not_merged_and_no_substantial_variant_guessed(client):
    with SessionLocal() as db:
        card(db, 'PC-8801FA', 'NEC'); card(db, 'PC-8801FA', 'NEC')
        card(db, 'NeXTstation', 'Next Software Inc', configs=[Configuration(variant_name='A'), Configuration(variant_name='B')])
        db.commit(); result = research.apply(db)
        skipped = {r['model_name']: r['reason'] for r in result['skipped']}
        assert 'ambigua' in skipped['PC-8801FA'] and 'multiple' in skipped['NeXTstation']
        assert count(db, Computer) == 5


def test_same_company_alias_does_not_duplicate_an_existing_vtech_computer(client):
    with SessionLocal() as db:
        c = card(db, 'Laser 500', 'VTech'); db.add(Manufacturer(name='Video Technology')); db.commit(); cid = c.id
        result = research.apply(db)
        assert result['created'] == 1 and db.get(Computer, cid).manufacturer.name == 'VTech'
        assert count(db, Computer) == 2


@pytest.mark.parametrize('failure_point', ['stage', 'refresh_pending'])
def test_any_failure_rolls_back_new_models_sources_and_all_native_changes(client, monkeypatch, failure_point):
    def fail(*a, **k): raise RuntimeError('synthetic failure')
    if failure_point == 'stage': monkeypatch.setattr(research, 'stage', fail)
    else: monkeypatch.setattr('app.catalog_store.refresh_pending', fail)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match='synthetic failure'): research.apply(db)
        for cls in [Computer, Manufacturer, Specification, Source, ImportJob, CatalogReconciliation]:
            assert count(db, cls) == 0


def test_same_commons_file_at_different_resolution_is_not_added_twice():
    proposal = {'image_url':'https://upload.wikimedia.org/wikipedia/commons/a/aa/example.jpg',
                'source_url':'https://commons.wikimedia.org/wiki/File:Example_photo.jpg'}
    image = ComputerImage(remote_url='https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/example.jpg/600px-example.jpg',
                          source_url='https://commons.wikimedia.org/wiki/File:Example%20photo.jpg')
    assert research.same_photo(image, proposal)
    image.source_url = 'https://www.1000bit.it/scheda.asp?id=342'
    proposal['source_url'] = image.source_url
    assert not research.same_photo(image, proposal)  # One archive page may contain several distinct images.
