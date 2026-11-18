"""Reader-facing configuration and price scope from approved former model names."""
import re
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import object_session
from .import_models import ComputerAlias
from .history_sources import replaceable
from .catalog_display import description_text
from .importing.regional_names import regional_name


def annotate(computer, data):
    db = object_session(computer)
    if db is None:
        return
    compact = lambda value: re.sub(r'[^\w]', '', value).casefold()
    for alias in db.scalars(select(ComputerAlias).where(ComputerAlias.computer_id == computer.id).order_by(ComputerAlias.id)):
        original = alias.original
        for config in data['configurations']:
            if config['id'] not in original.get('configurations', []):
                continue
            variant_label = regional_name(alias.original_name)
            config['model_variant'] = variant_label
            label = config.get('display_name', config['variant_name'])
            if not compact(label).startswith(compact(variant_label)):
                config['display_name'] = variant_label + ' · ' + label
            member = next((m for m in original.get('members', [original]) if config['id'] in m.get('configurations', [])), original)
            text = member.get('description')
            if text and not replaceable(member.get('model_name', alias.original_name), member.get('manufacturer_name', computer.manufacturer.name), text):
                config['variant_description'] = description_text(text)
            if member.get('announcement_date'):
                length = {'year': 4, 'month': 7}.get(member.get('announcement_precision'), 10)
                config['variant_announcement_date'] = member['announcement_date'][:length]
        for release in data['releases']:
            if release['id'] in original.get('releases', []):
                release['model_variant'] = regional_name(alias.original_name)
        for collection in ('sales', 'reviews', 'facts'):
            for original_row, row in zip(getattr(computer, collection), data[collection]):
                if original_row.id in original.get(collection, []):
                    row['model_variant'] = regional_name(alias.original_name)


def family_attribution(computer):
    context = json.loads((Path(__file__).parent / 'importing/data/ram-reviewed-v1.json').read_text(encoding='utf-8')).get('contexts', {}).get(computer.model_name)
    if context and context['description'] == computer.description and any(s.url == context['source']['url'] for s in computer.sources):
        return {'title': 'Commodore PET', 'url': context['source']['url'],
            'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/', 'method': 'sintesi editoriale da passaggi italiani'}
    return None
