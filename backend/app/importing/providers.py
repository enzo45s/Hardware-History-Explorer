"""Official exports/APIs and explicitly selected, authorized 1000bit sheets."""
import json
import re
import httpx
from .normalize import MAX_BYTES, MAX_ROWS
from .vocabulary import measurement_property, system_dates
from .wikidata_details import augment, linked_ids

USER_AGENT = 'HardwareHistoryExplorer/1.3 (https://github.com/enzo45s/Hardware-History-Explorer)'
PROVIDERS = [
    {'id': 'manual', 'name': 'CSV / JSON autorizzato', 'mode': 'upload', 'license': 'Dichiarata dall’operatore'},
    {'id': 'wikidata', 'name': 'Wikidata', 'mode': 'api', 'license': 'CC0 (dati strutturati)', 'url': 'https://www.wikidata.org/'},
    {'id': 'retroflops', 'name': 'RetroFlops', 'mode': 'api', 'license': 'CC BY 4.0 — RetroFlops; adattamento dei dati', 'url': 'https://retroflops.github.io/data/'},
    {'id': 'oldcomputers', 'name': 'Oldcomputers.net', 'mode': 'manual', 'license': 'Permessi da verificare', 'url': 'https://www.oldcomputers.net/'},
    {'id': '1000bit', 'name': '1000bit', 'mode': 'sheets', 'license': 'Autorizzazione del titolare; nessuna licenza aperta presunta', 'url': 'https://www.1000bit.it/'},
    {'id': 'computerhistory', 'name': 'Computer History Museum', 'mode': 'manual', 'license': 'Permessi da verificare', 'url': 'https://dev.computerhistory.org/'},
]


def get_json(url, params=None):
    with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False,
                      headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'}) as client:
        with client.stream('GET', url, params=params) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise ValueError('Risposta oltre 8 MB: limita il lotto')
    return bytes(content), json.loads(content)


def wikidata_date(statement):
    value = statement.get('mainsnak', {}).get('datavalue', {}).get('value', {})
    time, precision = value.get('time', ''), value.get('precision', 0)
    if value.get('calendarmodel') != 'http://www.wikidata.org/entity/Q1985727' or precision not in (9, 10, 11):
        return None
    if not re.fullmatch(r'\+\d{4}-\d{2}-\d{2}T00:00:00Z', time):
        return None
    return time[1:5] if precision == 9 else time[1:8] if precision == 10 else time[1:11]


