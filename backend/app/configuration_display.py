"""Regional technical-profile summaries without changing stored configurations."""
from collections import Counter, defaultdict
from copy import deepcopy

from .geography import european_configuration, geographic_key


SPEC_FIELDS = ('component_type', 'component_name', 'property_name', 'numeric_value', 'text_value', 'unit')


def spec_key(spec):
    normalized = spec.get('normalized') or spec
    return tuple(normalized.get(field) for field in SPEC_FIELDS)


def description_key(row):
    text = (row.get('display_description', row.get('description')) or '').strip()
    prefix = 'Opzioni di memoria censite: '
    if text.startswith(prefix):
        return prefix, tuple(sorted(part.strip() for part in text[len(prefix):].split(',')))
    return text


def configuration_summaries(configurations, model_name):
    groups = {}
    for row in sorted(deepcopy(configurations), key=lambda item: item['id']):
        region = european_configuration(row['variant_name'], model_name)
        signature = ('single', row['id'])
        if region:
            label, countries = region
            signature = ('europe', geographic_key(label), description_key(row),
                         tuple(sorted(Counter(spec_key(spec) for spec in row['specifications']).items(), key=repr)))
            row['display_name'] = label
            row['display_region'] = 'Europa'
            row['countries'] = list(countries)
        if signature not in groups:
            row['configuration_ids'] = [row['id']]
            for spec in row['specifications']:
                spec['specification_ids'] = [spec['id']]
            groups[signature] = row
            continue
        target = groups[signature]
        target['configuration_ids'].append(row['id'])
        target['countries'] = sorted(set(target['countries']) | set(countries))
        # Match repeated, identical components by occurrence, preserving multiplicity.
        originals = defaultdict(list)
        for spec in row['specifications']:
            originals[spec_key(spec)].append(spec)
        for spec in target['specifications']:
            original = originals[spec_key(spec)].pop(0)
            spec['specification_ids'].append(original['id'])
            sources = {source['id']: source for source in spec['sources'] + original['sources']}
            spec['sources'] = [sources[identifier] for identifier in sorted(sources)]

    rows = list(groups.values())
    counts = Counter(row.get('display_name', row['variant_name']) for row in rows)
    occurrences, used = Counter(), set()
    for row in rows:
        name = row.get('display_name', row['variant_name'])
        occurrences[name] += 1
        label = f'{name} ({occurrences[name]})' if counts[name] > 1 else name
        if label in used or (label != name and label in counts):
            label = f'{name} · #{row["id"]}'
        row['display_name'] = label
        used.add(label)
    return rows
