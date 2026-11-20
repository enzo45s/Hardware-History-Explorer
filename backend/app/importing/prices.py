"""Read a research workbook as data, never execute formulas or fetch its URLs."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

from .normalize import MAX_BYTES, MAX_ROWS, Citation, Record, name_key

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
FIELDS = ('ID', 'Produttore', 'Modello', 'Anno lancio', 'Prezzo al lancio', 'Valuta',
          'Mercato / Paese', 'Configurazione cui si riferisce', 'Altri listini / varianti',
          'Fonte URL', 'Affidabilità fonte', 'Stato ricerca', 'Note')
PRICED = {'Prezzo con fonte': 'prezzo riportato', "Listino d'epoca, non lancio": 'listino successivo'}
MARKETS = {'USA': 'Stati Uniti'}


def price_kind(status):
    """Declared research labels classify prices; they never verify a claim."""
    if not isinstance(status, str):
        return None
    normalized = name_key(status).replace('’', "'")
    known = {name_key(label): kind for label, kind in PRICED.items()}
    if normalized in known:
        return known[normalized]
    if re.fullmatch(r'prezzo (?:di|al) lancio (?:verificato|documentato|confermato|con fonte)', normalized):
        return 'prezzo riportato'
    return None


def release_from_fields(data, citation, evidence):
    """Interpret the explicit price/currency/market cells, never prose numbers."""
    kind = price_kind(data.get('Stato ricerca', ''))
    if kind is None:
        return None
    try:
        if not isinstance(data.get('Prezzo al lancio'), str):
            raise ValueError('Importo testuale della cella richiesto')
        amount = Decimal(data['Prezzo al lancio'])
    except (InvalidOperation, TypeError, KeyError) as exc:
        raise ValueError('Importo non numerico o separatori ambigui') from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError('Importo positivo e finito richiesto')
    numeric = float(amount)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError('Importo fuori dall’intervallo numerico supportato')
    currency, market = data.get('Valuta', ''), data.get('Mercato / Paese', '')
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}', currency) or not isinstance(market, str) or not market.strip():
        raise ValueError('Valuta ISO e mercato espliciti richiesti')
    return {'market': MARKETS.get(market, market), 'price': numeric, 'currency': currency,
            'price_type': kind, 'source': citation, 'evidence': evidence}


def worksheet(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('Massimo 8 MB per Excel')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as book:
            if len(book.infolist()) > 2000 or sum(item.file_size for item in book.infolist()) > 64 * 1024 * 1024:
                raise ValueError('Excel troppo grande dopo la decompressione')
            def xml(path):
                data = book.read(path)
                if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
                    raise ValueError('Dichiarazioni XML non ammesse')
                return ET.fromstring(data)
            strings = []
            if 'xl/sharedStrings.xml' in book.namelist():
                strings = [''.join(item.itertext()) for item in xml('xl/sharedStrings.xml').findall('s:si', NS)]
            sheets = xml('xl/workbook.xml').findall('s:sheets/s:sheet', NS)
            masters = [sheet for sheet in sheets if sheet.get('name') == 'Prezzi per modello']
            if len(masters) != 1:
                raise ValueError('Serve un solo foglio «Prezzi per modello»')
            relationships = {item.get('Id'): item for item in xml('xl/_rels/workbook.xml.rels')}
            relation = relationships[masters[0].get('{' + REL + '}id')]
            target = relation.get('Target', '')
            path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/' + target)
            if relation.get('TargetMode') == 'External' or not path.startswith('xl/worksheets/') or '..' in path.split('/'):
                raise ValueError('Foglio Excel esterno o non valido')
            root = xml(path)
            rows = []
            for row in root.findall('s:sheetData/s:row', NS):
                if len(rows) >= 10001:
                    raise ValueError('Massimo 10.000 righe nel foglio Excel')
                cells, formulas = {}, []
                for cell in row.findall('s:c', NS):
                    column = re.sub(r'\d', '', cell.get('r', ''))
                    if cell.find('s:f', NS) is not None:
                        formulas.append(column)
                    value = cell.find('s:v', NS)
                    value = value.text if value is not None else ''
                    if cell.get('t') == 's':
                        index = int(value)
                        if not 0 <= index < len(strings):
                            raise ValueError('Indice di stringa Excel non valido')
                        value = strings[index]
                    elif cell.get('t') == 'inlineStr':
                        inline = cell.find('s:is', NS)
                        value = ''.join(inline.itertext()) if inline is not None else ''
                    cells[column] = value or ''
                rows.append((int(row.get('r')), cells, formulas))
            if not rows or [rows[0][1].get(chr(65 + i), '').strip() for i in range(13)] != list(FIELDS):
                raise ValueError('Intestazioni del foglio prezzi non riconosciute')
            return rows[1:], [sheet.get('name') for sheet in sheets if sheet.get('name') != 'Prezzi per modello']
    except (zipfile.BadZipFile, ET.ParseError, KeyError, IndexError, TypeError) as exc:
        raise ValueError('Excel XLSX non valido o struttura non supportata') from exc


def workbook_records(raw):
    rows, ignored = worksheet(raw)
    checksum = hashlib.sha256(raw).hexdigest()
    records, issues, statuses = [], [], Counter()
    missing, shifted, priced, contextual = 0, 0, 0, 0
    for row_number, cells, formulas in rows:
        original = {field: cells.get(chr(65 + index), '').strip() for index, field in enumerate(FIELDS)}
        if not any(original.values()):
            continue
        status = original['Stato ricerca']; statuses[status] += 1
        if not original['Prezzo al lancio'] and not formulas:
            missing += 1
            continue
        try:
            if formulas:
                raise ValueError('Riga con formule: trascrivi valori e riferimenti espliciti prima di importare')
            data = dict(original)
            # Known three-column rotation in the supplied research workbook.
            if data['Affidabilità fonte'].startswith(('https://', 'http://')):
                confidence = data['Altri listini / varianti']
                if not re.fullmatch(r'(?:Alta|Media|Bassa)(?:[- /](?:alta|media|bassa))*', confidence, re.I) or data['Fonte URL'].startswith(('https://', 'http://')):
                    raise ValueError('Colonne fonte/affidabilità ambigue: controlla la riga')
                data['Fonte URL'], data['Affidabilità fonte'], data['Altri listini / varianti'] = data['Affidabilità fonte'], confidence, data['Fonte URL']
                shifted += 1
                issues.append({'row': row_number, 'model': data['Modello'], 'kind': 'source_columns_repaired'})
            if not data['Fonte URL'].startswith(('https://', 'http://')):
                raise ValueError('URL della fonte HTTP(S) mancante o non univoco')
            citation = Citation(title=f"Ricerca prezzi — {data['Produttore']} {data['Modello']}"[:300],
                url=data['Fonte URL'], source_type='research_reference').model_dump(mode='json', exclude_none=True)
            evidence = json.dumps({'adapter': 'historical-prices-v1', 'workbook_sha256': checksum,
                'sheet': 'Prezzi per modello', 'row': row_number, 'original': original,
                'source_checked': False, 'columns_repaired': data != original}, ensure_ascii=False)
            context = '; '.join(f'{field}: {data[field]}' for field in FIELDS if data[field] and field != 'Fonte URL')
            record = {'external_id': f'price-workbook:{checksum}:{row_number}',
                'manufacturer': data['Produttore'], 'model_name': data['Modello'], 'source': citation,
                'evidence': evidence, 'facts': [{'fact_type': 'Contesto del prezzo',
                    'statement': 'Ricerca da verificare. ' + context, 'source': citation, 'evidence': evidence}]}
            release = release_from_fields(data, citation, evidence)
            if release:
                record['releases'] = [release]
                # The workbook's year is not necessarily the price or launch date.
                # Keep it and configuration/tax context in the fact, not release_date.
            Record.model_validate(record)
            if record.get('releases'):
                priced += 1
            else:
                contextual += 1
            records.append(record)
        except ValueError as exc:
            records.append({'error': str(exc), 'workbook_row': row_number, 'original': original})
            issues.append({'row': row_number, 'model': original['Modello'], 'kind': 'invalid', 'error': str(exc)})
    if not records:
        raise ValueError('Il foglio non contiene prezzi o indicazioni da importare')
    if len(records) > MAX_ROWS:
        raise ValueError('Massimo 1.000 righe con prezzi o indicazioni; suddividi il foglio')
    report = {'workbook_sha256': checksum, 'sheet': 'Prezzi per modello', 'ignored_sheets': ignored,
              'models': sum(statuses.values()), 'statuses': dict(statuses), 'without_price': missing,
              'price_records': priced, 'context_only_records': contextual, 'source_columns_repaired': shifted,
              'invalid_records': sum('error' in record for record in records), 'issues': issues,
              'sources_checked': False}
    return records, report
