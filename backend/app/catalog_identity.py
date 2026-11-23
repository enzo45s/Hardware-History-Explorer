"""Shared catalog identities and placeholder recognition; no network research."""
import re
import unicodedata
from .catalog_display import description_text
from .catalog_names import catalog_name
from .importing.identity import provider_computer_key, manufacturer_base, MAKERS, MODELS, maker_key

def maker_aliases(maker):
    """Research spellings only; never change catalog manufacturer identities."""
    # Remove legal suffixes only, not arbitrary words or company divisions.
    legal = r'(?:incorporated|inc|corporation|corp|limited|ltd|plc|gmbh|s\.?p\.?a\.?)'
    without_legal = lambda value: re.sub(r'(?:[\s,.]+' + legal + r'[\s,.]*)+$', '', value.strip(), flags=re.I).strip()
    short = without_legal(maker)
    compact = lambda value: re.sub(r'[^\w]', '', without_legal(manufacturer_base(value)))
    groups = [aliases for key, aliases in MAKERS.items() if key != 'dec'] + [
        ('DEC', 'Digital Equipment Corporation', 'Digital Equipment'),
        ('NeXT', 'NeXT Inc.', 'NeXT Computer Inc.', 'Next Software Inc', 'NeXT Software, Inc.'),
        ('HP', 'Hewlett-Packard', 'Hewlett Packard'),
        ('Acorn', 'Acorn Computers', 'Acorn Computers Ltd.'),
        ('Atari', 'Atari Inc.', 'Atari, Inc.', 'Atari Corporation'),
        ('Sinclair', 'Sinclair Research', 'Sinclair Research Ltd.'),
        ('Sun', 'Sun Microsystems', 'Sun Microsystem'),
        ('Kaypro', 'Kaypro Corporation', 'Kaypro Corp.'),
        ('EACA', 'EACA Computers'),
    ]
    aliases = next((aliases for aliases in groups if {compact(maker), compact(short)} & {compact(a) for a in aliases}), (short or maker.strip(),))
    return tuple(dict.fromkeys((*aliases, maker.strip())))


def model_names(model, maker):
    """Short research title and unbranded model, retaining hardware suffixes."""
    canonical, aliases = canonical_model(model, maker), maker_aliases(maker)
    title = core = canonical
    while True:
        for alias in sorted(aliases, key=len, reverse=True):
            if not alias:
                continue
            # NeXTcube/NeXTstation are actual joined product names. Do not
            # strip arbitrary substrings (e.g. Sun in Sunrise).
            boundary = r'(?=$|[\s:/-]|\d)'
            if alias.casefold() == 'next':
                boundary = r'(?=$|[\s:/-]|\d|cube\b|station\b|computer\b)'
            match = re.match(re.escape(alias) + boundary, core, flags=re.I)
            if match and core[match.end():].lstrip(' -:/'):
                remainder = core[match.end():]
                title = core if alias.casefold() == 'next' and not remainder.startswith(' ') else aliases[0] + ' ' + remainder.lstrip(' -:/')
                core = remainder.lstrip(' -:/')
                break
        else:
            return title, core


def canonical_model(model, maker):
    text = catalog_name(unicodedata.normalize('NFKC', model).strip())
    if maker_key(maker_aliases(maker)[0]) == 'apple':
        # Catalog names use the Macintosh product line; Italian article titles
        # use PowerBook. Keep every numeric/color/Duo suffix intact.
        text = re.sub(r'^Macintosh\s+(?=PowerBook\b)', '', text, flags=re.I)
    spelling = lambda value: re.sub(r'[\s-]+', '', value).casefold()
    for aliases in MODELS.get(maker_key(maker_aliases(maker)[0]), ()):
        if spelling(text) in {spelling(a) for a in aliases}:
            return aliases[0]
    return text


def replaceable(model, maker, value):
    """Only missing text and the exact old generated template are eligible."""
    if not (value or '').strip():
        return True
    text = description_text(value).strip()
    category = r'(?:un (?:calcolatore|home computer|personal computer|computer portatile|minicalcolatore|mainframe|microcomputer|supercomputer)|una workstation)'
    pattern = re.escape(model) + r' è ' + category + r' di ' + re.escape(maker) + r'\.(?: Le configurazioni censite riportano [^\n.!?]+\.)?'
    return re.fullmatch(pattern, text) is not None


def model_key(maker, model):
    # Research uses the public model name; hardware variants remain in the
    # catalog's configurations and original records, not in search queries.
    title = re.sub(r'\s*\((?:computer|informatica|home computer|personal computer)\)$', '', model, flags=re.I)
    _, title = model_names(title, maker)
    maker = maker_aliases(maker)[0]
    # HP's full corporate spelling is common in Italian article titles.
    if maker.casefold() in ('hp', 'hewlett-packard', 'hewlett packard'):
        maker = 'HP'
        title = re.sub(r'^Hewlett[ -]Packard\b', 'HP', title, flags=re.I)
    return provider_computer_key('historical_prices', maker, title)

