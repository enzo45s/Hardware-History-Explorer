"""Wikimedia requests with bounded timeouts and actionable, privacy-safe errors."""
import logging

import httpx
from fastapi import HTTPException

URL = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'HardwareHistoryExplorer/1.2 (https://github.com/enzo45s/Hardware-History-Explorer)'
logger = logging.getLogger(__name__)


def retry_headers(response):
    value = getattr(response, 'headers', {}).get('Retry-After', '')
    return {'Retry-After': value} if value.isascii() and value.isdigit() else None


def unavailable(detail, *, cause, status=502, response=None):
    # Do not log search terms, proxy credentials, response bodies or raw exceptions.
    upstream = getattr(response, 'status_code', None)
    logger.warning('Wikimedia search failed: cause=%s upstream_status=%s', cause, upstream)
    return HTTPException(status, detail, headers=retry_headers(response) if response is not None else None)


async def search_pages(query, limit):
    params = {
        'action': 'query', 'format': 'json', 'formatversion': '1', 'generator': 'search',
        'gsrsearch': query, 'gsrnamespace': '6', 'gsrlimit': str(limit), 'prop': 'imageinfo',
        'iiprop': 'url|extmetadata|mime', 'iiurlwidth': '500',
        'iiextmetadatafilter': 'Artist|Attribution|LicenseShortName|LicenseUrl|Copyrighted|UsageTerms',
    }
    response = None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30), headers={
            'User-Agent': USER_AGENT, 'Accept': 'application/json'
        }) as client:
            response = await client.get(URL, params=params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError('Unexpected response structure')
        if 'error' in payload:
            error = payload['error']
            code = error.get('code') if isinstance(error, dict) else None
            if code in ('ratelimited', 'maxlag', 'readonly'):
                raise unavailable('Wikimedia Commons è temporaneamente occupato o ha limitato le richieste. Attendi e riprova.',
                                  cause=code, status=503, response=response)
            if code in ('badsearch', 'srsearch-text-disabled', 'srsearch-title-disabled'):
                raise unavailable('Wikimedia Commons non può elaborare questa ricerca. Prova un nome più semplice.',
                                  cause='invalid_search', status=422, response=response)
            raise unavailable('Wikimedia Commons ha restituito un errore API. Riprova tra poco.', cause='api_error', response=response)
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
