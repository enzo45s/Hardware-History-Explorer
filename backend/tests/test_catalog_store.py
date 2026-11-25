"""Persistent catalog semantics and invalidation against both supported DBs."""
from copy import deepcopy
from decimal import Decimal
import json
import pytest
from sqlalchemy import select, update, delete, func, text
from app.main import SessionLocal, engine, full, EAGER
from app.models import (Computer, Configuration, Specification, Source, CatalogSnapshot,
                        CatalogDirty, CatalogMetric, spec_source, catalog_metric_assertions,
                        catalog_metric_sources)
from app.catalog_schema import ensure_schema
from app.catalog_store import refresh_pending, resolved, rebuild, status
from app.catalog_memory import memory_specifications, comparisons


def spec(i, prop, value, unit=None, role=None):
    return {'id': i, 'component_type': 'RAM', 'component_name': role, 'property_name': prop,
            'numeric_value': value if isinstance(value, (int, float)) else None,
            'text_value': value if isinstance(value, str) else None, 'unit': unit,
            'sources': [{'id': i, 'title': f'Documento {i}'}]}


@pytest.mark.parametrize('values,expected,options,note', [
    ([spec(1, 'Capacità', 4096, 'KiB'), spec(2, 'Capacità riportata', '4 MiB'), spec(3, 'Capacità di riferimento', 4, 'MiB'), spec(4, 'Opzioni di memoria', 4096, 'KiB')], '4 MB', None, None),
    ([spec(1, 'Capacità di riferimento', 128, 'KiB')], '128 KB', None, 'dotazione di base non documentata'),
    ([spec(1, 'Capacità riportata', 64, 'KiB'), spec(2, 'Capacità di riferimento', 128, 'KiB')], '64 KB', None, 'riferimento: 128 KB'),
    ([spec(1, 'Capacità', 16, 'KiB'), spec(2, 'Capacità riportata', 32, 'KiB')], '16 / 32 KB', None, 'Quantità diverse'),
    ([spec(1, 'Capacità riportata', '16 - 48 KiB'), spec(2, 'Capacità di riferimento', 48, 'KiB')], '16 - 48 KB', None, None),
    ([spec(1, 'Capacità', 16, 'KiB', 'Banco A'), spec(2, 'Capacità', 16, 'KiB', 'Banco B'), spec(3, 'Capacità', 4, 'KiB', 'VRAM')], 'Banco A: 16 KB; Banco B: 16 KB; VRAM: 4 KB', None, None),
    ([spec(1, 'Limite hardware riportato', 64, 'KiB')], 'Non documentata', 'Massima: 64 KB', None),
    ([spec(1, 'Capacità', 4096, 'KiB'), spec(2, 'Opzioni di memoria', '4096 KiB / 8192 KiB / 16384 KiB')], '4 MB', '4 / 8 / 16 MB', None),
    ([spec(1, 'Capacità riportata', '16 - 32', 'KiB')], '16 - 32 KB', None, None),
    ([spec(1, 'Capacità riportata', '4', 'MiB'), spec(2, 'Capacità', 4096, 'KiB')], '4 MB', None, None),
    ([spec(1, 'Capacità riportata', '64 KiB', 'MiB')], '64 KB (unità dichiarata: MB)', None, None),
    ([spec(1, 'Capacità', 1.125, 'KiB')], '1152 B', None, None),
    ([spec(1, 'Capacità riportata', '1024 parole')], '1024 parole', None, None),
])
def test_memory_resolution_preserves_scope_assertions_and_units(values, expected, options, note):
    original = deepcopy(values)
    result = memory_specifications(values)
    assert result[0]['text_value'] == expected
    assert len(result) == (2 if options else 1)
    if options:
        assert result[1]['text_value'] == options
    if note:
        assert note in ' '.join(result[0]['memory_notes'])
    assert {sid for row in result for sid in row['specification_ids']} == {v['id'] for v in values}
    assert {s['id'] for row in result for s in row['sources']} == {v['id'] for v in values}
    assert values == original