def wikidata_records(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('entities'), dict):
        raise ValueError('Serve un JSON wbgetentities con entities e le etichette dei produttori')
    entities = payload.get('entities', {})
    def label(entity):
        labels = entity.get('labels', {})
        return next((labels[lang]['value'] for lang in ('it', 'en') if lang in labels), None)
    def active(entity, prop):
        claims = [s for s in entity.get('claims', {}).get(prop, []) if s.get('rank') != 'deprecated']
        preferred = [s for s in claims if s.get('rank') == 'preferred']
        return preferred or claims
    records = []
    requested = payload.get('requested_ids', list(entities))
    for qid in requested:
        entity = entities.get(qid, {})
        manufacturers = active(entity, 'P176')
        maker_ids = {s.get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id') for s in manufacturers}
        maker_names = [label(entities.get(i, {})) for i in maker_ids if i]
        if not label(entity) or len(maker_names) != 1 or not maker_names[0]:
            records.append({'external_id': qid, 'error': 'Nome o produttore univoco mancante in Wikidata'})
            continue
        citation = {'title': f'Wikidata — {qid}', 'url': f'https://www.wikidata.org/wiki/{qid}', 'license': 'CC0'}
        row = {'external_id': qid, 'model_name': label(entity), 'manufacturer': maker_names[0], 'source': citation,
               'evidence': 'Dati strutturati Wikidata; statement e riferimenti originali conservati nello snapshot. Nessuna verifica storica automatica.'}
        dates = [wikidata_date(s) for s in active(entity, 'P577') if not s.get('qualifiers')]
        dates = list(dict.fromkeys(d for d in dates if d))
        if len(dates) == 1:
            row['releases'] = [{'market': 'Non specificato dalla fonte', 'release_date': dates[0]}]
        # P571 (inception) is intentionally not interpreted as a commercial release.
        augment(row,entity,entities,active,label)
        records.append(row)
    return records


def retroflops_records(payload):
    if not isinstance(payload, dict) or payload.get('schemaVersion') != 'catalog-v1' or not isinstance(payload.get('systems'), list):
        raise ValueError('Serve l’esportazione completa RetroFlops catalog-v1.json')
    if len(payload['systems']) > MAX_ROWS:
        raise ValueError('Esportazione oltre 1000 sistemi: suddividi il dataset')
    records = []
    components = {c['id']: c for c in payload.get('components', [])}
    measurements = {m['id']: m for m in payload.get('measurements', [])}
    sources = {s['id']: s for s in payload.get('sources', [])}
    for system in payload['systems']:
        if system.get('type') not in ('mainframe', 'minicomputer', 'home-computer', 'personal-computer', 'workstation'):
            continue
        citation = {'title': 'RetroFlops — ' + system['name'],
                    'url': 'https://retroflops.github.io/', 'author': 'RetroFlops',
                    'license': 'CC BY 4.0; https://github.com/retroflops/retroflops — dati adattati per Hardware History Explorer'}
        row = {'external_id': system['id'], 'model_name': system['name'], 'manufacturer': system['manufacturer'],
               'categories': [system['type'].replace('-', ' ').capitalize()], 'source': citation,
               'evidence': json.dumps({'sourceIds': system.get('sourceIds', []), 'sourceRecords': [sources[i] for i in system.get('sourceIds', []) if i in sources]}, ensure_ascii=False)[:3000]}
        # Unresolved editorial markers are not publishable prose.
        prose = system.get('description') or system.get('summary')
        if prose and '{{' not in prose:
            row['description'] = prose
        row.update(system_dates(system))
        variants = []
        for cfg in system.get('configurations', []):
            specs = []
            for entry in cfg.get('entries', []):
                component = components.get(entry.get('componentId'), {})
                cpu_name = component.get('name')
                if entry.get('role') == 'main-cpu' and component.get('kind') == 'cpu' and isinstance(cpu_name, str) and cpu_name.strip():
                    # A CPU identity is useful even when its clock is unknown.
                    # Keep it as a visible sourced value; component_name alone
                    # is metadata and is not displayed as a specification.
                    specs.append({'component_type': 'CPU', 'property_name': 'Modello',
                        'text_value': cpu_name.strip(), 'source': citation,
                        'evidence': json.dumps({'component': component, 'configuration_id': cfg.get('id'),
                            'sourceRecords': [sources[i] for i in component.get('sourceIds', []) if i in sources]}, ensure_ascii=False)[:3000]})
                for mid in entry.get('measurementIds', []):
                    m = measurements.get(mid, {})
                    quantity = m.get('quantity', {})
                    if quantity.get('state') != 'value' or m.get('evidenceLevel') == 'rumored':
                        continue
                    # Preserve benchmark/method/scope; never invent aggregate performance scores.
                    specs.append({'component_type': entry.get('role', 'component'), 'component_name': component.get('name'),
                        'property_name': measurement_property(m), 'numeric_value': quantity['value'], 'unit': quantity.get('unit'),
                        'evidence': json.dumps(m, ensure_ascii=False)[:3000], 'source': citation})
            variants.append({'variant_name': cfg.get('label') or cfg['id'], 'specifications': specs})
        row['configurations'] = variants
        records.append(row)
    if not records:
        raise ValueError('Nessun calcolatore compatibile nel dataset')
    return records


def fetch_provider(provider, options):
    if provider == '1000bit':
        from .bit1000 import sheet_url, snapshot_records
        from .collect_1000bit import Collector
        urls = options.get('urls', [])
        if not 1 <= len(urls) <= 5:
            raise ValueError('Indica da 1 a 5 URL di schede 1000bit.')
        urls = [sheet_url(url) for url in urls]
        with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False,
                          headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain;q=0.9'}) as client:
            payload = Collector(client).collect(urls)
        if not payload['pages']:
            raise ValueError(payload['errors'][0]['error'] if payload['errors'] else 'Nessuna scheda recuperata.')
        return json.dumps(payload, ensure_ascii=False).encode(), snapshot_records(payload)
    if provider == 'retroflops':
        raw, payload = get_json('https://retroflops.github.io/data/catalog-v1.json')
        return raw, retroflops_records(payload)
    if provider == 'wikidata':
        ids = options.get('ids', [])
        if not 1 <= len(ids) <= 20 or any(not re.fullmatch(r'Q[1-9]\d{0,12}', q) for q in ids):
            raise ValueError('Indica da 1 a 20 identificativi Wikidata Q…')
        _, payload = get_json('https://www.wikidata.org/w/api.php', {'action': 'wbgetentities', 'ids': '|'.join(ids), 'format': 'json', 'props': 'labels|claims|descriptions', 'languages': 'it|en','maxlag':'5'})
        if 'error' in payload:
            raise ValueError('Wikidata ha rifiutato la richiesta; riprova più tardi')
        entities = payload.get('entities', {})
        related=sorted(linked_ids(entities))
        if len(related)>200:
            raise ValueError('Troppi riferimenti a componenti/unità/valute: riduci il lotto')
        for offset in range(0,len(related),50):
            _, linked = get_json('https://www.wikidata.org/w/api.php', {'action':'wbgetentities','ids':'|'.join(related[offset:offset+50]),
                'format':'json','props':'labels|claims','languages':'it|en','maxlag':'5'})
            if 'error' in linked:raise ValueError('Wikidata ha rifiutato i riferimenti: riduci il lotto e riprova')
            entities.update(linked.get('entities',{}))
        payload['requested_ids'] = ids
        raw = json.dumps(payload, ensure_ascii=False).encode()
        return raw, wikidata_records(payload)
    raise ValueError('Fonte disponibile solo tramite caricamento manuale autorizzato')


def upload_records(provider, format, raw, source_url=None):
    """One adapter path shared by upload, retry and CLI."""
    if provider == '1000bit':
        from .bit1000 import uploaded_records
        return uploaded_records(raw, format, source_url)
    if format == 'json' and provider in ('wikidata', 'retroflops'):
        payload = json.loads(raw.decode('utf-8-sig'))
        return retroflops_records(payload) if provider == 'retroflops' else wikidata_records(payload)
    return None
