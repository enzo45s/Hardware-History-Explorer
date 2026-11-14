"""Collect a small, explicitly selected set of authorized 1000bit HTML pages.

This module deliberately does not guess the site's markup or import computers.
Original response bodies can be inspected offline to build a verified adapter.
"""
import argparse
import base64
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from .normalize import MAX_BYTES

AGENT = 'HardwareHistoryExplorer'
USER_AGENT = AGENT + '/1.3 (+https://github.com/enzo45s/Hardware-History-Explorer)'
HOSTS = {'www.1000bit.it', '1000bit.it'}
MAX_PAGES = 5
MAX_PAGE_BYTES = 1024 * 1024
MAX_ROBOTS_BYTES = 128 * 1024
MIN_INTERVAL = 5.0
SCHEMA = 'hhe-1000bit-pages-v1'


def page_url(value):
    if not isinstance(value, str) or len(value) > 800 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise ValueError('Indica un URL 1000bit valido, senza spazi o caratteri di controllo.')
    try:
        url = urlsplit(value)
        valid = (url.scheme == 'https' and url.hostname in HOSTS and url.port in (None, 443)
                 and url.username is None and url.password is None and not url.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Sono ammessi solo URL HTTPS di 1000bit.it, senza credenziali o frammenti.')
    return urlunsplit(('https', url.hostname, url.path or '/', url.query, ''))


def origin(url):
    value = urlsplit(url)
    return urlunsplit((value.scheme, value.netloc, '', '', ''))


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def snapshot(url, body, content_type):
    return {'url': url, 'accessed_at': timestamp(), 'content_type': content_type,
            'sha256': hashlib.sha256(body).hexdigest(),
            'body_base64': base64.b64encode(body).decode('ascii')}


class Collector:
    def __init__(self, client, interval=MIN_INTERVAL, clock=time.monotonic, sleep=time.sleep):
        if not math.isfinite(interval) or interval < MIN_INTERVAL:
            raise ValueError('Intervallo minimo: 5 secondi. Aumentalo se richiesto dal titolare.')
        self.client, self.interval, self.clock, self.sleep = client, interval, clock, sleep
        self.last_request = None
        self.rules, self.robots = {}, []

    def wait(self):
        if self.last_request is not None:
            delay = self.interval - (self.clock() - self.last_request)
            if delay > 0:
                self.sleep(delay)
        self.last_request = self.clock()

    def get(self, url, limit, robots=False):
        """Validate every redirect; a redirected page also needs robots permission."""
        for _ in range(4):
            if not robots:
                self.allowed(url)
            self.wait()
            with self.client.stream('GET', url) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get('location')
                    if not location:
                        raise ValueError('Redirect privo di destinazione.')
                    next_url = page_url(urljoin(url, location))
                    if robots and origin(next_url) != origin(url):
                        raise ValueError('robots.txt reindirizza su un altro host: verifica manuale necessaria.')
                    url = next_url
                    continue
                if robots and response.status_code == 404:
                    return url, 404, b'', response.headers.get('content-type', '')
                if response.status_code == 429:
                    raise ValueError('1000bit richiede una pausa (HTTP 429). Nessun ritentativo automatico: riprova più tardi.')
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise ValueError('Pagina oltre il limite consentito per la raccolta di prova.')
                return url, response.status_code, bytes(body), response.headers.get('content-type', '')
        raise ValueError('Troppi redirect: verifica l’indirizzo della scheda.')

    def allowed(self, url):
        host = origin(url)
        if host not in self.rules:
            robots_url, status, body, content_type = self.get(host + '/robots.txt', MAX_ROBOTS_BYTES, robots=True)
            rules = RobotFileParser()
            if status == 404:
                rules.allow_all = True
            else:
                if 'html' in content_type.casefold() or body.lstrip().lower().startswith((b'<!doctype html', b'<html')):
                    raise ValueError('robots.txt restituisce HTML: verifica manuale necessaria.')
                lines = body.decode('utf-8-sig', errors='replace').splitlines()
                directives = [line.split('#', 1)[0].strip().casefold() for line in lines]
                directives = [line for line in directives if line]
                if directives and not any(line.startswith('user-agent:') for line in directives) and not all(
                        line.startswith('sitemap:') for line in directives):
                    raise ValueError('robots.txt non interpretabile: nessuna scheda richiesta.')
                rules.parse(lines)
            delay = rules.crawl_delay(AGENT) or 0
            rate = rules.request_rate(AGENT)
            self.interval = max(self.interval, delay, rate.seconds / rate.requests if rate and rate.requests > 0 else 0)
            self.rules[host] = rules
            self.robots.append({**snapshot(robots_url, body, content_type), 'http_status': status})
        if not self.rules[host].can_fetch(AGENT, url):
            raise ValueError('robots.txt non consente questo percorso. La raccolta non lo ignora automaticamente.')

    def collect(self, urls):
        if not 1 <= len(urls) <= MAX_PAGES:
            raise ValueError('Indica da 1 a 5 URL di schede, senza scansione del catalogo.')
        # Reject an invalid batch before sending any requests.
        urls = list(dict.fromkeys(page_url(url) for url in urls))
        pages, errors = [], []
        for requested in urls:
            try:
                final, _, body, content_type = self.get(requested, MAX_PAGE_BYTES)
                if content_type.split(';', 1)[0].strip().casefold() not in ('text/html', 'application/xhtml+xml'):
                    raise ValueError('La risposta non è una pagina HTML: nessuna scheda estratta.')
                pages.append({**snapshot(final, body, content_type), 'requested_url': requested})
            except (ValueError, httpx.HTTPError) as exc:
                # Proxy errors may contain connection strings: store a fixed message.
                message = str(exc) if isinstance(exc, ValueError) else 'Rete/proxy non disponibile o risposta HTTP rifiutata.'
                errors.append({'url': requested, 'error': message})
                # Stop the batch on refusal, networking failure or ambiguous markup.
                # Later URLs remain pending rather than generating more traffic.
                break
        attempted = len(pages) + len(errors)
        return {'schema': SCHEMA, 'provider': '1000bit', 'created_at': timestamp(),
                'permission': 'Recupero autorizzato dall’operatore; nessuna licenza aperta presunta.',
                'interval_seconds': self.interval, 'robots': self.robots, 'pages': pages,
                'errors': errors, 'pending_urls': urls[attempted:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', action='append', required=True, help='URL di una scheda; ripetibile, massimo 5.')
    parser.add_argument('--output', type=Path, required=True, help='Nuovo file JSON con le pagine originali.')
    parser.add_argument('--interval', type=float, default=MIN_INTERVAL, help='Pausa minima fra richieste, almeno 5 secondi.')
    args = parser.parse_args()
    # Do not accidentally overwrite an earlier collection.
    if args.output.exists():
        parser.error('Il file di output esiste già: scegli un nuovo nome.')
    try:
        with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False,
                          headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain;q=0.9'}) as client:
            result = Collector(client, args.interval).collect(args.url)
        raw = json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8')
        if len(raw) > MAX_BYTES:
            raise ValueError('Raccolta oltre 8 MB: suddividi gli indirizzi.')
        with args.output.open('xb') as output:
            output.write(raw)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({'output': str(args.output), 'pages': len(result['pages']),
                      'errors': len(result['errors']), 'pending': len(result['pending_urls'])}))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