def test_ambiguous_legacy_units_and_annotations_never_become_equivalent_bytes():
    result = memory_specifications([spec(1, 'Capacità', 64, 'KiB'), spec(2, 'Capacità riportata', 64, 'KB'),
        spec(3, 'Capacità riportata', 64, 'Kb'), spec(4, 'Annotazione sulla memoria', 'Capacità non quantificabile.')])
    assert len(result[0]['memory_values']) == 3
    assert 'unità originale' in result[0]['text_value']
    assert '64 Kb' in result[0]['text_value']
    assert 'Capacità non quantificabile' in ' '.join(result[0]['memory_notes'])


def install_sample(db):
    c = db.get(Computer, 1)
    c.model_name = 'Sistema di prova'
    c.configurations.clear(); db.flush()
    source = Source(title='Manuale originale', url='https://example.org/manual')
    ram = Specification(component_type='RAM', property_name='Capacità riportata', numeric_value=4096, unit='KiB', sources=[source])
    c.configurations.append(Configuration(variant_name='Base', specifications=[ram,
        Specification(component_type='RAM', property_name='Capacità di riferimento', numeric_value=8192, unit='KiB', sources=[source]),
        Specification(component_type='RAM', property_name='Capacità massima riportata', numeric_value=16384, unit='KiB', sources=[source])]))
    db.commit()
    return c.id, ram.id, source.id


def test_api_uses_saved_ram_facts_and_editor_retains_originals(client):
    with SessionLocal() as db:
        cid, sid, source = install_sample(db)
    data = client.get(f'/api/computers/{cid}').json()
    assert data['catalog_data']['persisted'] is True
    assert len(data['configurations'][0]['specifications']) == 3
    main, options = data['display_configurations'][0]['specifications']
    assert main['text_value'] == '4 MB' and options['text_value'] == 'Massima: 16 MB'
    assert main['resolution_state'] == 'reported' and main['verification_status'] == 'pending'
    assert main['memory_notes'] == ['Altri valori di riferimento: 8 MB.']
    compare = client.get('/api/compare?ids=1,2').json()[0]
    assert compare['display_configurations'] == data['display_configurations']
    editor = client.get('/api/admin/computers/1').json()
    assert len(editor['configurations'][0]['specifications']) == 3
    with SessionLocal() as db:
        metric = db.scalar(select(CatalogMetric).where(CatalogMetric.computer_id == cid, CatalogMetric.metric == 'ram.capacity'))
        assert metric.numeric_value == Decimal(4096) and metric.unit == 'KiB'
        assert db.scalar(select(catalog_metric_assertions.c.specification_id).where(catalog_metric_assertions.c.metric_key == metric.key, catalog_metric_assertions.c.specification_id == sid)) == sid
        assert db.scalar(select(catalog_metric_sources.c.source_id).where(catalog_metric_sources.c.metric_key == metric.key)) == source
        assert db.get(Specification, sid).property_name == 'Capacità riportata'
        assert status(db)['pending'] == 0


def test_sql_write_is_queued_and_read_fallback_never_returns_stale_facts(client):
    with SessionLocal() as db:
        cid, sid, _ = install_sample(db); refresh_pending(db)
    with engine.begin() as conn:
        conn.execute(update(Specification).where(Specification.id == sid).values(numeric_value=2048))
    with SessionLocal() as db:
        assert db.get(CatalogDirty, cid) is not None
        old = db.get(CatalogSnapshot, cid).input_sha256
        c = db.scalar(select(Computer).where(Computer.id == cid).options(*EAGER))
        data, meta = resolved(c)
        assert meta['persisted'] is False
        assert data['configurations'][0]['specifications'][0]['text_value'] == '2 MB'
        assert db.get(CatalogSnapshot, cid).input_sha256 == old  # read does not write
        assert refresh_pending(db)['updated'] == 1
        assert resolved(c)[1]['persisted'] is True
        assert refresh_pending(db) == {'updated': 0, 'processed': 0}


