"""Only operator-approved former model names resolve to a consolidated record."""
from sqlalchemy import select
from ..models import Computer
from ..import_models import ComputerAlias
from .identity import provider_computer_key, maker_alias_keys, manufacturer_base
from .normalize import name_key


def alias_for(db, manufacturer, model, computer_id=None):
    maker, name = provider_computer_key('historical_prices', manufacturer, model)
    candidates = db.scalars(select(ComputerAlias).where(ComputerAlias.manufacturer_key.in_(maker_alias_keys(maker)), ComputerAlias.model_key == name).order_by(ComputerAlias.id)).all()
    if len({a.computer_id for a in candidates}) > 1:
        raise ValueError('Nome precedente ambiguo dopo la normalizzazione del produttore: controlla gli abbinamenti.')
    original_key = name_key(manufacturer_base(manufacturer))
    alias = min(candidates, key=lambda a:(a.manufacturer_key != original_key, a.manufacturer_key != maker, a.id)) if candidates else None
    if alias is None or (computer_id is not None and alias.computer_id != computer_id):
        return None
    computer = db.get(Computer, alias.computer_id)
    if computer is None or provider_computer_key('historical_prices', computer.manufacturer.name, computer.model_name)[0] != maker:
        return None
    return alias


def remember(db, computer, canonical_id):
    maker, name = provider_computer_key('historical_prices', computer.manufacturer.name, computer.model_name)
    alias = db.scalar(select(ComputerAlias).where(ComputerAlias.manufacturer_key == maker, ComputerAlias.model_key == name))
    if alias and alias.computer_id != canonical_id:
        raise ValueError('Un nome della variante è già associato a un altro sistema.')
    original = {field: getattr(computer, field) for field in ('model_name', 'description', 'announcement_precision')}
    original['computer_id'] = computer.id
    original['manufacturer_name'] = computer.manufacturer.name
    original['announcement_date'] = computer.announcement_date.isoformat() if computer.announcement_date else None
    for collection in ('configurations', 'releases', 'sales', 'reviews', 'facts'):
        original[collection] = [row.id for row in getattr(computer, collection)]
    original['configuration_names'] = {str(cfg.id): cfg.variant_name for cfg in computer.configurations}
    if alias is None:
        alias = ComputerAlias(manufacturer_key=maker, model_key=name, original_name=computer.model_name,
                              computer_id=canonical_id, original=original)
        db.add(alias); db.flush()
    else:
        prior = alias.original
        alias.original = {**prior, 'members': prior.get('members', [{k: v for k, v in prior.items() if k != 'members'}]) + [original],
            'configuration_names': {**prior.get('configuration_names', {}), **original['configuration_names']}}
        alias.original = {**alias.original, **{key: list(dict.fromkeys(prior.get(key, []) + original[key]))
            for key in ('configurations', 'releases', 'sales', 'reviews', 'facts')}}
    return alias


def remember_input(db, computer, record):
    """The configured generic naming rule also applies to new imports.

    Keep variant-specific fields and IDs scoped exactly as for a reviewed legacy
    merge. Import claims remain pending; this does not verify historical data.
    """
    from ..admin import historical_date
    maker, name = provider_computer_key('historical_prices', record['manufacturer'], record['model_name'])
    day, precision = historical_date(record['announcement_date']) if record.get('announcement_date') else (None, None)
    original = {'computer_id': computer.id, 'model_name': record['model_name'],
        'manufacturer_name': record['manufacturer'], 'description': record.get('description'),
        'announcement_date': day.isoformat() if day else None, 'announcement_precision': precision,
        'configurations': [], 'configuration_names': {}, 'releases': [], 'sales': [], 'reviews': [], 'facts': [],
        'naming_rule': 'catalog_attributes_v1'}
    alias = ComputerAlias(manufacturer_key=maker, model_key=name, original_name=record['model_name'],
        computer_id=computer.id, original=original)
    db.add(alias); db.flush()
    return alias


def assertion_variant(db, claim):
    if db is None or claim.computer_id is None:
        return None
    from ..import_models import ImportRow
    cache = db.info.setdefault('variant_claim_scopes', {})
    key = (claim.row_id, claim.computer_id)
    if key not in cache:
        row = db.get(ImportRow, claim.row_id)
        record = row.normalized if row else None
        alias = alias_for(db, record.get('manufacturer', ''), record.get('model_name', ''), claim.computer_id) if record else None
        from .regional_names import regional_name
        cache[key] = regional_name(alias.original_name) if alias else None
    return cache[key]
