"""One sheet per hardware configuration, with scoped differences and raw evidence."""
from copy import deepcopy
import json
from pathlib import Path

from app.catalog_display import specification_display
from app.technical_display import technical_sheets
from app.importing.vocabulary import normalize_spec
from app.main import SessionLocal
from app.models import Computer, Configuration, Specification, Source


def spec(identifier, component, prop, value, unit=None, name=None):
    data = {'id': identifier, 'component_type': component, 'component_name': name,
        'property_name': prop, 'numeric_value': value if isinstance(value, (int, float)) else None,
        'text_value': value if isinstance(value, str) else None, 'unit': unit,
        'sources': [{'id': identifier, 'title': 'Synthetic technical document'}]}
    data['normalized'] = normalize_spec(data)
    data['display'] = specification_display(data['normalized'])
    return data


def config(identifier, name, specs, **extra):
    return {'id': identifier, 'variant_name': name, 'display_name': name,
            'description': None, 'display_description': None, 'specifications': specs, **extra}


def profiles():
    return [config(1, 'MAME a400 — NTSC', [spec(10, 'CPU', 'Modello emulato (MAME)', '6502', name='maincpu'),
            spec(11, 'CPU', 'Frequenza emulata (MAME)', 1.79, 'MHz', 'maincpu'),
            spec(12, 'Video', 'Frequenza video emulata (MAME)', 60, 'Hz')]),
        config(2, 'MAME a400pal — PAL', [spec(20, 'CPU', 'Modello emulato (MAME)', '6502', name='maincpu'),
            spec(21, 'CPU', 'Frequenza emulata (MAME)', 1.77, 'MHz', 'maincpu'),
            spec(22, 'Video', 'Frequenza video emulata (MAME)', 50, 'Hz')]),
        config(3, 'Scheda tecnica', [spec(30, 'CPU', 'Modello', '6502'),
            spec(31, 'RAM', 'Capacità riportata', '16 - 48Kb'),
            spec(32, 'Porte', 'Joystick', '4')])]


def test_atari_one_sheet_repeated_cpu_once_scoped_clocks_and_complementary_specs():
    rows = profiles(); before = deepcopy(rows)
    sheet, = technical_sheets(rows, 'Atari 400')
    assert sheet['display_name'] == 'Scheda tecnica' and sheet['configuration_ids'] == [1, 2, 3]
    assert sheet['regional_variants'] == []
    assert rows == before and technical_sheets(list(reversed(rows)), 'Atari 400') == [sheet]
    cpu = [s for s in sheet['specifications'] if s['display']['property_name'] == 'Modello']
    assert len(cpu) == 1 and cpu[0]['text_value'] == '6502'
    assert cpu[0]['specification_ids'] == [10, 20, 30]
    assert [s['id'] for s in cpu[0]['sources']] == [10, 20, 30]
    clock = next(s for s in sheet['specifications'] if s['display']['property_name'] == 'Frequenza')
    assert clock['numeric_value'] is None and clock['text_value'] == '1.79 MHz / 1.77 MHz'
    assert [(v['numeric_value'], v['scopes']) for v in clock['display_values']] == [(1.79, []), (1.77, [])]
    assert not any(s['component_type'] == 'Video' for s in sheet['specifications'])
    assert any(s['text_value'] == '16 - 48Kb' for s in sheet['specifications'])
    assert any(s['component_type'] == 'Porte' for s in sheet['specifications'])
    assert {sid for s in sheet['specifications'] for sid in s['specification_ids']} == {s['id'] for c in rows for s in c['specifications'] if s['component_type'] != 'Video'}


def test_real_distributed_atari_records_merge_without_fabricating_missing_values():
    root = Path(__file__).resolve().parents[2]
    records = json.loads((root / 'docs/datasets/mame-0276/batch-01.json').read_text(encoding='utf-8'))['records']
    record = next(r for r in records if r['model_name'] == 'Atari 400')
    rows = []
    for i, cfg in enumerate(record['configurations'], 1):
        specs = [spec(i * 10 + j, s['component_type'], s['property_name'],
            s.get('numeric_value', s.get('text_value')), s.get('unit'), s.get('component_name'))
            for j, s in enumerate(cfg['specifications'])]
        rows.append(config(i, cfg['variant_name'], specs))
    rows.append(config(3, 'Scheda tecnica', [spec(30, 'ROM', 'Capacità riportata', '10KB')]))
    sheet, = technical_sheets(rows, 'Atari 400')
    assert len(sheet['specifications']) == 4
    assert any(s['component_type'] == 'ROM' for s in sheet['specifications'])


def test_different_ram_cpu_and_secondary_processor_roles_remain_distinct():
    rows = [config(1, 'NTSC', [spec(1, 'RAM', 'Capacità', 16, 'KiB')]),
            config(2, 'PAL', [spec(2, 'RAM', 'Capacità', 48, 'KiB')])]
    assert len(technical_sheets(rows, 'Synthetic')) == 2
    rows = [config(1, 'Base', [spec(1, 'CPU', 'Modello', 'Z80')]),
            config(2, 'Standard', [spec(2, 'CPU', 'Modello', '68000')])]
    assert len(technical_sheets(rows, 'Synthetic')) == 2
    rows = [config(1, 'Base', [spec(1, 'CPU', 'Modello', 'Z80', name='maincpu'),
            spec(2, 'CPU', 'Modello', 'Z80', name='audiocpu')])]
    assert len(technical_sheets(rows, 'Synthetic')[0]['specifications']) == 2


