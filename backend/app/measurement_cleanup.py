"""Lossless representation changes; historical byte/bit prefixes stay distinct."""
from decimal import Decimal, InvalidOperation
import math
import re

from .importing.vocabulary import normalize_spec, unit_name
from .catalog_display import specification_display

FREQUENCIES = {'Hz': Decimal('0.000001'), 'kHz': Decimal('0.001'),
               'MHz': Decimal('1'), 'GHz': Decimal('1000')}
MEMORY = {'B': Decimal(1) / 1024, 'KiB': Decimal(1), 'MiB': Decimal(1024), 'GiB': Decimal(1048576)}
NUMBER = r'\d+(?:[.,]\d+)?'
FREQ_UNIT = r'(?:GHz|MHz|Mhz|mhz|kHz|KHz|khz|Hz|hz)'
TOKEN = re.compile(r'(?<=\d)\s*(GiB|MiB|KiB|KByte|MByte|GByte|Kbytes|Mbytes|Gbytes|bytes|byte|KB|kB|MB|GB|Kb|kb|Mb|mb|Gb|gb|B)\b')


def converted(number, factor):
    try:
        result = float(Decimal(str(number).replace(',', '.')) * factor)
        if math.isfinite(result) and (result != 0 or Decimal(str(number).replace(',', '.')) == 0):
            return result
    except (ValueError, InvalidOperation, OverflowError):
        pass
    return None


def quantity_text(value):
    """Space explicit unit tokens, without guessing whether Kb meant KB or KiB."""
    names = {'KByte':'KB', 'MByte':'MB', 'GByte':'GB', 'Kbytes':'KB', 'Mbytes':'MB', 'Gbytes':'GB', 'bytes':'B', 'byte':'B'}
    return TOKEN.sub(lambda m: ' ' + names.get(m[1], m[1]), value)


def normalize_measurement(values):
    result = dict(values)
    view = normalize_spec({**values, **specification_display(values)})
    component, prop = view['component_type'], view['property_name']
    memory = component in ('RAM', 'ROM', 'Memoria', 'Cache') and ('capacit' in prop.casefold() or 'limite' in prop.casefold())
    frequency = component in ('CPU', 'GPU') and prop in ('Frequenza', 'Frequenza riportata')
    unit = unit_name(values.get('unit'))
    number, text = values.get('numeric_value'), values.get('text_value')
    factors = FREQUENCIES if frequency else MEMORY if memory else {}
    target = 'MHz' if frequency else 'KiB'
    # A full scalar only. Ranges, options, VRAM, notes and ambiguous kb/MB stay
    # textual rather than being reduced to one invented standard configuration.
    if text and number is None and not unit:
        units = FREQ_UNIT if frequency else r'(?:GiB|MiB|KiB|B|bytes|byte)' if memory else None
        match = re.fullmatch(r'\s*(' + NUMBER + r')\s*(' + units + r')\s*', text) if units else None
        if match:
            original_unit = unit_name(match[2]); factor = factors.get(original_unit)
            value = converted(match[1], factor) if factor is not None else None
            if value is not None:
                result.update(numeric_value=value, text_value=None, unit=target)
                return result
    if number is not None and unit in factors:
        value = converted(number, factors[unit])
        if value is not None:
            result.update(numeric_value=value, unit=target)
    elif unit != values.get('unit'):
        result['unit'] = unit
    if text and component in ('RAM', 'ROM', 'Memoria', 'Cache', 'Storage', 'Floppy', 'Archiviazione'):
        result['text_value'] = quantity_text(text)
    return result


def split_cpu(value):
    """Separate only explicit trailing clocks; never infer clocks from CPU codes."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'\s*(.+?)\s+[-–—]\s+([\d.,:/\s-]+?)\s*(' + FREQ_UNIT + r')(?:\s+(' + FREQ_UNIT + r'))?\s*', value)
    if not match or (match[4] and unit_name(match[4]) != unit_name(match[3])):
        return None
    model, expression, unit = match[1].strip(), match[2].strip(), unit_name(match[3])
    scalar = re.fullmatch(NUMBER, expression)
    if scalar:
        number = converted(expression, FREQUENCIES[unit])
        if number is None:
            return None
        return model, {'property_name':'Frequenza', 'numeric_value':number, 'text_value':None, 'unit':'MHz'}
    # Expressions are retained as declared: a colon or slash is not silently
    # interpreted as a minimum/maximum, base clock or overclock option.
    if not re.fullmatch(r'\d+(?:\.\d+)?(?:\s*[-/:,]\s*\d+(?:\.\d+)?)+', expression):
        return None
    expression = re.sub(r'\s*([-/:,])\s*', r' \1 ', expression)
    return model, {'property_name':'Frequenze riportate', 'numeric_value':None, 'text_value':expression + ' ' + unit, 'unit':None}
