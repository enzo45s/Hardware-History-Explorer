"""Only explicit geographic/language qualifiers; hardware and revisions survive."""
import re

REGIONS = set('france french germany german sweden swedish finland finnish norway norwegian denmark danish uk usa us europe european japan japanese italy italian spain spanish portugal portuguese netherlands dutch canada canadian australia australian brazil brazilian russia russian ussr soviet switzerland swiss hungary hungarian argentina argentinian estonia estonian poland polish czech czechoslovakia korea korean arabic english'.split())


def geographic(value):
    return all(part.strip().casefold() in REGIONS for part in re.split(r'\s*[/&]\s*', value))


def regional_name(name):
    def group(match):
        parts = [part.strip() for part in re.split(r'[,;]', match[1])]
        remaining = [part for part in parts if not geographic(part)]
        return '(' + ', '.join(remaining) + ')' if remaining else ''
    return ' '.join(re.sub(r'\(([^()]*)\)', group, name).split()).strip()