@pytest.mark.parametrize('change', ['link_status', 'link_delete', 'source', 'source_delete', 'market', 'model', 'configuration', 'alias'])
def test_invalidation_covers_provenance_metadata_scopes_and_removals(client, change):
    with SessionLocal() as db:
        cid, sid, source = install_sample(db); refresh_pending(db)
        old = db.get(CatalogSnapshot, cid).input_sha256
        if change == 'link_status':
            db.execute(update(spec_source).where(spec_source.c.target_id == sid).values(verification_status='verified', evidence='Controllo umano'))
        elif change == 'link_delete':
            db.execute(delete(spec_source).where(spec_source.c.target_id == sid))
        elif change == 'source':
            db.get(Source, source).title = 'Manuale aggiornato'
        elif change == 'source_delete':
            db.delete(db.get(Source, source))
        elif change == 'market':
            db.get(Computer, cid).releases[0].market.name = 'Nuovo mercato'
        elif change == 'model':
            db.get(Computer, cid).model_name = 'Nome aggiornato'
        elif change == 'configuration':
            db.get(Computer, cid).configurations[0].variant_name = 'Configurazione estesa'
        else:
            from app.import_models import ComputerAlias
            cfg = db.get(Specification, sid).configuration_id
            db.add(ComputerAlias(computer_id=cid, manufacturer_key='maker', model_key='model', original_name='Altro modello', original={'configurations': [cfg]}))
        db.commit()
        assert db.get(CatalogDirty, cid) is not None
        refresh_pending(db)
        assert db.get(CatalogSnapshot, cid).input_sha256 != old
        assert not db.scalar(select(CatalogDirty.computer_id).limit(1))


def test_failed_rebuild_is_atomic_and_keeps_retry_queue(client, monkeypatch):
    import app.catalog_store as store
    with SessionLocal() as db:
        cid, sid, _ = install_sample(db); refresh_pending(db)
        original = deepcopy(db.get(CatalogSnapshot, cid).payload)
        db.execute(update(Specification).where(Specification.id == sid).values(numeric_value=2048)); db.commit()
    persist = store.persist
    def fail(db, computer, **kwargs):
        persist(db, computer, **kwargs)
        raise RuntimeError('Interruzione simulata')
    monkeypatch.setattr(store, 'persist', fail)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError):
            refresh_pending(db)
        db.rollback()
        assert db.get(CatalogSnapshot, cid).payload == original
        assert db.get(CatalogDirty, cid) is not None
    monkeypatch.setattr(store, 'persist', persist)
    with SessionLocal() as db:
        assert refresh_pending(db)['updated'] == 1


def test_repeatable_additive_migration_rebuild_and_computer_delete(client):
    with SessionLocal() as db:
        cid, sid, source = install_sample(db); refresh_pending(db)
        original = deepcopy(full(db.get(Computer, cid))['configurations'])
        original_links = list(db.execute(select(spec_source).where(spec_source.c.target_id == sid)))
        first_keys = set(db.scalars(select(CatalogMetric.key)))
    ensure_schema(engine); ensure_schema(engine)
    with SessionLocal() as db:
        assert refresh_pending(db)['updated'] == 0
        assert rebuild(db)['updated'] == 10
        assert set(db.scalars(select(CatalogMetric.key))) == first_keys
        assert full(db.get(Computer, cid))['configurations'] == original
        assert list(db.execute(select(spec_source).where(spec_source.c.target_id == sid))) == original_links
        db.execute(delete(Computer).where(Computer.id == cid)); db.commit()
        assert db.get(CatalogSnapshot, cid) is None
        assert not db.scalar(select(CatalogMetric.key).where(CatalogMetric.computer_id == cid))
        assert db.get(CatalogDirty, cid) is None


def test_new_system_and_substantial_variants_remain_scoped(client):
    with SessionLocal() as db:
        cid, sid, _ = install_sample(db)
        c = db.get(Computer, cid)
        c.configurations.append(Configuration(variant_name='Espansa', specifications=[
            Specification(component_type='RAM', property_name='Capacità riportata', numeric_value=8192, unit='KiB')]))
        db.commit(); refresh_pending(db)
    data = client.get('/api/computers/1').json()
    assert len(data['display_configurations']) == 2
    cells = data['catalog_data']['comparison']
    main = next(v for v in cells['all'] if v['label'] == 'RAM')
    assert main['text'] == '4 / 8 MB' and main['coverage'] == 2
    for cfg in data['display_configurations']:
        cell = next(v for v in cells['configurations'][str(cfg['id'])] if v['label'] == 'RAM')
        assert cell['text'] in {'4 MB', '8 MB'} and '/' not in cell['text']


