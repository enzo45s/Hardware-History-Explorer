"""Human-readable import decisions; original IDs/values remain in the API."""
from datetime import date
from sqlalchemy.orm import object_session
from ..models import Computer, Configuration, Specification, Release, Sale, Review, Fact, Manufacturer, Market, Category
from .vocabulary import normalize_spec, spec_values, quantity_equal

TARGETS = {model.__name__: model for model in (Computer, Configuration, Specification, Release, Sale, Review, Fact)}
ENTITIES = {'Computer': 'Calcolatore', 'Configuration': 'Configurazione', 'Specification': 'Specifica tecnica',
            'Release': 'Commercializzazione', 'Sale': 'Vendite', 'Review': 'Recensione', 'Fact': 'Informazione storica'}
FIELDS = {'manufacturer_id': 'Produttore', 'market_id': 'Mercato', 'category': 'Categoria', 'model_name': 'Nome del modello',
          'description': 'Descrizione', 'announcement_date': 'Data di annuncio', 'variant_name': 'Nome configurazione',
          'quantity': 'Valore della specifica', 'price_bundle': 'Prezzo e valuta', 'review_score': 'Punteggio e scala',
          'sales_quantity': 'Quantità venduta', 'release_date': 'Data di lancio', 'discontinuation_date': 'Fine commercializzazione',
          'numeric_value': 'Valore numerico', 'text_value': 'Valore testuale', 'unit': 'Unità', 'component_type': 'Componente',
          'component_name': 'Nome componente', 'property_name': 'Proprietà', 'publication': 'Pubblicazione',
          'review_date': 'Data recensione', 'summary': 'Sintesi', 'statement': 'Testo', 'fact_type': 'Tipo informazione',
          'reference_date': 'Data di riferimento', 'period_start': 'Inizio periodo', 'period_end': 'Fine periodo'}
REFERENCES = {'manufacturer_id': Manufacturer, 'market_id': Market, 'category': Category}
PRECISION = {'announcement_date': 'announcement_precision', 'release_date': 'release_precision', 'discontinuation_date': 'discontinuation_precision'}
BUNDLES = {'quantity': ('numeric_value', 'text_value', 'unit'), 'price_bundle': ('price', 'currency', 'price_type'),
           'review_score': ('score', 'max_score'), 'sales_quantity': ('units_sold', 'estimated', 'metric_type')}


def text(value):
    if value is None:
        return 'Non indicato'
    if isinstance(value, bool):
        return 'Sì' if value else 'No'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def current_value(claim, target):
    if target is None:
        return None
    if claim.field == 'category':
        return {'value': claim.value.get('value')} if any(c.id == claim.value.get('value') for c in target.categories) else {'value': None}
    if claim.field in BUNDLES:
        return {field: getattr(target, field) for field in BUNDLES[claim.field]}
    value = getattr(target, claim.field)
    result = {'value': value.isoformat() if isinstance(value, date) else value}
    if claim.field in PRECISION:
        result['precision'] = getattr(target, PRECISION[claim.field])
    return result


def format_value(db, claim, values, target):
    if values is None:
        return 'Elemento non più disponibile'
    if claim.field in REFERENCES:
        value = values.get('value')
        if value is None:
            return 'Non indicato'
        reference = db.get(REFERENCES[claim.field], value)
        return reference.name if reference else f'Voce non più disponibile (ID {value})'
    if claim.field == 'quantity':
        quantity = normalize_spec({**spec_values(target), **values}) if target else values
        value = quantity.get('numeric_value') if quantity.get('numeric_value') is not None else quantity.get('text_value')
        return text(value) + (' ' + quantity['unit'] if quantity.get('unit') else '')
    if claim.field == 'price_bundle':
        return text(values.get('price')) + (' ' + values['currency'] if values.get('currency') else '') + (' · ' + values['price_type'] if values.get('price_type') else '')
    if claim.field == 'review_score':
        return text(values.get('score')) + ' / ' + text(values.get('max_score'))
    if claim.field == 'sales_quantity':
        return text(values.get('units_sold')) + (' (stima)' if values.get('estimated') else '')
    value = values.get('value')
    if value and claim.field in PRECISION:
        return value[:4] if values.get('precision') == 'year' else value[:7] if values.get('precision') == 'month' else value
    return text(value)


def claim_presentation(claim):
    db = object_session(claim)
    target = db.get(TARGETS[claim.entity], claim.target_id)
    computer = db.get(Computer, claim.computer_id) if claim.computer_id else None
    context = computer.model_name if computer else 'Scheda non più disponibile'
    field_label = FIELDS.get(claim.field, claim.field.replace('_', ' '))
    if target is not None and claim.entity == 'Specification':
        spec = normalize_spec(spec_values(target))
        field_label = f"{spec['component_type']} · {spec['property_name']}" if claim.field == 'quantity' else field_label
        context += ' · ' + target.configuration.variant_name
    elif target is not None and claim.entity == 'Configuration':
        context += ' · ' + target.variant_name
    current = current_value(claim, target)
    expected = claim.previous if claim.status == 'conflict' else claim.value
    stale = claim.computer_id is None or current is None or (not quantity_equal(target, current, expected) if claim.field == 'quantity' else current != expected)
    return {'entity_label': ENTITIES[claim.entity], 'field_label': field_label, 'context': context,
            'proposed': format_value(db, claim, claim.value, target),
            'previous': format_value(db, claim, claim.previous, target),
            'current': format_value(db, claim, current, target), 'stale': stale}
