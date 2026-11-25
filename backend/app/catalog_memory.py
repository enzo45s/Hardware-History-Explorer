"""Canonical RAM facts shared by storage, API, comparisons and assistant.

Exact byte quantities can coincide; historical KB, bits and native words cannot
be equated without a source decision. Original assertion IDs are never replaced.
"""
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from functools import cmp_to_key
import json
import math
import re

EXACT = {'B': 1, 'KiB': 1024, 'MiB': 1048576, 'GiB': 1073741824}
LABEL = {'KiB': 'KB', 'MiB': 'MB', 'GiB': 'GB'}
BASE = {'capacità', 'capacità riportata', 'dotazione', 'dotazioni riportate',
        'dotazione di base', 'capacità installata', 'ram installata'}
REFERENCE = {'capacità di riferimento', 'capacità predefinita (mame)'}
UNITS = r'B|KiB|MiB|GiB|KB|kB|MB|GB|Kb|kb|Mb|mb|Gb|gb'


def clean(value):
    return ' '.join(str(value or '').split())


def compact(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def identity(value):
    return json.dumps(compact(value), ensure_ascii=False, separators=(',', ':'))


def view(spec):
    return {**spec.get('normalized', spec), **spec.get('display', {})}


def entry(values, qualifier=''):
    number, unit, text = values.get('numeric_value'), clean(values.get('unit')), clean(values.get('text_value'))
    if number is None and unit and re.fullmatch(r'\d+', text):
        number, text = int(text), ''
    if number is None:
        match = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(' + UNITS + ')', text)
        if match and (not unit or unit == match[2]):
            number, unit, text = float(match[1].replace(',', '.')), match[2], ''
    if number is not None and not math.isfinite(number):
        return None
    if number is None and not text:
        return None
    role = clean(values.get('component_name'))
    if role.casefold() in {'ram', 'mainram', 'system ram', 'memoria principale'}:
        role = ''
    byte_count = float(Decimal(str(number)) * EXACT[unit]) if number is not None and unit in EXACT else None
    exact = byte_count is not None and byte_count.is_integer() and abs(byte_count) <= 9007199254740991
    shown_number, shown_unit = number, LABEL.get(unit, unit)
    if exact:
        shown_unit, factor = next(((u, f) for u, f in [('GB', 1073741824), ('MB', 1048576), ('KB', 1024), ('B', 1)]
                                   if byte_count % f == 0), ('B', 1)) if byte_count else ('KB', 1024)
        shown_number = byte_count / factor
    shown_text = re.sub(r'\b(KiB|MiB|GiB)\b', lambda m: LABEL[m[0]], text) if number is None else ''
    if number is None and unit:
        inline = re.findall(r'\b(?:' + UNITS + r')\b', text)
        if not inline:
            shown_text += ' ' + shown_unit
        elif any(u != unit for u in inline):
            shown_text += ' (unità dichiarata: ' + shown_unit + ')'
    return {'number': number, 'unit': unit, 'text': text, 'role': role, 'qualifier': qualifier,
            'bytes': byte_count, 'shownNumber': shown_number, 'shownUnit': shown_unit, 'shownText': shown_text,
            'identity': identity([role.lower(), qualifier, ['bytes', byte_count] if exact else [number, unit, text]])}


def number_text(value):
    return format(value, '.15g')


def natural(value):
    return tuple((1, int(p)) if p.isdigit() else (0, p.casefold()) for p in re.split(r'(\d+)', value))


def memory_text(values):
    values = list({v['identity']: v for v in values}.values())
    def compare(a, b):
        left, right = natural(a['role'] + a['qualifier']), natural(b['role'] + b['qualifier'])
        if left != right:
            return (left > right) - (left < right)
        if a['bytes'] is not None and b['bytes'] is not None:
            return (a['bytes'] > b['bytes']) - (a['bytes'] < b['bytes'])
        if a['number'] is not None and b['number'] is not None and a['unit'] == b['unit']:
            return (a['number'] > b['number']) - (a['number'] < b['number'])
        render = lambda v: v['shownText'] or number_text(v['shownNumber']) + ' ' + v['shownUnit']
        left, right = natural(render(a)), natural(render(b))
        return (left > right) - (left < right)
    values.sort(key=cmp_to_key(compare))
    groups = defaultdict(list)
    for v in values:
        groups[(v['role'], v['qualifier'])].append(v)
    texts = []
    for (role, qualifier), group in groups.items():
        first = group[0]
        common = (all(v['shownNumber'] is not None and v['shownUnit'] == first['shownUnit'] for v in group)
                  and len({v['shownNumber'] for v in group}) == len(group))
        if common:
            result = ' / '.join(number_text(v['shownNumber']) for v in group) + (' ' + first['shownUnit'] if first['shownUnit'] else '')
        else:
            rendered = []
            for v in group:
                if v['shownNumber'] is None:
                    rendered.append(v['shownText']); continue
                original = v['bytes'] is None and any(other is not v and other['shownNumber'] == v['shownNumber'] and other['shownUnit'] == v['shownUnit'] for other in group)
                rendered.append(number_text(v['shownNumber']) + (' ' + v['shownUnit'] if v['shownUnit'] else '') + (' (unità originale)' if original else ''))
            result = ' / '.join(rendered)
        label = ' · '.join(v for v in (role, qualifier) if v)
        texts.append((label + ': ' if label else '') + result)
    return '; '.join(texts)


def covered(reference, capacities):
    for value in capacities:
        if value['identity'] == reference['identity']:
            return True
        if value['number'] is None and not reference['role'] and not value['role'] and not re.search(r'\b(?:VRAM|SRAM|ROM)\b', value['text'], re.I):
            for token in re.findall(r'\d+(?:[.,]\d+)?\s*(?:' + UNITS + r')\b', value['text']):
                if entry({'text_value': token})['identity'] == reference['identity']:
                    return True
    return False


def memory_specifications(specifications):
    memory = [s for s in specifications if view(s)['component_type'] == 'RAM']
    if not memory:
        return deepcopy(specifications)
    if all(s.get('catalog_clean') for s in memory) and any(s.get('catalog_metric') == 'ram.capacity' for s in memory):
        return deepcopy(specifications)
    capacities, references, options, notes, main_sources, option_sources = [], [], [], [], [], []

    def add(target, value, original, sources):
        if value:
            target.append(value); sources.append(original)

    for original in memory:
        values = view(original); prop = values['property_name']; name = clean(prop).lower()
        if original.get('catalog_clean'):
            notes.extend(original.get('memory_notes', []))
            if original.get('resolution_state') == 'reference':
                add(references, entry(values), original, main_sources)
                continue
            if original.get('resolution_state') == 'unknown':
                main_sources.append(original)
                continue
        if name in BASE:
            add(capacities, entry(values), original, main_sources)
        elif name in REFERENCE:
            add(references, entry(values), original, main_sources)
        elif re.search(r'opzioni|espansion|massim|minim|limite', name):
            qualifier = ('Limite al lancio' if re.search(r'introduzione|lancio', name) else
                         'Massima' if re.search(r'massim|limite', name) else 'Minima' if 'minim' in name else
                         '' if 'opzioni' in name else prop)
            parts = [entry({**values, 'text_value': t}, qualifier) for t in re.split(r'\s*/\s*', clean(values.get('text_value')))] if 'opzioni' in name and values.get('numeric_value') is None else []
            if len(parts) > 1 and all(v and v['number'] is not None and v['unit'] for v in parts):
                for part in parts:
                    add(options, part, original, option_sources)
            else:
                add(options, entry(values, qualifier), original, option_sources)
        else:
            value = entry(values)
            if value:
                notes.append(prop + ': ' + memory_text([value])); main_sources.append(original)
    values = capacities or references
    if not capacities and references:
        notes.append('Valore di riferimento; dotazione di base non documentata.')
    if capacities:
        distinct = [v for v in references if not covered(v, capacities)]
        if distinct:
            notes.append('Altri valori di riferimento: ' + memory_text(distinct) + '.')
    primary = list({v['identity']: v for v in values}.values())
    conflict = any(v['number'] is not None and any(other is not v and other['number'] is not None and other['role'].lower() == v['role'].lower() for other in primary) for v in primary)
    if conflict:
        notes.append('Quantità diverse riportate per questa configurazione.')
    choices = {v['identity'] for v in options if not v['qualifier']}
    extra = [v for v in options if v['qualifier'] or len(choices) > 1 or not any(v['identity'] == other['identity'] for other in values)]
    main_sources.extend(source for value, source in zip(options, option_sources) if value not in extra)

    def row(prop, entries, originals, annotations, state):
        # Several citations of the same exact quantity are one catalog value,
        # not a list of alternative configurations. Keep every original link.
        entries = list({value['identity']: value for value in entries}.values())
        fields = {'component_type': 'RAM', 'component_name': None, 'property_name': prop,
                  'numeric_value': None, 'text_value': memory_text(entries) or 'Non documentata', 'unit': None}
        ids = sorted({sid for s in originals for sid in s.get('specification_ids', [s['id']])})
        sources = {s['id']: s for original in originals for s in original.get('sources', [])}
        return {'id': 'ram-' + prop, **fields, 'normalized': fields.copy(),
                'display': {'component_type': 'RAM', 'property_name': prop},
                'memory_values': entries, 'memory_notes': list(dict.fromkeys(annotations)),
                'specification_ids': ids, 'sources': [sources[k] for k in sorted(sources)],
                'catalog_metric': 'ram.capacity' if prop == 'Capacità' else 'ram.options',
                'resolution_state': state}

    state = 'conflicting' if conflict else 'reported' if capacities else 'reference' if references else 'unknown'
    rows = [row('Capacità', values, main_sources, notes, state)]
    if extra:
        rows.append(row('Opzioni di memoria', extra, option_sources, [], 'options'))
    result = []
    for spec in specifications:
        if spec is memory[0]:
            result.extend(rows)
        elif view(spec)['component_type'] != 'RAM':
            result.append(deepcopy(spec))
    return result


def comparisons(configurations):
    """Precompute comparison cells; selection and all-variant scope stay explicit."""
    groups = {}
    for index, cfg in enumerate(configurations):
        for original in cfg['specifications']:
            spec = view(original); number = spec.get('numeric_value')
            raw = number if number is not None else clean(spec.get('text_value'))
            if raw is None or raw == '' or (number is not None and not math.isfinite(number)):
                continue
            key = identity([spec['component_type'], spec['property_name']])
            group = groups.setdefault(key, {'key': key, 'label': 'RAM' if spec['component_type'] == 'RAM' and spec['property_name'] == 'Capacità' else spec['component_type'] + ' · ' + spec['property_name'], 'values': {}, 'coverage': set(), 'notes': []})
            if 'memory_values' in original:
                group['memory'] = True
                for v in original['memory_values']:
                    group['values'][v['identity']] = v
                group['notes'].extend(original['memory_notes'])
                if original['memory_values']:
                    group['coverage'].add(index)
            else:
                unit = clean(spec.get('unit'))
                group['values'][identity([str(raw), unit])] = {'raw': raw, 'numeric': number is not None, 'unit': unit}
                group['coverage'].add(index)
    result = []
    for group in groups.values():
        values = list(group['values'].values())
        if group.get('memory'):
            display = memory_text(values) or 'Non documentata'
        else:
            one_unit = len({v['unit'] for v in values}) == 1
            values.sort(key=lambda v: (0, v['raw']) if v['numeric'] and one_unit else (1, natural(str(v['raw']) + ' ' + v['unit'])))
            render = lambda v: number_text(v['raw']) if v['numeric'] else v['raw']
            if len({v['unit'] for v in values}) == 1:
                display = ' / '.join(render(v) for v in values) + (' ' + values[0]['unit'] if values[0]['unit'] else '')
            else:
                display = ' / '.join(render(v) + (' ' + v['unit'] if v['unit'] else '') for v in values)
        count, total = len(group['coverage']), len(configurations)
        result.append({'key': group['key'], 'label': group['label'], 'text': display,
                       'notes': list(dict.fromkeys(group['notes'])), 'coverage': count, 'total': total,
                       'partial': 0 < count < total})
    return result
