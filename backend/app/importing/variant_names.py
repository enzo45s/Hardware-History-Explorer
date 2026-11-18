"""Explicit product/configuration distinctions; no fuzzy numeric suffix removal."""
import re
from .identity import maker_key
from .regional_names import regional_name


def variant_name(manufacturer, name):
    text = regional_name(name)
    if maker_key(manufacturer) == 'commodore':
        match = re.fullmatch(r'(?:Commodore\s+)?PET\s*2001(?:\s*-?\s*(?:[BN]\s*-?\s*(?:8|16|32)|[48]))?', text, re.I)
        if match:
            return {'name': 'PET 2001', 'kind': 'product_configurations',
                'reason': 'Varianti PET 2001: RAM, tastiera e revisione restano nelle configurazioni originali.'}
    # Explicit RAM notation only. Macintosh 128K/512K and model numbers such as
    # Commodore 64, HP 85B, Atari 800XL or IBM 5160 never match this rule.
    ram = re.fullmatch(r'(.+?)\s*\(\s*(?:RAM\s*[:=]?\s*)?\d+(?:[.,]\d+)?\s*(?:KiB|MiB|GiB|KB|MB|GB)\s*(?:RAM)?\s*\)', text)
    if ram:
        if re.search(r'\bRAM\b', text[text.rfind('('):], re.I):
            return {'name': ram[1].strip(), 'kind': 'ram_option', 'reason': 'Quantità RAM esplicita nel qualificatore; dati hardware conservati separatamente.'}
    if maker_key(manufacturer) == 'apple' and re.fullmatch(r'Apple\s+(?://c|IIc)(?:\s*\((?:rev(?:ision)?\.?\s*\d+|UniDisk\s+3\.5)\))?', text, re.I):
        return {'name': 'Apple IIc', 'kind': 'product_configurations', 'reason': 'Revisioni dello stesso Apple IIc, conservate come configurazioni; Apple IIc Plus resta distinto.'}
    if maker_key(manufacturer) in ('acorn', 'acorn computers') and re.fullmatch(r'BBC\s+Micro\s+Model\s+B\+(?:\s+(?:64|128)K)?', text, re.I):
        return {'name': 'BBC Micro Model B+', 'kind': 'product_configurations', 'reason': 'Dotazioni 64K/128K del BBC Micro Model B+ conservate come configurazioni.'}
    firmware = re.fullmatch(r'(.+?)\s*\(\s*(?:BIOS|ROM|firmware)\s+(?:rev(?:ision)?\.?\s*)?\d+(?:\.\d+)*[a-z]?\s*\)', text, re.I)
    if firmware:
        return {'name': firmware[1].strip(), 'kind': 'firmware', 'reason': 'Revisione esplicitamente indicata come BIOS, ROM o firmware.'}
    return None


def same_variant_family(first, second):
    a = variant_name(first.manufacturer.name, first.model_name)
    b = variant_name(second.manufacturer.name, second.model_name)
    maker = maker_key(first.manufacturer.name) == maker_key(second.manufacturer.name)
    if not maker:
        return False
    base_a = a['name'] if a else first.model_name
    base_b = b['name'] if b else second.model_name
    return bool(a or b) and base_a.casefold() == base_b.casefold()
