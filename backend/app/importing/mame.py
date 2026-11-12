"""Conservative extraction of licensed MAME registration/configuration metadata.

Registration declarations identify computer entries; the official -listxml
export supplies resolved quantities. Emulator data stays explicitly separate
from independently documented hardware values. Neither parser executes C++.
"""
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

LICENSES = {'BSD-3-Clause', 'BSD-2-Clause', 'GPL-2.0+', 'LGPL-2.1+', 'CC0-1.0'}
REJECT = re.compile(r'prototype|\bproto\b|\bhomebrew\b|\bhack\b|\bmodified\b|\boverclock|\btrainer\b|development|evaluation|\bterminal\b|\bprinter\b|\bcalculator\b|\bdisk drive\b|\bcontroller\b|\bupgrade\b|\bexpansion\b|\btest board\b|\bmotherboard\b|\bcpu board\b', re.I)
EXCLUDED_DRIVERS = {
    'pippin.cpp', 'vis.cpp', 'hp48.cpp', 'hp49g.cpp', 'hp49gp.cpp', 'hp38g.cpp', 'hp39gii.cpp',
    'hp16500.cpp', 'hp2620.cpp', 'hp2640.cpp', 'hp64k.cpp', 'hpz80unk.cpp',
    'dct11em.cpp', 'dectalk.cpp', 'dtc03.cpp', 'decwritr.cpp', 'vk100.cpp',
    'vt100.cpp', 'vt220.cpp', 'vt240.cpp', 'vt320.cpp', 'vt62.cpp', 'ibm3477.cpp',
    'pve500.cpp', 'celint2k.cpp', 'minitel_2_rpic.cpp', 'agvision.cpp', 'piet1.cpp',
    'c900.cpp', 'dgnalpha.cpp', 'dgn_beta.cpp', 'chloe.cpp', 'reutapm.cpp', 'pentevo.cpp', 'tsconf.cpp',
}
REGIONS = {'pal', 'ntsc', 'usa', 'us', 'uk', 'europe', 'european', 'japan', 'japanese', 'germany', 'german',
           'france', 'french', 'spain', 'spanish', 'sweden', 'swedish', 'norway', 'norwegian', 'finland', 'finnish',
           'denmark', 'danish', 'italy', 'italian', 'australia', 'australian', 'canada', 'canadian', 'korea', 'korean',
           'brazil', 'brazilian', 'russia', 'russian', 'arabic', 'international', 'netherlands', 'dutch', 'portugal', 'portuguese',
           'msx', 'msx1', 'msx2', 'msx2+', 'msx turbo r'}


