"""Italian-language research only. No LLM, scraping, translation or arbitrary URLs."""
import asyncio
import re
import unicodedata
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException
from .commons import USER_AGENT, retry_seconds
from .catalog_display import description_text
from .importing.identity import provider_computer_key, manufacturer_base

API = 'https://it.wikipedia.org/w/api.php'
LICENSE = 'https://creativecommons.org/licenses/by-sa/4.0/'
MAX_RESPONSE = 2 * 1024 * 1024


def replaceable(model, maker, value):
    """Only missing text and the exact old generated template are eligible."""
    if not (value or '').strip():
        return True
    text = description_text(value).strip()
    category = r'(?:un (?:calcolatore|home computer|personal computer|computer portatile|minicalcolatore|mainframe|microcomputer|supercomputer)|una workstation)'
    pattern = re.escape(model) + r' è ' + category + r' di ' + re.escape(maker) + r'\.(?: Le configurazioni censite riportano [^\n.!?]+\.)?'
    return re.fullmatch(pattern, text) is not None


def model_key(maker, model):
    # Remove only article disambiguation, not hardware or regional qualifiers.
    title = re.sub(r'\s*\((?:computer|informatica|home computer|personal computer)\)$', '', model, flags=re.I)
    maker = manufacturer_base(maker)
    # HP's full corporate spelling is common in Italian article titles.
    if maker.casefold() in ('hp', 'hewlett-packard', 'hewlett packard'):
        maker = 'HP'
        title = re.sub(r'^Hewlett[ -]Packard\b', 'HP', title, flags=re.I)
    return provider_computer_key('historical_prices', maker, title)


def intro(extract):
    """At most two paragraphs, ending at an existing sentence boundary."""
    paragraphs = [p.strip() for p in extract.split('\n') if p.strip() and not p.startswith('==')]
    text = '\n\n'.join(paragraphs[:2])
    # Never leave a partial sentence or produce new historical assertions.
    if len(text) > 1500:
        ends = list(re.finditer(r'[.!?](?=\s|$)', text[:1501]))
        text = text[:ends[-1].end()] if ends else ''
    return text if len(text) >= 180 and re.search(r'\b(?:computer|microcomputer|minicomputer|supercomputer|calcolator\w*|elaborator\w*|mainframe|workstation)\b', text, re.I) and re.search(
        r'\b(?:19\d{2}|20\d{2}|svilupp\w*|progett\w*|commercial\w*|introdott\w*|presentat\w*|success\w*|diffus\w*|destinat\w*)\b', text, re.I) else None


