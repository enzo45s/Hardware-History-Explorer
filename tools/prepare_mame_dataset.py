"""Reproducible, bounded computer metadata batches from the official MAME Git tree.

No MAME code is executed, no ROM is downloaded, no database is changed.
Registration years and emulator configurations are secondary, unverified data.
"""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'backend'))
from app.importing.mame import registrations, read_export, exported_configuration, positive_integer  # noqa: E402
from app.importing.normalize import Record, MAX_BYTES, name_key  # noqa: E402
from app.importing.identity import maker_key  # noqa: E402

REPOSITORY = 'https://github.com/mamedev/mame'
REVISION = '758c8a169a44f0ce3abfd28e8b5c44cc49148eba'
MAME_BUILD = '0.276'
PLATFORMS = tuple('acorn amstrad amiga apple atari commodore dec epson fujitsu heathzenith hp ibm kaypro mits msx nec next olivetti osborne philips sanyo sgi sharp sinclair sony sun thomson toshiba trs enterprise memotech samcoupe svi camputers sord tatung tangerine nascom morrow'.split())
PC_FILES = {'ibmpc.cpp', 'ibmpcjr.cpp', 'pc.cpp', 'pc_t1t.cpp', 'tandy1t.cpp', 'tosh1000.cpp', 'europc.cpp', 'compc.cpp', 'ps2.cpp'}
LEGAL = {'BSD-3-Clause': 'BSD-3-Clause', 'BSD-2-Clause': 'BSD-2-Clause', 'GPL-2.0+': 'GPL-2.0',
         'LGPL-2.1+': 'LGPL-2.1', 'CC0-1.0': 'CC0'}
MAKERS = {'apple': 'Apple', 'ibm': 'IBM', 'commodore': 'Commodore', 'dec': 'Digital Equipment Corporation',
          'acorn': 'Acorn', 'acorn computers': 'Acorn', 'acorn computers ltd': 'Acorn',
          'sinclair': 'Sinclair', 'sinclair research': 'Sinclair', 'sinclair research ltd': 'Sinclair',
          'tandy radio shack': 'Tandy', 'tandy': 'Tandy', 'radio shack': 'Tandy',
          'hewlett packard': 'Hewlett-Packard', 'hewlett-packard': 'Hewlett-Packard',
          'sun microsystems': 'Sun Microsystems', 'sun microsystems, inc.': 'Sun Microsystems',
          'sony': 'Sony', 'sony corporation': 'Sony', 'sharp': 'Sharp', 'sharp corporation': 'Sharp'}


def git(source, *arguments):
    return subprocess.check_output(['git', '-C', str(source), *arguments])


