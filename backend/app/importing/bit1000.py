"""1000bit technical sheets, based on the operator's real Amiga 1200 HTML.

Parse data only: never execute scripts, submit forms or follow page links.
"""
import base64
import binascii
import hashlib
import json
import math
import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from .collect_1000bit import SCHEMA, MAX_PAGES, MAX_PAGE_BYTES, page_url
from .normalize import MAX_BYTES, clean


def sheet_url(value):
    # The supplied page declares its own HTTP URL; citations use HTTPS.
    if isinstance(value, str) and value.startswith('http://'):
        value = 'https://' + value[7:]
    value = page_url(value)
    parsed = urlsplit(value)
    ids = parse_qs(parsed.query).get('id', [])
    if parsed.path.casefold() != '/scheda.asp' or len(ids) != 1 or not re.fullmatch(r'[1-9]\d{0,11}', ids[0]):
        raise ValueError('Serve l’URL di una scheda 1000bit: https://www.1000bit.it/scheda.asp?id=…')
    return f'https://www.1000bit.it/scheda.asp?id={ids[0]}'


class TechnicalSheet(HTMLParser):
    """Only labeled cells inside tabDatiTecnici; navigation/forms are excluded."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.fields, self.urls = [], {}, []
        self.section_depth = self.row_depth = self.cell_depth = None
        self.cells, self.cell, self.label = [], None, False
        self.skip = 0
        self.sections = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style', 'noscript', 'form'):
            self.skip += 1
        if self.skip:
            return
        if tag == 'div' and 'fb-like' in attrs.get('class', '').split() and attrs.get('data-href'):
            self.urls.append(attrs['data-href'])
        if tag == 'link' and 'canonical' in attrs.get('rel', '').split() and attrs.get('href'):
            self.urls.append(attrs['href'])
        if tag == 'meta' and attrs.get('property') == 'og:url' and attrs.get('content'):
            self.urls.append(attrs['content'])
        if tag in self.VOID:
            if tag == 'br' and self.cell is not None:
                self.cell.append(' ')
            return
        self.stack.append(tag)
        if len(self.stack) > 100:
            raise ValueError('HTML troppo annidato.')
        depth = len(self.stack)
        if attrs.get('id') == 'tabDatiTecnici':
            self.section_depth = depth
            self.sections += 1
        if self.section_depth and tag == 'tr':
            self.row_depth, self.cells = depth, []
        if self.row_depth and tag in ('td', 'th'):
            self.cell_depth, self.cell = depth, []
            self.label = 'w3-indigo' in attrs.get('class', '').split()

    def handle_endtag(self, tag):
        if self.skip:
            if tag in ('script', 'style', 'noscript', 'form'):
                self.skip -= 1
            return
        if tag not in self.stack:
            return
        depth = len(self.stack) - self.stack[::-1].index(tag)
        if self.cell_depth is not None and depth == self.cell_depth:
            self.cells.append((self.label, clean(''.join(self.cell))))
            self.cell_depth, self.cell = None, None
        if self.row_depth is not None and depth == self.row_depth:
            for index, (label, value) in enumerate(self.cells[:-1]):
                if label and not self.cells[index + 1][0]:
                    field_value = self.cells[index + 1][1]
                    key = clean(value).rstrip(':').casefold()
                    if key in self.fields and self.fields[key] != field_value:
                        raise ValueError('La scheda contiene valori discordanti per lo stesso campo.')
                    self.fields[key] = field_value
            self.row_depth = None
        if self.section_depth is not None and depth == self.section_depth:
            self.section_depth = None
        self.stack = self.stack[:depth - 1]

    def handle_data(self, value):
        if not self.skip and self.cell is not None:
            self.cell.append(value)


def decode_html(raw, content_type=''):
    if len(raw) > MAX_BYTES:
        raise ValueError('HTML oltre 8 MB.')
    declaration = re.search(r'charset\s*=\s*["\']?([\w-]+)', content_type, re.I)
    if declaration is None:
        declaration = re.search(br'charset\s*=\s*["\']?([\w-]+)', raw[:4096], re.I)
    encoding = declaration[1] if declaration else 'utf-8-sig'
    if isinstance(encoding, bytes):
        encoding = encoding.decode('ascii')
    if encoding.casefold() not in ('utf-8', 'utf8', 'utf-8-sig', 'iso-8859-1', 'latin-1', 'windows-1252', 'cp1252'):
        raise ValueError('Codifica HTML non supportata: salva la scheda in UTF-8.')
    try:
        return raw.decode(encoding)
    except UnicodeError as exc:
        raise ValueError('La codifica dichiarata non corrisponde al file HTML.') from exc


def present(value):
    return bool(value and value.strip().casefold() not in ('-', '–', '—', '?', 'n/a', 'n.d.', 'nd', 'unknown', 'sconosciuto'))


def price_value(value):
    """Only an unambiguous positive amount with an explicit ISO/specific currency."""
    currencies = {'USD': 'USD', 'US$': 'USD', 'EUR': 'EUR', '€': 'EUR', 'GBP': 'GBP',
                  'ITL': 'ITL', 'JPY': 'JPY', 'DEM': 'DEM', 'FRF': 'FRF'}
    tokens = '|'.join(re.escape(k) for k in currencies)
    match = re.fullmatch(rf'(?:(?P<before>{tokens})\s*(?P<a>[\d., ]+)|(?P<b>[\d., ]+)\s*(?P<after>{tokens}))', value.strip(), re.I)
    if not match:
        return None
    number = (match['a'] or match['b']).strip()
    # Grouped/locale-ambiguous numbers remain contextual facts, never guessed.
    if not re.fullmatch(r'\d+(?:[.,]\d{1,2})?', number):
        return None
    amount = float(number.replace(',', '.'))
    currency = currencies[(match['before'] or match['after']).upper()]
    return (amount, currency) if math.isfinite(amount) and amount > 0 else None


def html_record(raw, source_url=None, content_type='', accessed_at=None):
    parser = TechnicalSheet()
    parser.feed(decode_html(raw, content_type))
    parser.close()
    fields = parser.fields
    if parser.sections != 1 or not present(fields.get('nome')) or not present(fields.get('costruttore')):
        raise ValueError('Non è una scheda 1000bit riconosciuta: mancano tabDatiTecnici, Nome o Costruttore.')
    urls = {sheet_url(value) for value in parser.urls}
    if source_url:
        urls.add(sheet_url(source_url))
    if len(urls) != 1:
        raise ValueError('URL originale mancante o discordante. Specifica l’URL della scheda o usa il raccoglitore.')
    url = urls.pop()
    model, maker = fields['nome'], fields['costruttore']
    if accessed_at is not None and not isinstance(accessed_at, str):
        raise ValueError('Data di accesso della pagina non valida.')
    access_date = date.today() if accessed_at is None else datetime.fromisoformat(accessed_at.replace('Z', '+00:00')).date()
    citation = {'title': f'1000bit — {model}', 'url': url, 'publisher': '1000bit', 'source_type': 'website',
                'access_date': access_date.isoformat(), 'license': 'Recupero autorizzato dall’operatore; nessuna licenza aperta presunta.'}
    checksum = hashlib.sha256(raw).hexdigest()

    def evidence(label, value):
        return json.dumps({'adapter': '1000bit-sheet-v1', 'sha256': checksum, 'url': url,
                           'field': label, 'value': value[:1800]}, ensure_ascii=False)

    specs, facts, releases = [], [], []
    def spec(component, prop, value, label, **quantity):
        specs.append({'component_type': component, 'property_name': prop,
                      **({'text_value': value} if not quantity else quantity), 'source': citation, 'evidence': evidence(label, value)})
    def fact(label, value):
        facts.append({'fact_type': label, 'statement': f'{label}: {value}', 'source': citation, 'evidence': evidence(label, value)})

    cpu = fields.get('cpu', '')
    if present(cpu):
        match = re.fullmatch(r'(.+?)\s+[-–—]\s+(\d+(?:[.,]\d+)?)\s*(GHz|MHz|kHz|Hz)', cpu, re.I)
        spec('CPU', 'Modello', match[1] if match else cpu, 'CPU')
        if match:
            unit = {'ghz': 'GHz', 'mhz': 'MHz', 'khz': 'kHz', 'hz': 'Hz'}[match[3].casefold()]
            spec('CPU', 'Frequenza', cpu, 'CPU', numeric_value=float(match[2].replace(',', '.')), unit=unit)
    mappings = {'ram': ('RAM', 'Capacità riportata'), 'rom': ('ROM', 'Capacità riportata'),
                'tipo': ('Sistema', 'Formato'), 'sistema operativo': ('Sistema operativo', 'Nome'),
                'testo (col. x righe)': ('Video', 'Modalità testo'), 'grafica': ('Video', 'Grafica'),
                'suono': ('Audio', 'Dotazione'), 'memoria di massa': ('Storage', 'Dotazione'),
                'porta seriale': ('Interfacce', 'Porta seriale'), 'porta parallela': ('Interfacce', 'Porta parallela'),
                'altre porte': ('Interfacce', 'Altre porte')}
    for label, (component, prop) in mappings.items():
        if present(fields.get(label)):
            spec(component, prop, fields[label], label)
    # Production, ownership/contributor metadata and sale dates have different meanings.
    known = {'nome', 'costruttore', 'cpu', 'user', *mappings}
    price_fields = ('prezzo originale', 'prezzo originale in valuta')
    known.update(price_fields)
    for label, value in fields.items():
        if label not in known and present(value):
            fact(label.capitalize(), value)
    prices = [(label, value, price_value(value)) for label in price_fields
              if present(value := fields.get(label)) and not re.fullmatch(r'0(?:[.,]0+)?', value)]
    parsed = {parsed for _, _, parsed in prices if parsed}
    if len(prices) == 1 and len(parsed) == 1:
        amount, currency = parsed.pop()
        label, value, _ = prices[0]
        releases.append({'market': 'Non specificato dalla fonte', 'price': amount, 'currency': currency,
                         'price_type': 'prezzo riportato', 'source': citation, 'evidence': evidence(label, value)})
    else:
        for label, value, _ in prices:
            fact(label.capitalize(), value)
    # Synthesize only recorded facts in Italian; optional upgrades stay in notes.
    description = f'{model} è un calcolatore di {maker}.'
    if present(cpu):
        description += f' La scheda tecnica riporta la CPU {cpu}.'
    record = {'external_id': url.rsplit('=', 1)[1], 'manufacturer': maker, 'model_name': model,
              'description': description, 'source': citation, 'evidence': evidence('Scheda tecnica', model),
              'facts': facts, 'releases': releases}
    if specs:
        record['configurations'] = [{'variant_name': 'Scheda tecnica',
            'description': 'Dotazioni riportate dalla fonte; opzioni e aggiornamenti sono descritti separatamente nelle note.',
            'source': citation, 'specifications': specs}]
    return record


def snapshot_records(payload):
    if not isinstance(payload, dict) or payload.get('schema') != SCHEMA or payload.get('provider') != '1000bit':
        raise ValueError('Formato del raccoglitore 1000bit non riconosciuto.')
    pages, errors, pending = (payload.get(k, []) for k in ('pages', 'errors', 'pending_urls'))
    if not all(isinstance(v, list) for v in (pages, errors, pending)) or not 1 <= len(pages) + len(errors) + len(pending) <= MAX_PAGES:
        raise ValueError('La raccolta deve contenere da 1 a 5 schede/esiti.')
    records, identities = [], {}
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError('Metadati della pagina mancanti.')
        try:
            raw = base64.b64decode(page['body_base64'], validate=True)
        except (KeyError, ValueError, TypeError, binascii.Error) as exc:
            raise ValueError('Contenuto Base64 della pagina non valido.') from exc
        if len(raw) > MAX_PAGE_BYTES or hashlib.sha256(raw).hexdigest() != page.get('sha256'):
            raise ValueError('Dimensione o SHA-256 della pagina non corrispondente.')
        url = sheet_url(page.get('url'))
        if page.get('requested_url') and sheet_url(page['requested_url']) != url:
            raise ValueError('La raccolta reindirizza a una scheda con un altro ID.')
        if url in identities:
            if identities[url] != page['sha256']:
                raise ValueError('La raccolta contiene copie discordanti della stessa scheda: separa le versioni.')
            continue
        identities[url] = page['sha256']
        try:
            records.append(html_record(raw, url, page.get('content_type', ''), page.get('accessed_at')))
        except ValueError as exc:
            records.append({'error': str(exc), 'source_url': url})
    for item in errors:
        if not isinstance(item, dict):
            raise ValueError('Esito della raccolta non valido.')
        records.append({'error': str(item.get('error', 'Recupero fallito'))[:2000], 'source_url': sheet_url(item.get('url'))})
    for url in pending:
        records.append({'error': 'Scheda non recuperata: riprova questo URL.', 'source_url': sheet_url(url)})
    return records


def uploaded_records(raw, format, source_url=None):
    if format in ('html', 'htm'):
        return [html_record(raw, source_url)]
    if format == 'json':
        payload = json.loads(raw.decode('utf-8-sig'))
        if isinstance(payload, dict) and payload.get('schema') == SCHEMA:
            return snapshot_records(payload)
    # Canonical CSV/JSON continues through the normal ETL parser.
    return None
