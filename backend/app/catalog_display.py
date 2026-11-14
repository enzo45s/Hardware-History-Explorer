"""Reader-facing vocabulary; raw import keys and historical evidence stay intact.

These aliases are deliberately separate from ETL identity/normalization rules:
two fields with the same display label must not overwrite each other's claims.
"""
import re
from collections import Counter


PROPERTY_LABELS = {
    'Modello emulato (MAME)': 'Modello',
    'Frequenza emulata (MAME)': 'Frequenza',
    'Capacità predefinita (MAME)': 'Capacità di riferimento',
    'Risoluzione emulata (MAME)': 'Risoluzione',
    'Frequenza video emulata (MAME)': 'Frequenza di aggiornamento',
    'Opzioni RAM emulatore (MAME)': 'Opzioni di memoria',
    'Chip audio emulati (MAME)': 'Chip audio',
    'Modello riportato (Wikidata)': 'Modello',
    'Nome riportato (Wikidata)': 'Nome',
    'Massa riportata (Wikidata)': 'Massa',
    'Altezza riportata (Wikidata)': 'Altezza',
    'Larghezza riportata (Wikidata)': 'Larghezza',
    'Profondità riportata (Wikidata)': 'Profondità',
    'Capacità riportata (Wikidata)': 'Capacità riportata',
}


def specification_display(values):
    return {'component_type': values['component_type'],
            'property_name': PROPERTY_LABELS.get(values['property_name'], values['property_name'])}


def description_text(value):
    if value is None:
        return None
    # Only known generated sentences are rewritten, never a global source-name
    # replacement which could change quotations or operator-written history.
    value = re.sub(r' MAME associa il modello all’anno \d{1,4}\.', '', value)
    value = value.replace('Le configurazioni emulate documentano ', 'Le configurazioni censite riportano ')
    value = value.replace('La documentazione tecnica del driver indica ', 'La documentazione tecnica indica ')
    return value


def configuration_description(value):
    if not value:
        return value
    if value.startswith('Configurazione emulata MAME; registrazione: '):
        options = re.search(r'Opzioni RAM nell’emulatore: (.+)', value)
        return 'Opzioni di memoria censite: ' + options[1] if options else ''
    if value == 'Dati dai commenti tecnici del driver; non valori dedotti dal default emulato.':
        return 'Dati ricavati dalla documentazione tecnica.'
    if value == 'Elenco delle dotazioni dichiarate negli statement, non attestazione di una singola configurazione ordinabile.':
        return 'Le dotazioni elencate possono appartenere a configurazioni diverse.'
    return value


def configuration_displays(configurations, model_name):
    """Stable, distinct labels preserve every revision and configuration ID."""
    rows = sorted(configurations, key=lambda c: c.id)
    names = []
    for c in rows:
        name = c.variant_name
        if name.startswith('MAME '):
            match = re.fullmatch(r'MAME \S+ — (.+)', name)
            name = match[1] if match else 'Configurazione di riferimento'
            if name.casefold() == model_name.casefold():
                name = 'Configurazione di riferimento'
        elif name == 'Documentazione tecnica MAME':
            name = 'Specifiche documentate'
        elif name.endswith(' · documentazione MAME'):
            name = name.removesuffix(' · documentazione MAME')
        elif name == 'AppleDB · Identificativi e architettura':
            name = 'Identificativi e architettura'
        elif name == 'Wikidata · Dotazioni riportate':
            name = 'Dotazioni documentate'
        names.append(name)
    counts, occurrences, used = Counter(names), Counter(), set()
    result = {}
    for c, name in zip(rows, names):
        occurrences[name] += 1
        label = f'{name} ({occurrences[name]})' if counts[name] > 1 else name
        # Also avoid colliding with an existing, literal numbered variant name.
        if label in used or (label != name and label in counts):
            base = label = f'{name} · #{c.id}'
            suffix = 2
            while label in used or label in counts:
                label = f'{base} ({suffix})'
                suffix += 1
        used.add(label)
        result[c.id] = {'display_name': label, 'display_description': configuration_description(c.description)}
    return result