def test_generic_source_not_copied_to_multiple_hardware_variants_or_assigned_a_base_ram():
    rows = [config(1, 'RAM 16 KB', [spec(1, 'RAM', 'Capacità', 16, 'KB')]),
            config(2, 'RAM 48 KB', [spec(2, 'RAM', 'Capacità', 48, 'KB')]),
            config(3, 'Scheda tecnica', [spec(3, 'ROM', 'Capacità', 10, 'KB')])]
    result = technical_sheets(rows, 'Synthetic')
    assert len(result) == 3 and result[-1]['display_name'] == 'Dati generali del sistema'
    assert not any(s['component_type'] == 'ROM' for r in result[:2] for s in r['specifications'])
    rows[2]['specifications'].append(spec(4, 'RAM', 'Capacità riportata', 48, 'KB'))
    result = technical_sheets(rows, 'Synthetic')
    assert len(result) == 2 and result[1]['configuration_ids'] == [2, 3]


def test_partial_video_values_do_not_become_a_fact_for_every_standard_and_roles_stay_distinct():
    rows = [config(1, 'NTSC', [spec(1, 'Video', 'Risoluzione', '320 × 200')]), config(2, 'PAL', []),
            config(3, 'Scheda tecnica', [spec(3, 'RAM', 'Capacità massima', 48, 'KB'),
                spec(4, 'RAM', 'Capacità', 16, 'KB'), spec(5, 'RAM', 'Capacità di riferimento', 16, 'KiB')])]
    sheet, = technical_sheets(rows, 'Synthetic')
    assert sheet['specifications'][0]['text_value'] == '320 × 200'
    assert len([s for s in sheet['specifications'] if s['component_type'] == 'RAM']) == 3


def test_source_profiles_stay_with_their_approved_hardware_variant():
    rows = [config(1, 'Base', [spec(1, 'RAM', 'Capacità', 8, 'KB')], model_variant='PET 2001-B8'),
            config(2, 'Base', [spec(2, 'RAM', 'Capacità', 32, 'KB')], model_variant='PET 2001-N32'),
            config(3, 'Scheda tecnica', [spec(3, 'Porte', 'Nome', 'IEEE-488')], model_variant='PET 2001-N32')]
    result = technical_sheets(rows, 'PET 2001')
    assert len(result) == 2 and result[0]['configuration_ids'] == [1] and result[1]['configuration_ids'] == [2, 3]
    rows = rows[2:] + [config(4, 'Scheda tecnica', [spec(4, 'RAM', 'Capacità', 8, 'KB')], model_variant='PET 2001-B8')]
    assert len(technical_sheets(rows, 'PET 2001')) == 2


def test_hidden_generated_descriptions_do_not_reappear_from_the_raw_fallback():
    row = config(1, 'NTSC', [], description='Configurazione emulata MAME; registrazione: Synthetic.', display_description='')
    sheet, = technical_sheets([row], 'Synthetic')
    assert sheet['display_description'] == '' and sheet['description'] is None


def test_api_compare_and_assistant_use_one_sheet_while_editor_and_database_keep_original_ids(client):
    with SessionLocal() as db:
        computer = db.get(Computer, 1); computer.model_name = 'Atari 400'; computer.configurations.clear(); db.flush()
        for row in profiles():
            computer.configurations.append(Configuration(variant_name=row['variant_name'], specifications=[Specification(
                **{k: v for k, v in s.items() if k in ('component_type', 'component_name', 'property_name', 'numeric_value', 'text_value', 'unit')},
                sources=[Source(title=f'Technical document {s["id"]}', url=f'https://example.org/spec/{s["id"]}')]) for s in row['specifications']]))
        db.commit()
        cfg_ids = [c.id for c in computer.configurations]
        spec_ids = {s.id for c in computer.configurations for s in c.specifications}
    data = client.get('/api/computers/1').json()
    assert len(data['configurations']) == 3 and len(data['display_configurations']) == 1
    sheet = data['display_configurations'][0]
    assert sheet['configuration_ids'] == cfg_ids
    assert {sid for s in sheet['specifications'] for sid in s['specification_ids']} < spec_ids
    assert client.get('/api/compare?ids=1,2').json()[0]['display_configurations'] == [sheet]
    editor = client.get('/api/admin/computers/1').json()
    assert [c['id'] for c in editor['configurations']] == cfg_ids
    assert {s['id'] for c in editor['configurations'] for s in c['specifications']} == spec_ids
    from app.assistant_context import retrieve
    from app.main import EAGER, full
    with SessionLocal() as db:
        context = retrieve(db, 'Atari 400', EAGER, full)
        item = next(r for r in context['computers'] if r['id'] == 1)
        assert len(item['configurations']) == 1 and item['configurations'][0]['name'] == 'Scheda tecnica'
        assert all('NTSC' not in (s['text_value'] or '') for s in item['configurations'][0]['specifications'])
