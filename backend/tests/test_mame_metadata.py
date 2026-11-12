"""Synthetic licensed registrations and official-shaped XML, never historical facts."""
import pytest
from app.importing.mame import registrations, model_label, read_export, exported_configuration, positive_integer
from app.importing.normalize import Spec

HEADER = '// license:BSD-3-Clause\n// copyright-holders:Synthetic test author\n'


def test_registration_keeps_unknown_year_original_license_and_quoted_commas():
    source = HEADER + '// COMP(1980, ignored)\nCOMP(19??, test, 0, 0, base, keys, test_state, empty_init, "Test, Inc.", "Test Computer (PAL)", 0)\n'
    good, bad = registrations('src/mame/test.cpp', source)
    assert not bad and len(good) == 1
    item = good[0]
    assert item['year'] == '19??' and item['manufacturer'] == 'Test, Inc.'
    assert item['license'] == 'BSD-3-Clause' and item['line'] == 4
    assert item['name'] == 'Test Computer' and item['variants'] == ['PAL']
    assert item['original'].startswith('COMP(19??')


@pytest.mark.parametrize('description,flags,path', [('Prototype computer', '0', 'test.cpp'),
    ('Synthetic terminal', '0', 'test.cpp'), ('Synthetic computer', 'MACHINE_UNOFFICIAL', 'test.cpp'),
    ('Commodore 900', '0', 'c900.cpp'), ('HP-2622A', '0', 'hp2620.cpp'), ('CDTV (PAL)', '0', 'amiga.cpp')])
def test_noncommercial_or_out_of_scope_registrations_are_logged(description, flags, path):
    source = HEADER + f'COMP(1980, test, 0, 0, base, keys, test_state, empty_init, "Test Maker", "{description}", {flags})'
    good, bad = registrations(path, source)
    assert not good and len(bad) == 1


def test_hardware_model_qualifiers_are_not_removed_as_firmware():
    assert model_label('System/360 Model 50') == ('System/360 Model 50', [])
    assert model_label('Macintosh SE (FDHD)') == ('Macintosh SE (FDHD)', [])
    assert model_label('System (ROM03)') == ('System', ['ROM03'])
    assert model_label('FS-A1FX (MSX2+, Japan)') == ('FS-A1FX', ['MSX2+, Japan'])


def test_conditional_registration_and_unlicensed_file_are_not_assumed_available():
    source = HEADER + '#if 0\nCOMP(1980, disabled, 0, 0, base, keys, test_state, empty_init, "Test", "Not active", 0)\n#endif'
    good, bad = registrations('one.cpp', source)
    assert not good and 'condizionale' in bad[0]['reason']
    good, bad = registrations('one.cpp', 'COMP(1980, unknown, 0, 0, base, keys, test_state, empty_init, "Test", "Unknown licence", 0)')
    assert not good and 'Licenza' in bad[0]['reason']


def test_official_export_retains_raw_values_and_excludes_devices(tmp_path):
    path = tmp_path / 'test.xml'
    path.write_text('''<?xml version="1.0"?><mame build="0.276 (test)">
<machine name="test" sourcefile="synthetic/test.cpp" runnable="yes" isdevice="no">
<description>Test computer</description><year>19??</year><manufacturer>Test maker</manufacturer>
<chip type="cpu" tag="maincpu" name="Synthetic processor" clock="4000000" />
<chip type="cpu" tag="cia" name="Synthetic peripheral" clock="4000000" />
<ramoption name="16K">16384</ramoption><ramoption name="48K" default="yes">49152</ramoption>
<driver status="imperfect" /></machine>
<machine name="device" runnable="no" isdevice="yes"><description>Peripheral</description></machine>
</mame>''')
    build, machines = read_export(path, {'test', 'device'}, '0.276')
    assert build == '0.276 (test)' and set(machines) == {'test'}
    machine = machines['test']
    assert machine['year'] == '19??' and machine['driver']['status'] == 'imperfect'
    cpus, ram = exported_configuration(machine)
    assert len(cpus) == 1 and cpus[0]['name'] == 'Synthetic processor'
    assert ram['bytes'] == '49152' and positive_integer(ram['bytes']) / 1024 == 48
    with pytest.raises(ValueError, match='Versione'):
        read_export(path, {'test'}, '0.277')


def test_board_tags_do_not_promote_video_or_dma_chips_to_system_processors():
    machine = {'chips': [{'type': 'cpu', 'tag': 'u7', 'name': 'MOS Technology 6510', 'clock': '1022727'},
        {'type': 'cpu', 'tag': 'u19', 'name': 'MOS 6567 VIC-II', 'clock': '1022727'},
        {'type': 'cpu', 'tag': 'iec8:fdcpu', 'name': 'MOS Technology 6502', 'clock': '1000000'}], 'ram_options': []}
    cpus, ram = exported_configuration(machine)
    assert [c['tag'] for c in cpus] == ['u7'] and ram is None


@pytest.mark.parametrize('raw', ['0', '-1', 'unknown', '1e20', '9' * 1000])
def test_unknown_or_invalid_quantities_are_not_invented(raw):
    assert positive_integer(raw) is None


def test_xml_entities_are_rejected_and_model_text_is_never_parsed_as_quantity(tmp_path):
    path = tmp_path / 'unsafe.xml'
    path.write_text('<!DOCTYPE mame [<!ENTITY x SYSTEM "file:///etc/passwd">]><mame build="0.276">&x;</mame>')
    with pytest.raises(ValueError, match='Entità'):
        read_export(path, set(), '0.276')
    spec = Spec(component_type='CPU', property_name='Modello emulato (MAME)', text_value='6800 CPU')
    assert spec.text_value == '6800 CPU' and spec.numeric_value is None