def uncomment(source):
    pattern = re.compile(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*[\s\S]*?\*/')
    return pattern.sub(lambda m: m[0] if m[1] else re.sub(r'[^\n]', ' ', m[0]), source)


def closing(text, start, left='(', right=')'):
    depth, quote, escape = 0, None, False
    for i in range(start, len(text)):
        char = text[i]
        if quote:
            if escape: escape = False
            elif char == '\\': escape = True
            elif char == quote: quote = None
            continue
        if char == '"' or (char == "'" and not (i > 0 and i + 1 < len(text) and text[i-1].isdigit() and text[i+1].isdigit())):
            quote = char; continue
        if char == left: depth += 1
        elif char == right:
            depth -= 1
            if depth == 0: return i
    raise ValueError('Delimitatori non bilanciati')


def arguments(text):
    result, start, depth, quote, escape = [], 0, 0, False, False
    for i, char in enumerate(text):
        if quote:
            if escape: escape = False
            elif char == '\\': escape = True
            elif char == '"': quote = False
        elif char == '"': quote = True
        elif char in '([{': depth += 1
        elif char in ')]}': depth -= 1
        elif char == ',' and depth == 0: result.append(text[start:i].strip()); start = i + 1
    return result + [text[start:].strip()]


def quoted(text):
    if not re.fullmatch(r'"(?:\\.|[^"\\])*"', text.strip()):
        raise ValueError('Stringa C++ composta o dinamica non supportata')
    return json.loads(text.strip())


def conditional_lines(text):
    """Unknown build branches are not treated as active registrations/configs."""
    result, depth = set(), 0
    for line, value in enumerate(text.splitlines(), 1):
        directive = re.match(r'\s*#\s*(if|ifdef|ifndef|endif|else|elif)\b', value)
        if directive and directive[1] in ('if', 'ifdef', 'ifndef'): depth += 1
        if depth: result.add(line)
        if directive and directive[1] == 'endif': depth = max(0, depth - 1)
    return result


def model_label(description):
    variants = []
    def replace(match):
        parts = [p.strip().casefold() for p in re.split(r'[,;]', match[1])]
        if all(p in REGIONS or re.fullmatch(r'(?:rom|bios)\s*\d+[a-z]*', p) for p in parts):
            variants.append(match[1]); return ''
        return match[0]
    name = re.sub(r'\(([^()]*)\)', replace, description)
    firmware = re.search(r'\s*/\s*(\d+(?:st|nd|rd|th) released version)\s*$', name, re.I)
    if firmware: variants.append(firmware[1]); name = name[:firmware.start()]
    return ' '.join(name.split()).strip(), variants


def registrations(path, text):
    license_match = re.search(r'license:\s*([^\s]+)', text[:400])
    license_name = license_match[1] if license_match else ''
    author = re.search(r'copyright-holders:\s*([^\n]+)', text[:1500])
    clean, accepted, excluded = uncomment(text), [], []
    conditional = conditional_lines(clean)
    for match in re.finditer(r'^\s*COMP\s*\(', clean, re.M):
        macro_start = clean.index('COMP', match.start())
        line = clean.count('\n', 0, macro_start) + 1
        try:
            if line in conditional: raise ValueError('Registrazione in ramo di compilazione condizionale: revisione manuale')
            end = closing(clean, clean.index('(', match.start()))
            args = arguments(clean[clean.index('(', match.start()) + 1:end])
            if len(args) != 11: raise ValueError('COMP non standard')
            year, short, parent, compat, config, inputs, owner, init, maker, description, flags = args
            maker, description = quoted(maker), quoted(description)
            if license_name not in LICENSES: raise ValueError('Licenza del file non inclusa nel pacchetto')
            if path.rsplit('/', 1)[-1] in EXCLUDED_DRIVERS: raise ValueError('Dispositivo fuori ambito')
            if re.search(r'\b(?:CDTV|CD32)\b|Emulators ID|\btrial\b|\bBRNO mod\b', description, re.I): raise ValueError('Console, prova o variante non commerciale')
            if not re.fullmatch(r'[a-z][a-z0-9_]*', short): raise ValueError('Identificativo dinamico')
            if REJECT.search(description) or 'MACHINE_UNOFFICIAL' in flags: raise ValueError('Prototipo, modifica o dispositivo fuori ambito')
            if maker.casefold() in ('unknown', '<unknown>', 'homebrew', '?', ''): raise ValueError('Produttore non identificato')
            label, variants = model_label(description)
            if description.startswith('ZX Spectrum Next: KS'):
                label, variants = 'ZX Spectrum Next', [description.split(': ', 1)[1]]
            accepted.append({'shortname': short, 'parent': parent, 'year': year, 'config': config, 'owner': owner,
                'manufacturer': maker, 'name': label, 'description': description, 'variants': variants,
                'flags': flags, 'path': path, 'line': line, 'original': text[macro_start:end + 1].strip(),
                'license': license_name, 'author': author[1].strip() if author else 'MAME contributors'})
        except (ValueError, json.JSONDecodeError) as exc:
            excluded.append({'path': path, 'line': line, 'reason': str(exc)})
    return accepted, excluded


PROCESSOR_NAMES = re.compile(r'\b(?:6502|6510|8502|7501|8501|65C02|65C816|Z80|Z180|Z8001|Z8002|8080|8085|8086|8088|80186|80286|80386|80486|Pentium|MC?680[012346]0|6809|HD6309|PowerPC|MIPS|R[2345]\d{3}|ARM[0-9]*|SPARC|NS32016|NS32032|TMS9900|PDP-11|DEC T-11)\b', re.I)


def positive_integer(text):
    return int(text) if isinstance(text, str) and re.fullmatch(r'\d{1,18}', text) and int(text) > 0 else None


def read_export(path, names, expected_build):
    """Stream the official XML; keep only selected machine metadata, never ROMs."""
    path = Path(path)
    with path.open('rb') as source:
        header = source.read(65536)
    if b'<!ENTITY' in header or re.search(rb'<!DOCTYPE[^>]*\b(?:SYSTEM|PUBLIC)\s+[\"\']', header, re.S):
        raise ValueError('Entità e DTD esterni non ammessi')
    result, build = {}, None
    for event, element in ET.iterparse(path, events=('start', 'end')):
        if event == 'start' and build is None:
            if element.tag != 'mame': raise ValueError('Serve l’esportazione XML ufficiale MAME')
            build = element.get('build', '')
            if build.split(' ', 1)[0] != expected_build:
                raise ValueError('Versione XML e revisione sorgente non corrispondono')
        if event == 'end' and element.tag == 'machine':
            name = element.get('name')
            if name in names and element.get('runnable', 'yes') == 'yes' and element.get('isdevice', 'no') == 'no' and element.get('isbios', 'no') == 'no':
                result[name] = {'attributes': dict(element.attrib), 'description': element.findtext('description'),
                    'year': element.findtext('year'), 'manufacturer': element.findtext('manufacturer'),
                    'chips': [dict(chip.attrib) for chip in element.findall('chip') if chip.get('type') == 'cpu'],
                    'ram_options': [{'attributes': dict(r.attrib), 'bytes': r.text or ''} for r in element.findall('ramoption')],
                    'driver': dict(element.find('driver').attrib) if element.find('driver') is not None else {}}
            element.clear()
    return build, result


def exported_configuration(machine):
    chips = machine['chips']
    preferred = [c for c in chips if c.get('tag', '').lstrip(':') in ('maincpu', 'main_cpu', 'cpu')]
    # Some processors use physical board labels (e.g. C64 U7). MAME also marks
    # peripheral CIAs/DMA/video chips as "cpu", so type alone is insufficient.
    processors = preferred or [c for c in chips if ':' not in c.get('tag', '').lstrip(':') and PROCESSOR_NAMES.search(c.get('name', ''))]
    defaults = [r for r in machine['ram_options'] if r['attributes'].get('default') == 'yes' and positive_integer(r['bytes'])]
    ram = defaults[0] if len(defaults) == 1 else None
    return processors, ram
