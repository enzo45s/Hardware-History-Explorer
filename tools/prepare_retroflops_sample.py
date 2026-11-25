"""Build a bounded, attributed JSON sample from a local official RetroFlops clone.

Uses the backend's locked dependencies. Does not fetch documents, run upstream
code, import photos or write to a database. Git blobs preserve the exact source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import date
import yaml

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'backend'))
from app.importing.normalize import Record, MAX_BYTES  # noqa: E402
from app.importing.vocabulary import measurement_property, system_dates  # noqa: E402

REPO = 'https://github.com/retroflops/retroflops'
REVISION = 'fbbed6181149b997329854e5808e0d036ad769e2'
SYSTEMS = ('acorn-archimedes-a310', 'amiga-1200', 'amiga-4000', 'amiga-500', 'amstrad-cpc-464',
           'apple-ii', 'apple-mac-mini-m1', 'apple-mac-mini-m4', 'apple-macintosh-128k',
           'atari-520st', 'atari-800', 'bbc-micro-model-b', 'commodore-64', 'dec-pdp-8',
           'ibm-pc-5150', 'ibm-system-360-model-50', 'raspberry-pi-5', 'sgi-octane', 'zx-spectrum-48k')


def prepare(source, revision=REVISION):
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Serve un commit Git completo a 40 caratteri')
    originals = {}
    blobs = {}
    today = date.today().isoformat()

    def raw(path):
        if path not in blobs:
            blobs[path] = subprocess.check_output(['git', '-C', str(source), 'show', f'{revision}:{path}'])
        if path not in originals:
            content = blobs[path]
            originals[path] = {'path': path, 'url': f'{REPO}/blob/{revision}/{path}',
                'sha256': hashlib.sha256(content).hexdigest(), 'content_utf8': content.decode('utf-8')}
        return originals[path]['content_utf8']

    def load(path):
        return yaml.safe_load(raw(path))

    license_text = raw('LICENSE-CONTENT.md')
    if 'Creative Commons Attribution 4.0' not in license_text:
        raise ValueError('La licenza dei contenuti deve essere ricontrollata')
    paths = subprocess.check_output(['git', '-C', str(source), 'ls-tree', '-r', '--name-only', revision, 'data/canonical/components'], text=True).splitlines()
    components = {}
    for path in paths:
        if path.endswith('.yaml'):
            content = subprocess.check_output(['git', '-C', str(source), 'show', f'{revision}:{path}'])
            blobs[path] = content
            cid = yaml.safe_load(content)['id']
            if cid in components:
                raise ValueError('Identificativo componente duplicato: ' + cid)
            components[cid] = path
    exclusions = []

    def cited(ids):
        result = {}
        for sid in ids:
            if not re.fullmatch(r'[a-z0-9]+(?:[-:][a-z0-9]+)*', sid):
                raise ValueError('Identificativo fonte inatteso')
            s = load(f'data/sources/{sid}.yaml')
            result[sid] = {k: s[k] for k in ('title', 'url', 'archiveUrl', 'locator', 'sourceType') if k in s}
        return result

    def citation(title, path):
        return {'title': 'RetroFlops — ' + title, 'url': f'{REPO}/blob/{revision}/{path}',
            'author': 'RetroFlops', 'publisher': 'RetroFlops', 'source_type': 'dataset',
            'license': 'CC BY 4.0; RetroFlops, https://github.com/retroflops/retroflops; dati selezionati e adattati per Hardware History Explorer.',
            'access_date': today}

    def evidence(data, ids):
        result = json.dumps({'source_commit': revision, 'data': data, 'cited_sources': cited(ids),
            'verification': 'Dataset secondario RetroFlops; documenti primari non verificati indipendentemente in questa sessione.'}, ensure_ascii=False, default=str)
        if len(result) > 3000:
            # Complete source files stay in the snapshot, even for lengthy metadata.
            result = json.dumps({'source_commit': revision, 'data_id': data.get('id'), 'source_ids': ids,
                'note': 'Metadati completi nei file originali conservati nello snapshot.'}, ensure_ascii=False)
        return result

    records = []
    for slug in SYSTEMS:
        spath = f'data/canonical/systems/{slug}.yaml'
        mpath = f'data/canonical/measurements/{slug}.yaml'
        system = load(spath)
        measurements = {m['id']: m for m in load(mpath)}
        row = {'external_id': 'retroflops:' + slug, 'manufacturer': system['manufacturer'], 'model_name': system['name'],
            'source': citation(system['name'], spath), 'categories': [system['type'].replace('-', ' ').capitalize()],
            'evidence': evidence(system, system.get('sourceIds', [])), 'configurations': []}
        row.update(system_dates(system))
        if system.get('description') and '{{' not in system['description']:
            row['description'] = system['description']
        for cfg in system['configurations']:
            specs = []
            for entry in cfg['entries']:
                cid = entry['componentId']
                cpath = components.get(cid)
                if not cpath:
                    raise ValueError('Componente mancante: ' + cid)
                component = load(cpath)
                if entry['role'] == 'main-cpu' and component['kind'] == 'cpu':
                    specs.append({'component_type': 'CPU', 'property_name': 'Modello', 'text_value': component['name'],
                        'source': citation(system['name'] + ' — modello CPU', cpath), 'evidence': evidence(component, component.get('sourceIds', []))})
                for mid in entry.get('measurementIds', []):
                    measurement = measurements[mid]
                    quantity = measurement['quantity']
                    if quantity['state'] != 'value':
                        continue
                    if measurement.get('evidenceLevel') not in ('confirmed', 'reported'):
                        exclusions.append({'system_id': slug, 'configuration_id': cfg['id'], 'measurement_id': mid,
                            'reason': 'Livello della fonte non sufficientemente documentato: ' + str(measurement.get('evidenceLevel'))})
                        continue
                    if entry['role'] == 'main-cpu' and measurement['metric'] == 'clock-frequency' and measurement['scope'] == 'cpu':
                        ctype, prop = 'CPU', measurement_property(measurement).replace('clock-frequency', 'Frequenza')
                    elif measurement['metric'] == 'memory-capacity' and (entry['role'] == 'unified-memory' or (entry['role'] == 'system-memory' and (
                        re.search(r'\bRAM\b|random.access', component.get('memoryType', '') + ' ' + component['name'], re.I)
                    ) and not re.search(r'\bROM\b', component['name'], re.I))):
                        ctype, prop = 'RAM', measurement_property(measurement).replace('memory-capacity', 'Capacità')
                    else:
                        continue
                    specs.append({'component_type': ctype, 'property_name': prop, 'numeric_value': float(quantity['value']),
                        'unit': quantity['unit'], 'source': citation(system['name'] + ' — misure tecniche', mpath),
                        'evidence': evidence(measurement, measurement.get('sourceIds', []))})
            row['configurations'].append({'variant_name': cfg.get('label') or cfg['id'], 'specifications': specs})
        # Validate, but preserve original values/units in the distributed file.
        Record.model_validate(json.loads(json.dumps(row, default=str)))
        records.append(row)
    return {'_metadata': {'title': 'Diciannove calcolatori commerciali — campione RetroFlops',
        'source_repository': REPO, 'source_commit': revision, 'retrieved_on': today,
        'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'attribution': 'RetroFlops; https://github.com/retroflops/retroflops',
        'adaptations': ['Selezione di 19 modelli concreti; esclusi sistemi Intel di riferimento, standard MSX e categorie non pertinenti.',
            'Selezione delle denominazioni CPU e delle misure CPU/RAM documentate; esclusi valori ignoti o rumored, senza inventare dati.',
            'Frequenze di parti hardware diverse conservate separatamente; date dichiarate di annuncio non trasformate in commercializzazioni.',
            'Formato JSON canonico con originali e hash; etichette italiane, nomi e unità originali conservati; nessuna verifica automatica.'],
        'excluded_uncertain_measurements': exclusions, 'original_files': [originals[p] for p in sorted(originals)]}, 'records': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Clone locale ufficiale RetroFlops')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--revision', default=REVISION)
    args = parser.parse_args()
    data = prepare(args.source, args.revision)
    encoded = (json.dumps(data, ensure_ascii=False, indent=2, default=str) + '\n').encode()
    if len(encoded) > MAX_BYTES:
        parser.error('Snapshot oltre il limite di upload di 8 MB')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(json.dumps({'records': len(data['records']), 'configurations': sum(len(r['configurations']) for r in data['records']),
        'specifications': sum(len(c['specifications']) for r in data['records'] for c in r['configurations']),
        'original_files': len(data['_metadata']['original_files']), 'bytes': len(encoded)}))


if __name__ == '__main__':
    main()
