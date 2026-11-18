"""Conservative geographic Europe aliases, independent of EU membership.

Country labels with partly Asian territory are intentionally not mapped without
a more precise location. Languages, currencies and PAL/NTSC are not geography.
"""
import re
import unicodedata


def geographic_key(value):
    text = unicodedata.normalize('NFKD', value or '').casefold()
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return ' '.join(re.sub(r'[._]', ' ', text).split())


EUROPE_ALIASES = {
    'Europa': ('Europe', 'European market', 'European version', 'European'),
    'Albania': ('AL', 'ALB'),
    'Andorra': ('AD', 'AND'),
    'Austria': ('AT', 'AUT'),
    'Belgio': ('Belgium', 'Belgique', 'BE', 'BEL'),
    'Bielorussia': ('Belarus', 'BY', 'BLR'),
    'Bosnia-Erzegovina': ('Bosnia and Herzegovina', 'Bosnia ed Erzegovina', 'Bosnia', 'BA', 'BIH'),
    'Bulgaria': ('BG', 'BGR'),
    'Cechia': ('Czechia', 'Czech Republic', 'Repubblica Ceca', 'CZ', 'CZE'),
    'Cecoslovacchia': ('Czechoslovakia', 'CS', 'CSK'),
    'Croazia': ('Croatia', 'HR', 'HRV'),
    'Danimarca': ('Denmark', 'DK', 'DNK'),
    'Estonia': ('EE', 'EST'),
    'Finlandia': ('Finland', 'FI', 'FIN'),
    'Francia': ('France', 'FR', 'FRA'),
    'Germania': ('Germany', 'Deutschland', 'DE', 'DEU', 'West Germany', 'East Germany',
                 'Germania Ovest', 'Germania Est', 'GDR', 'FRG', 'DD', 'DDR'),
    'Grecia': ('Greece', 'GR', 'GRC'),
    'Irlanda': ('Ireland', 'Republic of Ireland', 'IE', 'IRL'),
    'Islanda': ('Iceland', 'IS', 'ISL'),
    'Italia': ('Italy', 'IT', 'ITA'),
    'Kosovo': ('XK', 'XKX'),
    'Lettonia': ('Latvia', 'LV', 'LVA'),
    'Liechtenstein': ('LI', 'LIE'),
    'Lituania': ('Lithuania', 'LT', 'LTU'),
    'Lussemburgo': ('Luxembourg', 'LU', 'LUX'),
    'Macedonia del Nord': ('North Macedonia', 'Macedonia', 'MK', 'MKD'),
    'Malta': ('MT', 'MLT'),
    'Moldavia': ('Moldova', 'Republic of Moldova', 'MD', 'MDA'),
    'Monaco': ('MC', 'MCO'),
    'Montenegro': ('ME', 'MNE'),
    'Norvegia': ('Norway', 'NO', 'NOR'),
    'Paesi Bassi': ('Netherlands', 'The Netherlands', 'Holland', 'Olanda', 'NL', 'NLD'),
    'Polonia': ('Poland', 'PL', 'POL'),
    'Portogallo': ('Portugal', 'PT', 'PRT'),
    'Regno Unito': ('United Kingdom', 'UK', 'U.K.', 'U K', 'GB', 'GBR', 'Great Britain', 'Britain',
                    'Gran Bretagna', 'England', 'Inghilterra', 'Scotland', 'Scozia', 'Wales', 'Galles',
                    'Northern Ireland', 'Irlanda del Nord'),
    'Romania': ('RO', 'ROU'),
    'San Marino': ('SM', 'SMR'),
    'Serbia': ('RS', 'SRB'),
    'Serbia e Montenegro': ('Serbia and Montenegro', 'SCG'),
    'Slovacchia': ('Slovakia', 'SK', 'SVK'),
    'Slovenia': ('Slovenia', 'SI', 'SVN'),
    'Spagna': ('Spain', 'España', 'Espana', 'ES', 'ESP'),
    'Svezia': ('Sweden', 'SE', 'SWE'),
    'Svizzera': ('Switzerland', 'CH', 'CHE'),
    'Ucraina': ('Ukraine', 'UA', 'UKR'),
    'Ungheria': ('Hungary', 'HU', 'HUN'),
    'Vaticano': ('Vatican City', 'Holy See', 'Città del Vaticano', 'VA', 'VAT'),
    'Jugoslavia': ('Yugoslavia', 'YU', 'YUG'),
    'Gibilterra': ('Gibraltar', 'GI', 'GIB'),
    'Isole Faroe': ('Faroe Islands', 'Færøerne', 'FO', 'FRO'),
    'Isola di Man': ('Isle of Man', 'IM', 'IMN'),
    'Jersey': ('JE', 'JEY'),
    'Guernsey': ('GG', 'GGY'),
    'Isole Åland': ('Åland Islands', 'Aland', 'AX', 'ALA'),
}
EUROPE = {geographic_key(alias): country for country, aliases in EUROPE_ALIASES.items()
          for alias in (country, *aliases)}


def european_countries(value, *, allow_codes=True):
    """Return recognized countries, only when the whole geographic label qualifies."""
    text = geographic_key(value)
    # In configuration names AT/SE/ME can mean hardware editions, not countries.
    def admitted(alias):
        compact = re.sub(r'\W', '', alias)
        return alias in EUROPE and (allow_codes or len(compact) > 3 or compact in {'uk', 'gb'})
    if admitted(text):
        return (EUROPE[text],)
    parts = re.split(r'\s*(?:/|,|;|\+|&|\band\b|\be\b)\s*', text)
    if len(parts) > 1 and all(admitted(part) for part in parts):
        return tuple(sorted({EUROPE[part] for part in parts}))
    return ()


def european_configuration(name, model_name):
    """Recognize regional labels without erasing revision/keyboard qualifiers."""
    name = re.sub(r'^MAME \S+ — ', '', name).strip()
    direct = european_countries(name, allow_codes=False)
    if direct:
        return 'Europa', direct
    parenthesized = re.fullmatch(r'(.+?)\s*\(([^()]*)\)', name)
    base = parenthesized[1].strip() if parenthesized else ''
    parts = [part.strip() for part in (parenthesized[2] if parenthesized else name).split(',')]
    countries, qualifiers = set(), []
    if base and european_countries(base, allow_codes=False):
        countries.update(european_countries(base, allow_codes=False))
        base = ''
    for part in parts:
        recognized = european_countries(part, allow_codes=False)
        if recognized:
            countries.update(recognized)
        elif re.match(r'^(?:MSX[12]\b|ROM\b|BIOS\b|Rev(?:ision)?\b|Version\b|Enhanced\b|Platinum\b|UniDisk\b|AZERTY\b|QWERTY\b|QWERTZ\b|Keyboard\b|PAL\b|NTSC\b|SECAM\b)', part, re.I):
            qualifiers.append(part)
        else:
            return None
    if not countries:
        return None
    if base and geographic_key(base) != geographic_key(model_name):
        qualifiers.insert(0, base)
    label = 'Europa' + (' · ' + ', '.join(qualifiers) if qualifiers else '')
    return label, tuple(sorted(countries))
