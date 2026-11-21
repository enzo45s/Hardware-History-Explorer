"""Read-only RAM coverage audit and guards for sourced, missing-only enrichment."""
import argparse
import json
import math
import os
from pathlib import Path
import re

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from .models import Computer, Configuration
from .importing.vocabulary import normalize_spec, spec_values
from .catalog_display import specification_display

MODE = 'missing_ram_only'
UNITS = {'B', 'KB', 'kB', 'KiB', 'MB', 'MiB', 'GB', 'GiB',
         'Kb', 'kb', 'Mb', 'mb', 'Gb', 'gb', 'word', 'words', 'parole'}
QUANTITY = re.compile(r'\d+(?:[.,]\d+)?\s*(?:[kKmMgG]i?[bB]|bytes?|[kK]?words?|parole)\b')


def documented_ram(values):
    """Presence of a stated quantity, not proof of its historical correctness.

    An ambiguous Kb still documents a quantity; it is never converted to KiB.
    CPU clocks, ROM, VRAM, slot counts and unitless '1M/4M' are not RAM sizes.
    """
    values = normalize_spec(values)
    view = {**values, **specification_display(values)}
    if view['component_type'] != 'RAM':
        return False
    prop = view['property_name'].casefold()
    if not any(word in prop for word in ('capacit', 'dotazion', 'opzioni', 'limite')):
        return False
    number = view.get('numeric_value')
    if number is not None:
        return math.isfinite(number) and number > 0 and view.get('unit') in UNITS
    text = view.get('text_value') or ''
    # Do not fill a missing system RAM field with a video/ROM-only statement.
    if re.search(r'\b(?:VRAM|ROM)\b', text, re.I):
        text = re.split(r'\s*[+,;]\s*', text)[0]
        if re.search(r'\b(?:VRAM|ROM)\b', text, re.I):
            return False
    return bool(QUANTITY.search(text))


def has_documented_ram(computer):
    return any(documented_ram(spec_values(s)) for c in computer.configurations for s in c.specifications)


def validate_enrichment(data):
    """A RAM-only package cannot mutate other parts of the catalog."""
    forbidden = ('external_id', 'description', 'categories', 'announcement_date',
                 'releases', 'sales', 'reviews', 'facts')
    if any(data.get(field) for field in forbidden):
        raise ValueError('Il pacchetto RAM può contenere solo specifiche RAM di sistemi esistenti.')
    specs = [s for cfg in data.get('configurations', []) for s in cfg.get('specifications', [])]
    if not specs or any(not documented_ram(s) or not s.get('source') or not s.get('evidence') for s in specs):
        raise ValueError('Ogni quantità RAM richiede una fonte e un’evidenza; ROM e VRAM sono escluse.')
    if any(cfg.get('description') for cfg in data.get('configurations', [])):
        raise ValueError('Il pacchetto RAM non modifica le descrizioni delle configurazioni.')


def coverage(db):
    rows = db.scalars(select(Computer).order_by(Computer.id).options(
        selectinload(Computer.manufacturer),
        selectinload(Computer.configurations).selectinload(Configuration.specifications))).all()
    missing = [{'manufacturer': c.manufacturer.name, 'model_name': c.model_name}
               for c in rows if not has_documented_ram(c)]
    return {'computers': len(rows), 'with_documented_ram': len(rows) - len(missing),
            'without_documented_ram': len(missing), 'missing': missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    url = os.getenv('DATABASE_URL')
    if not url:
        parser.error('DATABASE_URL deve indicare esplicitamente il database.')
    engine = create_engine(url)
    with Session(engine) as db:
        result = coverage(db)
        with args.output.open('x', encoding='utf-8') as out:
            json.dump(result, out, ensure_ascii=False, indent=2)
        print(json.dumps({key: value for key, value in result.items() if key != 'missing'}))
    engine.dispose()


if __name__ == '__main__':
    main()
