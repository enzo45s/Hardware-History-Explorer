"""A technical sheet describes hardware, not the source that supplied a field.

This is a read-only projection. Original configurations, claims and IDs remain
available to the editor and ETL, including contradictory source values.
"""
from collections import defaultdict
from copy import deepcopy
import re

from .catalog_display import specification_display
from .configuration_display import configuration_summaries
from .geography import european_countries
from .importing.regional_names import REGIONS
from .importing.vocabulary import normalize_spec


GENERIC = {'', 'base', 'standard', 'scheda tecnica', 'specifiche documentate',
    'documentazione tecnica mame', 'configurazione di riferimento',
    'appledb · identificativi e architettura', 'wikidata · dotazioni riportate',
    'identificativi e architettura', 'dotazioni documentate'}
SUPPLEMENTS = GENERIC - {'', 'base', 'standard', 'configurazione di riferimento'}
STANDARDS = {'pal', 'ntsc', 'secam', 'pal-b', 'pal-m', 'pal-n', 'ntsc-j'}


def key(value):
    return ' '.join((value or '').split()).casefold()


def profile(row, model):
    name = re.sub(r'^MAME \S+ — ', '', row['variant_name']).strip()
    name = name.removesuffix(' · documentazione MAME')
    scope = ''
    supplement = key(name) in SUPPLEMENTS
    # A regional or television-standard label alone is not a hardware option.
    remaining = name
    if key(name) == key(model):
        remaining = ''
    elif key(name).startswith(key(model) + ' '):
        remaining = name[len(model):].strip()
    qualifier = remaining.strip('() ')
    parts = [part.strip() for part in re.split(r'[,;/]', qualifier)]
    if parts and all(key(p) in STANDARDS | REGIONS or european_countries(p, allow_codes=False) for p in parts):
        scope = ', '.join(p.upper() if key(p) in STANDARDS else p for p in parts)
        remaining = ''
    if key(remaining) in GENERIC:
        remaining = ''
    if row.get('display_region'):
        scope = row['display_region'] + (' · ' + scope if scope else '')
    return {'family': row.get('model_variant') or key(remaining), 'label': remaining,
            'scope': scope, 'supplement': supplement}


def fields(spec):
    normalized = spec.get('normalized') or spec
    view = normalize_spec({**normalized, **specification_display(normalized), **spec.get('display', {})})
    # The generic main processor label and an unnamed main CPU are equivalent;
    # named secondary CPUs and other repeated components retain their own roles.
    role = key(view.get('component_name'))
    if view['component_type'] == 'CPU' and role in ('maincpu', 'main-cpu', 'cpu'):
        role = ''
    return view, (view['component_type'], role, view['property_name'])


def value_key(view):
    text = ' '.join((view.get('text_value') or '').split()) or None
    return view.get('numeric_value'), text, view.get('unit') or None


def hardware(row, info):
    result = defaultdict(set)
    for spec in row['specifications']:
        view, slot = fields(spec)
        component, role, prop = slot
        substantial = (component in ('CPU', 'GPU') and prop in ('Modello', 'Architettura'))
        substantial |= component in ('RAM', 'ROM', 'Memoria', 'Memoria di massa', 'Tastiera', 'Storage')
        # Lists, bounds and uncertain units are reported facts, not a base option.
        if component in ('RAM', 'ROM', 'Memoria'):
            substantial = prop in ('Capacità', 'Capacità di riferimento', 'Capacità riportata') and view.get('numeric_value') is not None
            if substantial:
                slot = (component, role, 'Capacità')
        # PAL/NTSC clock differences are shown as scoped values in one sheet.
        if component == 'CPU' and prop == 'Frequenza' and not re.search(r'\b(?:PAL|NTSC|SECAM)\b', info['scope']):
            substantial = True
        if substantial:
            result[slot].add(value_key(view))
    return result


def compatible(first, second):
    return all(not (first[slot] and second[slot]) or first[slot] == second[slot]
               for slot in first.keys() & second.keys())


def text_value(value):
    number = value.get('numeric_value')
    text = format(number, '.15g') if number is not None else value.get('text_value') or ''
    return text + (' ' + value['unit'] if value.get('unit') else '')


