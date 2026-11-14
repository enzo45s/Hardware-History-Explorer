"""Presentation must preserve import identity, source evidence and variants."""
from types import SimpleNamespace

from sqlalchemy import select

from app.catalog_display import configuration_displays, description_text, specification_display
from app.main import SessionLocal, EAGER, full
from app.models import Computer, Configuration, Source, Specification
from app.assistant_context import retrieve
from app.importing.enrichment import italian_summary


def test_display_keeps_default_ram_separate_from_documented_capacity():
    def view(name):
        return specification_display({'component_type': 'RAM', 'property_name': name})['property_name']
    assert view('Capacità predefinita (MAME)') == 'Capacità di riferimento'
    assert len({view('Capacità predefinita (MAME)'), view('Capacità minima riportata'),
                view('Capacità massima riportata'), view('Capacità')}) == 4
    assert view('Nuova misura sconosciuta') == 'Nuova misura sconosciuta'


def test_display_names_preserve_revisions_and_resolve_collisions_stably():
    def config(id, name):
        return SimpleNamespace(id=id, variant_name=name, description=None)
    rows = [config(1, 'MAME a — Example'), config(2, 'MAME b — Example'),
            config(3, 'MAME c — ROM 03'), config(4, 'MAME d — ROM 01'),
            config(5, 'Configurazione di riferimento (1)'),
            config(6, 'Configurazione di riferimento · #1')]
    result = configuration_displays(rows, 'Example')
    assert result == configuration_displays(list(reversed(rows)), 'Example')
    assert len({v['display_name'] for v in result.values()}) == len(rows)
    assert result[3]['display_name'] == 'ROM 03'
    assert result[4]['display_name'] == 'ROM 01'
    assert rows[0].variant_name == 'MAME a — Example'
    assert description_text('Testo manuale: MAME è una delle fonti.') == 'Testo manuale: MAME è una delle fonti.'


def test_catalog_editor_compare_and_assistant_keep_raw_evidence(client):
    original_description = ('Example è un home computer di Archivio. MAME associa il modello all’anno 1982.'
                            ' Le configurazioni emulate documentano CPU esempio.')
    original_note = ('Configurazione emulata MAME; registrazione: Example. Anno dichiarato: 1982.'
                     ' Non attesta opzioni ordinabili. Opzioni RAM nell’emulatore: 16K, 32K.')
    with SessionLocal() as db:
        computer = db.get(Computer, 1)
        computer.description = original_description
        source = Source(title='MAME · driver di riferimento', url='https://github.com/mamedev/mame', publisher='MAME')
        config = Configuration(variant_name='MAME example — Example', description=original_note,
            specifications=[Specification(component_type='CPU', property_name='Modello emulato (MAME)',
                text_value='CPU esempio', sources=[source]),
                Specification(component_type='RAM', property_name='Capacità predefinita (MAME)',
                numeric_value=640, unit='KiB', sources=[source])])
        computer.configurations.append(config)
        computer.sources.append(source)
        db.commit()
        cfg_id, spec_id, source_id = config.id, config.specifications[0].id, source.id
    record = client.get('/api/computers/1').json()
    assert record['description'] == original_description
    assert 'MAME' not in record['display_description'] and 'emulat' not in record['display_description']
    cfg = next(c for c in record['configurations'] if c['id'] == cfg_id)
    assert cfg['display_name'] == 'Example'
    assert cfg['description'] == original_note
    assert cfg['display_description'] == 'Opzioni di memoria censite: 16K, 32K.'
    spec = next(s for s in cfg['specifications'] if s['id'] == spec_id)
    assert spec['property_name'] == 'Modello emulato (MAME)'
    assert spec['display']['property_name'] == 'Modello'
    assert spec['sources'][0]['id'] == source_id and spec['sources'][0]['publisher'] == 'MAME'
    overview = next(r for r in client.get('/api/computers').json()['items'] if r['id'] == 1)
    assert overview['display_description'] == record['display_description']
    assert client.get('/api/compare?ids=1,2').json()[0] == record
    raw_editor = client.get('/api/admin/computers/1').json()
    assert 'display_description' not in raw_editor
    editor = client.get('/api/admin/computers/1?readable=true').json()
    assert editor['display_description'] == record['display_description']
    assert next(c for c in editor['configurations'] if c['id'] == cfg_id)['display_name'] == 'Example'
    with SessionLocal() as db:
        loaded = db.scalar(select(Computer).where(Computer.id == 1).options(*EAGER))
        assert loaded.description == original_description
        assert 'MAME' not in italian_summary(loaded) and 'emulat' not in italian_summary(loaded)
        context = retrieve(db, 'IBM System/360', EAGER, full)
        item = next(r for r in context['computers'] if r['id'] == 1)
        assert item['description'] == record['display_description']
        assert next(v for v in item['configurations'] if v['name'] == 'Example')
        assert any(s['id'] == source_id for s in item['sources'])