def maker_in_text(maker, text):
    from .importing.identity import MAKERS, maker_key, manufacturer_base
    maker = manufacturer_base(maker)
    aliases = MAKERS.get(maker_key(maker), (maker,))
    if maker in ('hp', 'hewlett-packard', 'hewlett packard'):
        aliases = ('HP', 'Hewlett-Packard', 'Hewlett Packard')
    normalized = unicodedata.normalize('NFKC', text)
    return any(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', normalized, re.I) for alias in aliases)


def hp85_note(model, maker, page):
    """A researched Italian passage about HP-85 lives in the HP 9800 article.

    This explicit exception is model-specific; never substitute a family's
    introduction for every member. Require both supporting passages verbatim.
    """
    if model_key(maker, model) != model_key('HP', 'HP 85') or page.get('title') != 'HP 9800':
        return None
    evidence = [
        'Questa serie diede avvio allo sviluppo della serie HP 80, ovvero HP 85 e HP 87, che erano computer con linguaggio BASIC più piccoli con display CRT, prodotti dalla divisione Advanced Products di HP con sede a Corvallis.',
        "Nel 1979 viene prodotto l'85, il primo della serie 80 di personal computer scientifici da tavolo. Aveva un potente interprete BASIC ed era accessibile a singoli individui, al contrario dei costosi 9845, accessibili solo alle aziende."
    ]
    if not all(part in page.get('extract', '') for part in evidence):
        return None
    return (
        "L'HP 85 fu il primo modello della serie 80 di personal computer scientifici da tavolo di Hewlett-Packard, sviluppata dopo la serie HP 9800. "
        "Questi sistemi, prodotti dalla divisione Advanced Products di Corvallis, offrivano il linguaggio BASIC e un display CRT in dimensioni più contenute. "
        "L'HP 85 disponeva di un interprete BASIC e, rispetto ai costosi HP 9845 rivolti alle aziende, era accessibile anche ai singoli utenti.",
        '\n\n'.join(evidence)
    )


def pc5150_article(model, maker, page):
    # The Italian article uses the reversed title "PC IBM". It explicitly
    # identifies the 5150, not the PC XT/AT family; require that evidence.
    return (model_key(maker, model) == model_key('IBM', 'IBM PC 5150')
        and page.get('title') == 'PC IBM'
        and re.search(r'\bIBM 5150\b', page.get('extract', '')) is not None)


def select_result(model, maker, payload):
    pages = payload.get('query', {}).get('pages', [])
    if not isinstance(pages, list):
        raise ValueError('Formato API inatteso')
    candidates, accepted = [], []
    for page in pages:
        if page.get('missing') or page.get('ns') != 0 or 'disambiguation' in page.get('pageprops', {}):
            continue
        revisions = page.get('revisions') or []
        revision = revisions[0].get('revid') if revisions else None
        if not isinstance(revision, int) or revision <= 0:
            continue
        url = 'https://it.wikipedia.org/w/index.php?' + urlencode({'title': page['title'], 'oldid': revision})
        if len(url) > 800:
            url = 'https://it.wikipedia.org/w/index.php?' + urlencode({'oldid': revision})
        candidates.append({'title': page['title'], 'url': url})
        note = hp85_note(model, maker, page)
        text = note[0] if note else intro(page.get('extract', ''))
        exact_model = model_key(maker, page['title']) == model_key(maker, model) or pc5150_article(model, maker, page)
        if not text or (not note and (not exact_model or not maker_in_text(maker, text))):
            continue
        accepted.append({'description': text, 'evidence': note[1] if note else text,
            'title': page['title'], 'url': url, 'revision_id': revision,
            'method': 'sintesi editoriale da passaggi italiani' if note else 'estratto introduttivo italiano',
            'license_url': LICENSE})
    if len(accepted) == 1:
        return {'status': 'found', **accepted[0], 'candidates': candidates}
    return {'status': 'ambiguous' if accepted else 'no_match', 'candidates': candidates,
        'reason': 'Più voci compatibili: nessuna scelta automatica.' if accepted else 'Nessun testo storico italiano sufficientemente completo con abbinamento certo al modello.'}


async def research(model, maker):
    params = {'action': 'query', 'format': 'json', 'formatversion': 2, 'maxlag': 5,
        'prop': 'extracts|pageprops|revisions', 'explaintext': 1, 'rvprop': 'ids', 'ppprop': 'disambiguation'}
    if model_key(maker, model) == model_key('HP', 'HP 85'):
        params['titles'] = 'HP 9800'
    elif model_key(maker, model) == model_key('IBM', 'IBM PC 5150'):
        params.update(titles='PC IBM', exintro=1)
    else:
        query = re.sub(r'["\[\]{}|:]', ' ', model).strip()
        params.update(generator='search', gsrsearch=f'"{query}" computer', gsrnamespace=0, gsrlimit=5, exintro=1, exlimit=5)
    try:
        async with asyncio.timeout(35), httpx.AsyncClient(timeout=httpx.Timeout(25, connect=10), headers={'User-Agent': USER_AGENT}, follow_redirects=False) as client:
            async with client.stream('GET', API, params=params) as response:
                retry = max(2, retry_seconds(response.headers.get('Retry-After', '')) or 30)
                if response.status_code == 429 or response.status_code >= 500:
                    raise HTTPException(503, 'Wikipedia è occupata. La ricerca resta in attesa e può essere ripresa.', headers={'Retry-After': str(retry)})
                if response.status_code != 200:
                    raise HTTPException(503, 'Wikipedia non è raggiungibile. Nessuna descrizione modificata.', headers={'Retry-After': '60'})
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE:
                        raise HTTPException(503, 'Risposta Wikipedia troppo grande: ricerca in pausa.', headers={'Retry-After': '60'})
        import json
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('Formato API inatteso')
        if payload.get('error'):
            code = payload['error'].get('code', '')
            if code in ('badsearch', 'cirrussearch-parse-error', 'urlparamnormal'):
                return {'status': 'search_error', 'reason': 'Query rifiutata da Wikipedia; nessuna modifica.'}, payload
            raise HTTPException(503, 'Wikipedia ha segnalato un errore API. Riprendi per ritentare.', headers={'Retry-After': str(retry)})
        return select_result(model, maker, payload), payload
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(503, 'Risposta Wikipedia non disponibile o non valida. Riprendi per ritentare.', headers={'Retry-After': '30'}) from exc