def sheet(members, model, count):
    first = deepcopy(members[0][0])
    ids = sorted({cid for row, _ in members for cid in row.get('configuration_ids', [row['id']])})
    first['configuration_ids'], first['id'] = ids, ids[0]
    label = next((row.get('model_variant') or info['label'] for row, info in members
                  if row.get('model_variant') or info['label']), '')
    first['display_name'] = 'Scheda tecnica' if count == 1 else label or 'Configurazione'
    first.pop('display_region', None)
    first.pop('countries', None)
    # Never silently retain just the first profile's notes or announcement.
    notes = []
    for row, info in members:
        for field in ('variant_description', 'variant_announcement_date', 'display_description'):
            text = row.get(field)
            if text and text not in notes:
                notes.append(text)
    first['display_description'] = '\n'.join(notes)
    first['description'] = first['display_description'] or None
    first.pop('variant_description', None)
    first.pop('variant_announcement_date', None)
    slots = {}
    scopes = {info['scope'] for _, info in members if info['scope']}
    first['regional_variants'] = sorted(scopes)
    for row, info in members:
        occurrences = defaultdict(int)
        for spec in row['specifications']:
            view, base = fields(spec)
            # Keep physical repeated components with the same role/multiplicity.
            occurrences[base] += 1
            slot = (*base, occurrences[base])
            entry = slots.setdefault(slot, {'spec': deepcopy(spec), 'view': view, 'values': {}})
            value = entry['values'].setdefault(value_key(view), {
                'numeric_value': view.get('numeric_value'), 'text_value': view.get('text_value'),
                'unit': view.get('unit'), 'scopes': [], 'sources': [], 'specification_ids': [], 'unscoped': False})
            value['unscoped'] |= not bool(info['scope'])
            if info['scope'] and info['scope'] not in value['scopes']:
                value['scopes'].append(info['scope'])
            value['specification_ids'].extend(spec.get('specification_ids', [spec['id']]))
            source_map = {s['id']: s for s in value['sources'] + spec.get('sources', [])}
            value['sources'] = [source_map[sid] for sid in sorted(source_map)]
    specs = []
    for slot, entry in slots.items():
        values = list(entry['values'].values())
        projected = []
        for value in values:
            value['scopes'].sort()
            value['specification_ids'] = sorted(set(value['specification_ids']))
            scoped = bool(value['scopes']) and (len(values) > 1 or (not value['unscoped'] and set(value['scopes']) != scopes))
            projected.append(text_value(value) + (' (' + ', '.join(value['scopes']) + ')' if scoped else ''))
        view = dict(entry['view'])
        if len(values) != 1 or projected[0] != text_value(values[0]):
            view.update(numeric_value=None, text_value=' / '.join(projected), unit=None)
        spec = entry['spec']
        spec.update(numeric_value=view.get('numeric_value'), text_value=view.get('text_value'), unit=view.get('unit'))
        spec['normalized'] = view
        spec['display'] = {k: view[k] for k in ('component_type', 'property_name')}
        if slot[1]:
            spec['display']['property_name'] += ' (' + slot[1] + ')'
        spec['display_values'] = [{k: v for k, v in value.items() if k != 'unscoped'} for value in values]
        spec['specification_ids'] = sorted({sid for value in values for sid in value['specification_ids']})
        sources = {s['id']: s for value in values for s in value['sources']}
        spec['sources'] = [sources[sid] for sid in sorted(sources)]
        specs.append(spec)
    first['specifications'] = specs
    return first


def technical_sheets(configurations, model_name):
    rows = configuration_summaries(configurations, model_name)
    groups, supplements = [], []
    for row in rows:
        info = profile(row, model_name)
        if info['supplement']:
            supplements.append((row, info)); continue
        signature = hardware(row, info)
        group = next((g for g in groups if g['family'] == info['family'] and compatible(g['hardware'], signature)), None)
        if group is None:
            group = {'family': info['family'], 'hardware': defaultdict(set), 'members': []}
            groups.append(group)
        group['members'].append((row, info))
        for slot, values in signature.items():
            group['hardware'][slot].update(values)
    general = defaultdict(list)
    for row, info in supplements:
        signature = hardware(row, info)
        candidates = [g for g in groups if not row.get('model_variant') or g['family'] == info['family']]
        matches = [g for g in candidates if compatible(g['hardware'], signature) and g['hardware'].keys() & signature.keys()]
        group = candidates[0] if len(candidates) == 1 else matches[0] if len(matches) == 1 else None
        if group:
            group['members'].append((row, info))
        else:
            general[row.get('model_variant') or ''].append((row, info))
    for family, members in general.items():
        groups.append({'members': members, 'general': not bool(family)})
    result = [sheet(g['members'], model_name, len(groups)) for g in groups]
    for row, group in zip(result, groups):
        if group.get('general') and len(groups) > 1:
            row['display_name'] = 'Dati generali del sistema'
    # Distinct hardware can have the same regional/generic name. Prefer an actual
    # capacity/model in the label to anonymous numbered source blocks.
    labels = defaultdict(list)
    for row in result:
        labels[row['display_name']].append(row)
    for label, repeated in labels.items():
        if len(repeated) > 1:
            for index, row in enumerate(repeated, 1):
                amounts = [text_value(s.get('normalized', s)) for s in row['specifications']
                           if s['component_type'] == 'RAM' and s.get('numeric_value') is not None]
                row['display_name'] = label + ' · ' + (', '.join(amounts) + ' RAM' if amounts else str(index))
    return result
