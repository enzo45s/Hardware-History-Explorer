"""Explicit spelling aliases only; families and individual models stay distinct."""
import re
from .normalize import name_key
from .regional_names import geographic, regional_name

# Additional country spellings used for manufacturer annotations only.
# Words identifying divisions, revisions or hardware options are never removed.
MANUFACTURER_COUNTRIES = set('''taiwan|china|hong kong|south korea|new zealand|austria|belgium|ireland|israel|singapore|india|south africa|west germany|east germany|united kingdom|united states|united states of america|soviet union|czech republic|yugoslavia|slovenia|croatia|serbia|romania|bulgaria|luxembourg|malta|turkey|greece|iceland|ukraine|lithuania|latvia|indonesia|malaysia|thailand|vietnam|mexico|chile|peru|colombia|venezuela|uruguay|u.s.a.|u.k.'''.split('|'))

MAKERS = {
    'apple': ('Apple', 'Apple Computer', 'Apple Computer Inc.', 'Apple Computer, Inc.', 'Apple Inc.'),
    'ibm': ('IBM', 'International Business Machines', 'International Business Machines Corporation'),
    'commodore': ('Commodore', 'Commodore Business Machines', 'Commodore Business Machines, Inc.', 'Commodore Business Machines (USA)'),
    'dec': ('DEC', 'Digital Equipment Corporation', 'Digital Equipment Corp.', 'Digital Equipment', 'Digital'),
    'hp': ('HP', 'Hewlett-Packard', 'Hewlett Packard', 'Hewlett-Packard Company'),
    'asem': ('ASEM', 'ASEM S.p.A.'),
    'general processor': ('General Processor', 'General Processor Srl', 'General Processor S.r.l.',
                          'General Processor (Italy)', 'General Processor (Italia)', 'GeneralProcessor'),
}
MANUFACTURERS = {name_key(alias): key for key, aliases in MAKERS.items() for alias in aliases}
MODELS = {
    'apple': (('Apple II', 'II', 'Apple ]['), ('Apple IIc', 'Apple //c'), ('Apple IIe', 'Apple //e'),
              ('Apple III', 'Apple ///'), ('Macintosh 128K', 'Apple Macintosh 128K')),
    'ibm': (('IBM PC 5150', 'IBM Personal Computer 5150', 'IBM Personal Computer Model 5150', 'PC 5150'),),
    'commodore': (('Commodore 64', 'C64'),),
    'dec': tuple((f'VAX-11/{n}', f'VAX 11/{n}', f'VAX11/{n}', f'VAX 11-{n}', f'DEC VAX-11/{n}')
                 for n in ('750','780','785')) + (('GIGI','VK100','VK-100','VK 100','DEC GIGI'),),
    'general processor': (('Child 8', 'Child8', 'General Processor Child 8'),
                          ('Child Z', 'ChildZ', 'General Processor Child Z'),
                          ('GPS4', 'GPS-4', 'GPS/4', 'General Processor GPS4'),
                          ('GPS5', 'GPS-5', 'GPS/5', 'General Processor GPS5')),
}

# Commercial spelling aliases only. Machine type/model codes deliberately stay
# separate: their ComputerAlias records retain hardware and price scopes.
from .ibm_ps_names import FAMILIES as IBM_PS_FAMILIES
MODELS['ibm'] += tuple((name, 'IBM '+name) for name in IBM_PS_FAMILIES)
MODELS['ibm'] += tuple((name, 'IBM '+name) for name in (
    'PS/1 Model 2011', 'PS/1 Model 2121', 'PS/1 Model 2133', 'PS/1 Model 2168',
    'PS/2 Note N33 SX', 'PS/2 Note N51 SX', 'PS/note 182', 'PS/note 425'))
MODELS['ibm'] += (('PS/note 425', 'ThinkPad 350', 'IBM ThinkPad 350'),)
MODELS['ibm'] += tuple((f'PS/1 Model {code}', f'PS/1 {code}', f'IBM PS/1 {code}')
                      for code in ('2011','2121','2133','2168'))
MODELS['ibm'] += tuple((f'PS/2 Note {code} SX', f'PS/2 Model {code} SX', f'IBM PS/2 Model {code} SX',
                       f'PS/2 Note {code}SX', f'IBM PS/2 Note {code}SX') for code in ('N33','N51'))


def maker_key(name):
    normalized = name_key(name)
    return MANUFACTURERS.get(normalized, normalized)


def maker_alias_keys(name):
    canonical = maker_key(name)
    return tuple(dict.fromkeys((canonical, *(name_key(v) for v in MAKERS.get(canonical, ())))))


def model_key(manufacturer, name):
    normalized = name_key(regional_name(name))
    for aliases in MODELS.get(maker_key(manufacturer), ()):
        if normalized in {name_key(alias) for alias in aliases}:
            return name_key(aliases[0])
    return normalized


def computer_key(manufacturer, model):
    return maker_key(manufacturer), model_key(manufacturer, model)


def manufacturer_base(name):
    normalized = regional_name(name_key(name))
    def annotation(match):
        parts = re.split(r'\s*[,;/&]\s*', match[1])
        country = all(part in MANUFACTURER_COUNTRIES or geographic(part) for part in parts)
        return ' ' if country else match[0]
    return ' '.join(re.sub(r'\(([^()]*)\)', annotation, normalized).split())


def provider_maker_key(provider, name):
    # 1000bit appends the manufacturer's country, e.g. Fujitsu (Japan).
    # Strip only recognized geographic annotations, never corporate divisions.
    return maker_key(manufacturer_base(name)) if provider in ('1000bit', 'historical_prices') else maker_key(name)


def provider_computer_key(provider, manufacturer, model):
    if provider not in ('1000bit', 'historical_prices'):
        return computer_key(manufacturer, model)
    maker = manufacturer_base(manufacturer)
    normalized = model_key(maker, name_key(model))
    aliases = {manufacturer_base(alias) for alias in MAKERS.get(maker_key(maker), ())}
    aliases.add(name_key(maker))
    for alias in sorted(aliases, key=len, reverse=True):
        if not alias:
            continue
        match = re.match(re.escape(alias) + r'(?=[\s:_\-\u2010-\u2015])', normalized)
        if match:
            normalized = normalized[match.end():].lstrip(' :_-\u2010\u2011\u2012\u2013\u2014\u2015')
            break
    # Formatting separators only: preserve +, /, dots, numbers and suffixes.
    # All candidates with this key must be considered, even when one is exact.
    normalized = re.sub(r'[\s_\-\u2010-\u2015]+', '', normalized)
    return provider_maker_key(provider, manufacturer), normalized


def price_model_keys(manufacturer, model):
    """Also recognize the exact legacy name export consumed by the workbook.

    The old exporter trimmed brand prefixes and leading slashes. Compare all
    resulting catalog candidates, never guess that an isolated 'c' means IIc.
    """
    keys = {provider_computer_key('historical_prices', manufacturer, model)}
    aliases = set(MAKERS.get(maker_key(manufacturer), ())) | {manufacturer}
    for alias in sorted(aliases, key=len, reverse=True):
        match = re.match(re.escape(alias) + r'(?=$|[\s:/-])', model, flags=re.I)
        if match:
            exported = model[match.end():].lstrip(' -:/')
            if exported:
                keys.add(provider_computer_key('historical_prices', manufacturer, exported))
            break
    else:
        brand = MAKERS.get(maker_key(manufacturer), (manufacturer,))[0]
        keys.add(provider_computer_key('historical_prices', manufacturer, f'{brand} {model}'))
    return keys