def test_textual_exact_scalar_is_stored_in_canonical_kib_without_changing_original(client):
    with SessionLocal() as db:
        cid, sid, _ = install_sample(db)
        original = db.get(Specification, sid)
        original.numeric_value, original.text_value, original.unit = None, '4 MiB', None
        db.commit(); refresh_pending(db)
        metric = db.scalar(select(CatalogMetric).where(CatalogMetric.computer_id == cid, CatalogMetric.metric == 'ram.capacity'))
        assert metric.numeric_value == Decimal(4096) and metric.unit == 'KiB'
        assert db.get(Specification, sid).text_value == '4 MiB'


def test_equivalent_sourced_capacities_remain_one_sql_queryable_scalar(client):
    with SessionLocal() as db:
        cid, sid, _ = install_sample(db)
        c = db.get(Computer, cid)
        second = Specification(component_type='RAM', property_name='Capacità', numeric_value=4, unit='MiB',
            sources=[Source(title='Secondo manuale', url='https://example.org/second')])
        c.configurations[0].specifications.append(second)
        db.commit(); refresh_pending(db)
        metric = db.scalar(select(CatalogMetric).where(CatalogMetric.computer_id == cid, CatalogMetric.metric == 'ram.capacity'))
        assert metric.numeric_value == Decimal(4096) and metric.unit == 'KiB'
        assert len(metric.quantities) == 1 and metric.resolution_state == 'reported'
        ids = set(db.scalars(select(catalog_metric_assertions.c.specification_id).where(catalog_metric_assertions.c.metric_key == metric.key)))
        assert {sid, second.id} <= ids


def test_assistant_uses_same_resolutions_and_consolidated_releases(client):
    from app.assistant_context import retrieve
    with SessionLocal() as db:
        cid, _, _ = install_sample(db); refresh_pending(db)
        context = retrieve(db, 'Sistema di prova', EAGER, full)
        item = next(v for v in context['computers'] if v['id'] == cid)
        data = full(db.get(Computer, cid))
        assert item['catalog_version'] == data['catalog_data']['version']
        assert item['configurations'][0]['specifications'] == data['display_configurations'][0]['specifications']
        assert item['releases'] == data['display_releases']


def test_postgresql_concurrent_writer_keeps_its_invalidation_after_drain(client, monkeypatch):
    if engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL row-lock concurrency test')
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import app.catalog_store as store
    with SessionLocal() as db:
        cid, sid, _ = install_sample(db)
    entered, release, writer_started = threading.Event(), threading.Event(), threading.Event()
    original = store.persist
    def pause(db, computer, **kwargs):
        result = original(db, computer, **kwargs)
        if computer.id == cid:
            entered.set()
            assert release.wait(10)
        return result
    def drain():
        with SessionLocal() as db:
            return store.refresh_pending(db)
    def write():
        with engine.begin() as conn:
            writer_started.set()
            conn.execute(update(Specification).where(Specification.id == sid).values(numeric_value=2048))
    monkeypatch.setattr(store, 'persist', pause)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(drain)
        try:
            assert entered.wait(10)
            writer = pool.submit(write)
            assert writer_started.wait(10)
        finally:
            release.set()
        future.result(timeout=15); writer.result(timeout=15)
    monkeypatch.setattr(store, 'persist', original)
    with SessionLocal() as db:
        assert db.get(CatalogDirty, cid) is not None
        assert refresh_pending(db)['updated'] == 1
        metric = db.scalar(select(CatalogMetric).where(CatalogMetric.computer_id == cid, CatalogMetric.metric == 'ram.capacity'))
        assert metric.numeric_value == Decimal(2048)