def write_coverage(output, records):
    def cell(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    with (output / 'coverage.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream, delimiter=';', lineterminator='\n')
        writer.writerow(['external_id', 'produttore', 'nome', 'anni_MAME', 'CPU_emulate', 'clock_emulati_MHz', 'RAM_predefinite_MAME_KiB', 'configurazioni', 'prezzi_presenti'])
        for record in records:
            specs = [s for cfg in record['configurations'] for s in cfg['specifications']]
            def values(property_name, field):
                return ' | '.join(sorted({str(s[field]) for s in specs if s['property_name'] == property_name}))
            writer.writerow(map(cell, [record['external_id'], record['manufacturer'], record['model_name'],
                ' | '.join(sorted({r['release_date'] for r in record['releases']})),
                values('Modello emulato (MAME)', 'text_value'), values('Frequenza emulata (MAME)', 'numeric_value'),
                values('Capacità predefinita (MAME)', 'numeric_value'), len(record['configurations']), 'no']))


def prepare(source, xml, output, revision=REVISION, batch_size=250, distribution='Non specificata dall’operatore'):
    if not re.fullmatch(r'[a-f0-9]{40}', revision): raise ValueError('Indica un commit Git completo')
    if revision != REVISION: raise ValueError('Questo generatore richiede il commit ufficiale mame0276 indicato nel codice, coerente con XML 0.276')
    if not 1 <= batch_size <= 250: raise ValueError('Dimensione lotto: 1–250')
    paths = git(source, 'ls-tree', '-r', '--name-only', revision, 'src/mame').decode().splitlines()
    paths = [p for p in paths if (p.split('/')[2] in PLATFORMS or (p.split('/')[2] == 'pc' and p.rsplit('/', 1)[-1] in PC_FILES)) and p.endswith(('.cpp', '.h'))]
    originals = {path: git(source, 'show', f'{revision}:{path}').decode() for path in paths}
    legal = {key: git(source, 'show', f'{revision}:docs/legal/{path}').decode() for key, path in LEGAL.items()}
    legal['MAME-COPYING'] = git(source, 'show', f'{revision}:COPYING').decode()
    accepted, excluded = [], []
    for path, text in originals.items():
        if path.endswith('.cpp'):
            good, bad = registrations(path, text); accepted.extend(good); excluded.extend(bad)
    build, exported = read_export(xml, {r['shortname'] for r in accepted}, MAME_BUILD)
    compiled = []
    for entry in accepted:
        machine = exported.get(entry['shortname'])
        if machine is None or 'src/mame/' + machine['attributes'].get('sourcefile', '') != entry['path']:
            excluded.append({'path': entry['path'], 'line': entry['line'], 'reason': 'Registrazione assente o origine diversa nell’export XML corrispondente'})
            continue
        if machine['description'] != entry['description'] or machine['manufacturer'] != entry['manufacturer'] or machine['year'] != entry['year']:
            excluded.append({'path': entry['path'], 'line': entry['line'], 'reason': 'Metadati XML e sorgente divergenti: revisione richiesta'})
            continue
        compiled.append(entry)
    accepted = compiled
    groups = defaultdict(list)
    aliases = {}
    for entry in accepted:
        maker = MAKERS.get(maker_key(entry['manufacturer']), entry['manufacturer'])
        aliases[entry['manufacturer']] = maker
        entry['canonical_manufacturer'] = maker
        if len(entry['name']) > 180:
            excluded.append({'path': entry['path'], 'line': entry['line'], 'reason': 'Nome oltre 180 caratteri'}); continue
        groups[(name_key(maker), name_key(entry['name']))].append(entry)
    today = date.today().isoformat()

    def citation(title, path, line):
        text = originals[path]; license_name = re.search(r'license:\s*(\S+)', text[:400])[1]
        return {'title': 'MAME — ' + title[:280], 'url': f'{REPOSITORY}/blob/{revision}/{path}#L{line}',
                'author': 'MAMEdev and contributors', 'publisher': 'MAME', 'source_type': 'dataset',
                'license': f'{license_name}; copyright e testi di licenza conservati nel blocco _metadata del lotto.', 'access_date': today}

    records, audits, coverage = [], [], Counter()
    for key, entries in sorted(groups.items()):
        entries.sort(key=lambda e: e['shortname'])
        root = entries[0]
        record = {'external_id': 'mame:' + root['shortname'], 'manufacturer': root['canonical_manufacturer'], 'model_name': root['name'],
            'categories': ['Calcolatore'], 'source': citation(root['name'], root['path'], root['line']),
            'evidence': 'Metadati di registrazione MAME. Fonte tecnica secondaria; commercializzazione, anno e hardware non verificati indipendentemente.',
            'configurations': [], 'releases': []}
        raw, used, release_years = [], set(), set()
        model_coverage = set()
        for entry in entries:
            used.add(entry['path']); raw.append({'kind': 'registration', **entry})
            machine = exported[entry['shortname']]
            processors, ram = exported_configuration(machine)
            raw[-1]['xml_metadata'] = machine
            label = f"MAME {entry['shortname']} — " + ('; '.join(entry['variants']) or entry['description'])
            if len(label) > 140: label = f"MAME {entry['shortname']} (configurazione emulata)"
            cfg = {'variant_name': label, 'description': f"Configurazione emulata MAME; registrazione: {entry['description']}. Anno dichiarato: {entry['year']}. Non attesta opzioni ordinabili.",
                   'source': citation(entry['description'], entry['path'], entry['line']), 'specifications': []}
            for cpu in processors:
                proof = json.dumps({'mame_build': build, 'machine': entry['shortname'], 'chip': cpu,
                    'note': 'Tipo e clock risolti da MAME -listxml, non verifica del chip montato nel calcolatore reale.'}, ensure_ascii=False)
                cfg['specifications'].append({'component_type': 'CPU', 'component_name': cpu['tag'], 'property_name': 'Modello emulato (MAME)',
                    'text_value': cpu['name'], 'source': citation(entry['description'] + ' — CPU emulata', entry['path'], entry['line']), 'evidence': proof})
                model_coverage.add('models_with_cpu')
                hz = positive_integer(cpu.get('clock'))
                if hz and hz <= 1000000000000:
                    cfg['specifications'].append({'component_type': 'CPU', 'component_name': cpu['tag'], 'property_name': 'Frequenza emulata (MAME)',
                        'numeric_value': hz / 1e6, 'unit': 'MHz', 'source': citation(entry['description'] + ' — clock emulato', entry['path'], entry['line']), 'evidence': proof})
                    model_coverage.add('models_with_frequency')
            if ram:
                cfg['specifications'].append({'component_type': 'RAM', 'property_name': 'Capacità predefinita (MAME)', 'numeric_value': positive_integer(ram['bytes']) / 1024, 'unit': 'KiB',
                    'source': citation(entry['description'] + ' — RAM emulata', entry['path'], entry['line']),
                    'evidence': json.dumps({'mame_build': build, 'machine': entry['shortname'], 'ram_option': ram,
                        'note': 'Quantità in byte nell’export ufficiale. RAM predefinita nell’emulatore, non configurazione commerciale certificata.'}, ensure_ascii=False)})
                model_coverage.add('models_with_ram')
            if machine['ram_options']:
                cfg['description'] += ' Opzioni RAM nell’emulatore: ' + ', '.join(r['attributes'].get('name', '?') for r in machine['ram_options']) + '.'
            if re.fullmatch(r'\d{4}', entry['year']) and 1900 <= int(entry['year']) <= int(today[:4]) and entry['year'] not in release_years:
                release_years.add(entry['year'])
                record['releases'].append({'market': 'Non specificato dalla fonte', 'release_date': entry['year'],
                    'source': citation(entry['description'] + ' — anno registrato', entry['path'], entry['line']),
                    'evidence': 'Anno della registrazione COMP MAME, precisione annuale; non è una verifica della prima disponibilità commerciale. ' + entry['original'][:1800]})
            record['configurations'].append(cfg)
        if record['releases']: model_coverage.add('models_with_year')
        # The original quoted data stays separate; normalized records are validated.
        Record.model_validate(record)
        records.append(record); audits.append({'model_id': record['external_id'], 'originals': raw, 'paths': sorted(used)})
        coverage.update(model_coverage)

    output.mkdir(parents=True, exist_ok=True)
    if any(output.glob('batch-*.json')) or (output / 'manifest.json').exists(): raise ValueError('La cartella contiene già lotti: usa una nuova cartella per evitare residui')
    with Path(xml).open('rb') as source_xml:
        xml_sha256 = hashlib.file_digest(source_xml, 'sha256').hexdigest()
    common = {'mame_build': build, 'mame_distribution': distribution, 'mame_source_tag': 'mame0276', 'xml_sha256': xml_sha256,
        'source_repository': REPOSITORY, 'source_revision': revision, 'retrieved_on': today, 'adapted_on': today,
        'adapted_by': 'Hardware History Explorer import tooling',
        'license_notice': 'Estratti testuali soggetti alle licenze dei rispettivi file MAME; copyright individuali e testi completi inclusi. Nessuna ROM, immagine o codice compilato redistribuito.',
        'limitations': ['Fonte di emulazione, non verifica storica indipendente o certificazione di commercializzazione.',
            'Modelli accorpati solo per produttore normalizzato e denominazione uguale dopo qualificatori geografici/firmware espliciti; parent MAME non usato come identità hardware.',
            'CPU/clock/RAM emulati sono proprietà esplicitamente distinte dalle specifiche storiche già presenti.',
            'Prezzi, vendite, recensioni, foto e descrizioni storiche non presenti non vengono inventati.',
            'Date annuali della registrazione, senza giorno inventato; anni incerti restano ignoti.'],
        'licenses': legal}
    batches = []
    for offset in range(0, len(records), batch_size):
        selected = records[offset:offset + batch_size]; audit = audits[offset:offset + batch_size]
        source_paths = sorted({p for item in audit for p in item['paths']})
        file_audit = []
        for path in source_paths:
            text = originals[path]
            header = '\n'.join(text.splitlines()[:10])
            file_audit.append({'path': path, 'url': f'{REPOSITORY}/blob/{revision}/{path}',
                'sha256': hashlib.sha256(text.encode()).hexdigest(), 'copyright_and_license_header': header})
        result = {'_metadata': {**common, 'batch_index': len(batches) + 1, 'original_files': file_audit, 'original_records': audit}, 'records': selected}
        encoded = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()
        if len(encoded) > MAX_BYTES: raise ValueError('Lotto oltre 8 MB: riduci --batch-size')
        filename = f'batch-{len(batches) + 1:02d}.json'
        (output / filename).write_bytes(encoded)
        batches.append({'file': filename, 'models': len(selected), 'bytes': len(encoded), 'sha256': hashlib.sha256(encoded).hexdigest()})
    years = [int(release['release_date']) for record in records for release in record['releases']]
    report = {'title': 'Corpus multimarca da registrazioni MAME — dati da revisionare', **common,
        'models': len(records), 'configurations': sum(len(r['configurations']) for r in records),
        'specifications': sum(len(c['specifications']) for r in records for c in r['configurations']),
        'manufacturers': len({r['manufacturer'] for r in records}), 'coverage': dict(coverage), 'models_with_price': 0,
        'year_range': [min(years), max(years)] if years else None,
        'batches': batches, 'manufacturer_normalizations': aliases, 'excluded_registrations': excluded,
        'source_registrations_selected': len(accepted),
        'index': [{'external_id': r['external_id'], 'manufacturer': r['manufacturer'], 'model_name': r['model_name'],
                   'configurations': len(r['configurations'])} for r in records]}
    write_coverage(output, records)
    report['coverage_file'] = 'coverage.csv (consultazione, non formato di importazione)'
    (output / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--xml', type=Path, required=True, help='Export MAME 0.276 -listxml')
    parser.add_argument('--revision', default=REVISION)
    parser.add_argument('--batch-size', type=int, default=250)
    parser.add_argument('--distribution', default='Non specificata dall’operatore', help='Provenienza/versione del binario che ha prodotto XML')
    args = parser.parse_args()
    report = prepare(args.source, args.xml, args.output, args.revision, args.batch_size, args.distribution)
    print(json.dumps({k: report[k] for k in ('models', 'configurations', 'specifications', 'manufacturers', 'coverage', 'year_range', 'batches')}, indent=2))


if __name__ == '__main__':
    main()
