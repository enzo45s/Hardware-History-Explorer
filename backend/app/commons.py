"""Wikimedia requests with bounded timeouts and actionable, privacy-safe errors."""
import asyncio
import logging
import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from fastapi import HTTPException

URL = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'HardwareHistoryExplorer/1.2 (https://github.com/enzo45s/Hardware-History-Explorer)'
logger = logging.getLogger(__name__)


def photo_query(manufacturer, model):
    """Brand - public model name, without source/variant annotations."""
    from .catalog_names import catalog_name
    model = catalog_name(model)
    from .importing.identity import MAKERS, maker_key
    manufacturer = ' '.join((manufacturer or '').split())
    model = ' '.join((model or '').split())
    aliases = MAKERS.get(maker_key(manufacturer), (manufacturer,))
    brand = aliases[0] if manufacturer else ''
    for alias in sorted(set(aliases) | {manufacturer}, key=len, reverse=True):
        if not alias:
            continue
        match = re.match(re.escape(alias) + r'(?=$|[\s:/-])', model, flags=re.I)
        if match:
            model = model[match.end():].lstrip(' -:/')
            break
    if not model or not brand:
        return (model or brand)[:90]
    brand = brand[:40]
    return f'{brand} - {model}'[:90].rstrip()

INVALID_SEARCH = {'badsearch', 'cirrussearch-parse-error', 'cirrussearch-regex-syntax-error',
                  'cirrussearch-regex-empty-expression', 'cirrussearch-regex-too-complex-error',
                  'cirrussearch-query-too-long', 'cirrussearch-query-too-long-with-exemptions'}
BUSY = {'ratelimited', 'maxlag', 'readonly', 'cirrussearch-too-busy-error',
        'cirrussearch-backend-error', 'cirrussearch-regex-too-busy-error',
        'srsearch-text-disabled', 'srsearch-title-disabled'}


def retry_seconds(value):
    """Retry-After can be a delay or an HTTP date; never retry before it."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if value.isascii() and value.isdigit():
        return 86400 if len(value) > 6 else min(86400, int(value))
    try:
        deadline = parsedate_to_datetime(value)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return min(86400, max(0, math.ceil((deadline - datetime.now(timezone.utc)).total_seconds())))
    except (ValueError, TypeError, OverflowError):
        return None


def retry_headers(response):
    value = getattr(response, 'headers', {}).get('Retry-After', '')
    seconds = retry_seconds(value)
    return {'Retry-After': str(seconds)} if seconds is not None else None


def unavailable(detail, *, cause, status=502, response=None, api_code=None):
    # Do not log search terms, proxy credentials, response bodies or raw exceptions.
    upstream = getattr(response, 'status_code', None)
    logger.warning('Wikimedia search failed: cause=%s upstream_status=%s', cause, upstream)
    # Expose only the bounded API code, never info, query, response body or proxy details.
    if isinstance(api_code, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}', api_code):
        detail = detail.rstrip('.') + f' (codice API: {api_code}).'
    return HTTPException(status, detail, headers=retry_headers(response) if response is not None else None)


async def search_pages(query, limit):
    params = {
        'action': 'query', 'format': 'json', 'formatversion': '1', 'generator': 'search',
        'gsrsearch': query, 'gsrnamespace': '6', 'gsrlimit': str(limit), 'prop': 'imageinfo',
        'gsrsort': 'relevance',
        'maxlag': '5',
        'iiprop': 'url|extmetadata|mime', 'iiurlwidth': '500',
        'iiextmetadatafilter': 'Artist|Attribution|LicenseShortName|LicenseUrl|Copyrighted|UsageTerms',
    }
    response = None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30), headers={
            'User-Agent': USER_AGENT, 'Accept': 'application/json'
        }) as client:
            for attempt in range(2):
                response = await client.get(URL, params=params)
                response.raise_for_status()
                payload = response.json()
                error = payload.get('error') if isinstance(payload, dict) else None
                if attempt == 0 and isinstance(error, dict) and error.get('code') == 'urlparamnormal':
                    # One unrenderable file can abort the entire imageinfo generator.
                    # Retry the same search without thumbnails, not a different model.
                    delay = retry_seconds(response.headers.get('Retry-After', ''))
                    if delay is not None and delay > 5:
                        raise unavailable('Wikimedia Commons richiede una pausa prima di ritentare la ricerca.',
                                          cause='thumbnail_retry_wait', status=503, response=response,
                                          api_code='urlparamnormal')
                    await asyncio.sleep(max(2, delay or 0))
                    params.pop('iiurlwidth')
                    continue
                break
        if not isinstance(payload, dict):
            raise ValueError('Unexpected response structure')
        if 'error' in payload:
            error = payload['error']
            code = error.get('code') if isinstance(error, dict) else None
            if not isinstance(code, str):
                code = None
            if code in BUSY:
                raise unavailable('Wikimedia Commons è temporaneamente occupato o ha limitato le richieste. Attendi e riprova.',
                                  cause='upstream_busy', status=503, response=response, api_code=code)
            if code in INVALID_SEARCH:
                raise unavailable('Wikimedia Commons non può elaborare questa ricerca. Prova un nome più semplice.',
                                  cause='invalid_search', status=422, response=response, api_code=code)
            raise unavailable('Wikimedia Commons ha restituito un errore API. Riprova tra poco.',
                              cause='api_error', response=response, api_code=code)
        result = payload.get('query', {})
        if not isinstance(result, dict):
            raise ValueError('Unexpected query structure')
        pages = result.get('pages', {})
        if not isinstance(pages, dict):
            raise ValueError('Unexpected pages structure')
        return pages
    except httpx.TimeoutException as exc:
        raise unavailable('Wikimedia Commons non ha risposto in tempo. Riprova tra poco.', cause='timeout', status=504) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 429 or status == 503:
            raise unavailable(f'Wikimedia Commons ha limitato le richieste o è sovraccarico (HTTP {status}). Attendi e riprova.',
                              cause='upstream_busy', status=503, response=exc.response) from exc
        if status == 403:
            raise unavailable('Accesso a Wikimedia Commons rifiutato (HTTP 403). Verifica eventuali blocchi di rete o proxy.',
                              cause='upstream_forbidden', response=exc.response) from exc
        raise unavailable(f'Wikimedia Commons ha risposto con un errore (HTTP {status}). Riprova tra poco.',
                          cause='upstream_http', response=exc.response) from exc
    except httpx.ProxyError as exc:
        raise unavailable('Impossibile raggiungere Wikimedia Commons tramite il proxy. Verifica l’accesso a commons.wikimedia.org.',
                          cause='proxy') from exc
    except httpx.ConnectError as exc:
        if 'CERTIFICATE_VERIFY_FAILED' in str(exc).upper():
            raise unavailable('Il certificato HTTPS di Wikimedia Commons non è verificabile. Controlla i certificati del sistema o del proxy.',
                              cause='tls_certificate') from exc
        raise unavailable('Impossibile collegarsi a Wikimedia Commons. Verifica la connessione Internet e il DNS del container API.',
                          cause='connection') from exc
    except httpx.RequestError as exc:
        raise unavailable('Errore di rete durante la ricerca Wikimedia Commons. Riprova tra poco.', cause='network') from exc
    except ValueError as exc:
        raise unavailable('Wikimedia Commons ha restituito una risposta inattesa. Riprova tra poco.', cause='invalid_response', response=response) from exc
