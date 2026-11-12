"""Conservative catalog vocabulary. Unknown labels/units remain explicit."""
import math
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def key(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').split()).casefold()


def component_type(value, name=None):
    aliases = {'cpu': 'CPU', 'main-cpu': 'CPU', 'processor': 'CPU', 'processore': 'CPU',
               'ram': 'RAM', 'rom': 'ROM', 'gpu': 'GPU', 'graphics-processor': 'GPU',
               'memory': 'Memoria', 'memoria': 'Memoria', 'system-memory': 'Memoria', 'unified-memory': 'RAM'}
    result = aliases.get(key(value), value)
    if result == 'Memoria':
        # A system-memory role can mean writable RAM or read-only ROM.
        rom = bool(re.search(r'\bROM\b', name or '', re.I))
        ram = bool(re.search(r'\bRAM\b', name or '', re.I))
        if rom and not ram:
            return 'ROM'
        if ram and not rom:
            return 'RAM'
    return result


def property_name(value, component):
    aliases = {'capacity': 'Capacità', 'capacità': 'Capacità', 'memory-capacity': 'Capacità',
               'clock-frequency': 'Frequenza', 'frequency': 'Frequenza', 'frequenza': 'Frequenza',
               'model': 'Modello', 'modello': 'Modello', 'processor-model': 'Modello',
               'architecture': 'Architettura', 'architettura': 'Architettura'}
    normalized = key(value)
    qualified = re.fullmatch(r'(clock-frequency|frequency|frequenza|capacity|capacità|memory-capacity)\s*\(([^)]+)\)', normalized)
    if qualified:
        base = property_name(qualified[1], component)
        part = {'performance-cores': 'core prestazioni', 'performance cores': 'core prestazioni',
                'efficiency-cores': 'core efficienza', 'efficiency cores': 'core efficienza'}.get(qualified[2], qualified[2])
        return f'{base} ({part})'
    if normalized in ('clock-frequency', 'frequency', 'frequenza') and component not in ('CPU', 'GPU'):
        return value
    return aliases.get(normalized, value)


def measurement_property(measurement):
    """Preserve named hardware parts rather than merging heterogeneous clocks."""
    name = measurement['metric']
    part = measurement.get('subject', {}).get('part')
    if part:
        part = {'performance-cores': 'core prestazioni', 'efficiency-cores': 'core efficienza'}.get(part, part)
        base = {'clock-frequency': 'Frequenza', 'memory-capacity': 'Capacità'}.get(name, name)
        return f'{base} ({part})'
    return name


def system_dates(system):
    value = system.get('releaseDate')
    if value is None:
        return {}
    if re.search(r'release date[^.]*announcement', system.get('notes') or '', re.I):
        return {'announcement_date': str(value)}
    return {'releases': [{'market': system.get('region') or 'Non specificato dalla fonte', 'release_date': str(value)}]}


def unit_name(value):
    if value is None or not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        return None
    aliases = {'kb': 'KB', 'kbyte': 'KB', 'kbytes': 'KB', 'kib': 'KiB', 'mb': 'MB',
               'mib': 'MiB', 'gb': 'GB', 'gib': 'GiB', 'mhz': 'MHz', 'khz': 'kHz',
               'ghz': 'GHz', 'hz': 'Hz', 'bytes': 'B', 'byte': 'B', 'bits': 'bit'}
    if value.casefold() in ('kb', 'mb', 'gb') and value not in ('KB', 'kB', 'MB', 'GB'):
        return value  # Lower-case b may denote bits.
    return aliases.get(value.casefold(), value)


def normalize_spec(values):
    result = dict(values)
    result['component_type'] = component_type(values.get('component_type', ''), values.get('component_name'))
    result['property_name'] = property_name(values.get('property_name', ''), result['component_type'])
    result['unit'] = unit_name(values.get('unit'))
    number = values.get('numeric_value')
    unit = result['unit']
    factors = {}
    target = unit
    if result['component_type'] in ('CPU', 'GPU') and (result['property_name'] == 'Frequenza' or result['property_name'].startswith('Frequenza (')):
        factors, target = {'Hz': '0.000001', 'kHz': '0.001', 'MHz': '1', 'GHz': '1000'}, 'MHz'
    elif result['component_type'] in ('RAM', 'ROM', 'Memoria') and (result['property_name'] == 'Capacità' or result['property_name'].startswith('Capacità (')):
        # B is exact, as are explicit IEC prefixes. Historical KB/MB/GB are not.
        factors, target = {'B': '0.0009765625', 'KiB': '1', 'MiB': '1024', 'GiB': '1048576'}, 'KiB'
    if number is not None and unit in factors:
        try:
            original = Decimal(str(number))
            converted = float(original * Decimal(factors[unit]))
            if math.isfinite(converted) and (converted != 0 or original == 0):
                result['numeric_value'], result['unit'] = converted, target
        except (InvalidOperation, OverflowError, ValueError):
            pass  # Never turn an extreme quantity into Infinity or an invented zero.
    return result


SPEC_FIELDS = ('component_type', 'component_name', 'property_name', 'numeric_value', 'text_value', 'unit')


def spec_values(spec):
    return {field: getattr(spec, field) for field in SPEC_FIELDS}


def semantic_key(values):
    normalized = normalize_spec(values)
    return key(normalized['component_type']), key(normalized['property_name'])


def quantity_equal(target, left, right):
    context = spec_values(target)
    fields = ('numeric_value', 'text_value', 'unit')
    a, b = normalize_spec({**context, **left}), normalize_spec({**context, **right})
    return all(a.get(field) == b.get(field) for field in fields)


def matching_specs(specifications, incoming):
    candidates = [s for s in specifications if semantic_key(spec_values(s)) == semantic_key(incoming)]
    named = [s for s in candidates if key(s.component_name) == key(incoming.get('component_name'))]
    if named:
        return named
    # One anonymous side can safely enrich a sole semantic match. Two distinct
    # named devices are not assumed to be interchangeable.
    if len(candidates) == 1 and (not candidates[0].component_name or not incoming.get('component_name')):
        return candidates
    if not incoming.get('component_name'):
        return candidates  # Multiple candidates must be reported as ambiguous.
    return []
