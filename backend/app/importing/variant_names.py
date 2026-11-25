"""Explicit product/configuration distinctions; no fuzzy numeric suffix removal."""
import re
from .identity import maker_key
from .regional_names import regional_name
from ..catalog_names import catalog_name, video_only_variant


def variant_name(manufacturer, name):
    text = regional_name(catalog_name(name))
    if maker_key(manufacturer) == 'ibm':
        from .ibm_ps_names import commercial_name
        canonical = commercial_name(text)
        if canonical and canonical != text:
            return {'name': canonical, 'kind': 'product_configurations',
                'reason': 'Nome commerciale IBM; codice macchina e dotazione conservati nelle configurazioni e negli alias.'}
    if maker_key(manufacturer) == 'commodore':
        match = re.fullmatch(r'(?:Commodore\s+)?PET\s*2001(?:\s*-?\s*(?:[BN]\s*-?\s*(?:8|16|32)|[48]))?', text, re.I)
        if match:
            return {'name': 'PET 2001', 'kind': 'product_configurations',
                'reason': 'Varianti PET 2001: RAM, tastiera e revisione restano nelle configurazioni originali.'}
    if maker_key(manufacturer) == 'apple' and re.fullmatch(r'Apple\s+(?://c|IIc)(?:\s*\((?:rev(?:ision)?\.?\s*\d+|UniDisk\s+3\.5)\))?', text, re.I):
        return {'name': 'Apple IIc', 'kind': 'product_configurations', 'reason': 'Revisioni dello stesso Apple IIc, conservate come configurazioni; Apple IIc Plus resta distinto.'}
    if maker_key(manufacturer) in ('acorn', 'acorn computers') and re.fullmatch(r'BBC\s+Micro\s+Model\s+B\+(?:\s+(?:64|128)K)?', text, re.I):
        return {'name': 'BBC Micro Model B+', 'kind': 'product_configurations', 'reason': 'Dotazioni 64K/128K del BBC Micro Model B+ conservate come configurazioni.'}
    if catalog_name(name) != name.strip():
        return {'name': text, 'kind': 'video_standard' if video_only_variant(name) else 'catalog_attributes',
            'reason': 'Qualificatori spostati dal nome principale alle configurazioni originali; una sola scheda per modello.'}
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
