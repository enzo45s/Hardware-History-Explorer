"""Italian-language research only. No LLM, scraping, translation or arbitrary URLs."""
import asyncio
import re
import unicodedata
from urllib.parse import urlencode, quote
import httpx
from fastapi import HTTPException
from .commons import USER_AGENT, retry_seconds
from .catalog_display import description_text
from .importing.identity import provider_computer_key, manufacturer_base, MAKERS, MODELS, maker_key
from .catalog_names import catalog_name

API = 'https://it.wikipedia.org/w/api.php'
LICENSE = 'https://creativecommons.org/licenses/by-sa/4.0/'
MAX_RESPONSE = 2 * 1024 * 1024
SEARCH_VERSION = 5
COMPUTING_CONTEXT = re.compile(
    r'\b(?:\w*computers?|calcolator\w*|elaborator\w*|mainframe|workstation|'
    r'palmare|palmari|palmtop|notebook|netbook|subnotebook|laptop|'
    r'(?:handheld|pocket|tablet|desktop|personal)\s+PC|personal\s+digital\s+assistant|organizzator\w*\s+elettronic\w*)\b', re.I)


def maker_aliases(maker):
    """Research spellings only; never change catalog manufacturer identities."""
    compact = lambda value: re.sub(r'[^\w]', '', manufacturer_base(value))
    groups = [aliases for key, aliases in MAKERS.items() if key != 'dec'] + [
        ('DEC', 'Digital Equipment Corporation', 'Digital Equipment'),
        ('NeXT', 'NeXT Inc.', 'NeXT Computer Inc.', 'Next Software Inc', 'NeXT Software, Inc.'),
        ('HP', 'Hewlett-Packard', 'Hewlett Packard'),
        ('Acorn', 'Acorn Computers', 'Acorn Computers Ltd.'),
        ('Atari', 'Atari Inc.', 'Atari, Inc.', 'Atari Corporation'),
        ('Sinclair', 'Sinclair Research', 'Sinclair Research Ltd.'),
        ('Sun', 'Sun Microsystems'),
    ]
    return next((aliases for aliases in groups if compact(maker) in {compact(a) for a in aliases}), (maker.strip(),))


def canonical_model(model, maker):
    text = catalog_name(unicodedata.normalize('NFKC', model).strip())
    if maker_key(maker_aliases(maker)[0]) == 'apple':
        # Catalog names use the Macintosh product line; Italian article titles
        # use PowerBook. Keep every numeric/color/Duo suffix intact.
        text = re.sub(r'^Macintosh\s+(?=PowerBook\b)', '', text, flags=re.I)
    spelling = lambda value: re.sub(r'[\s-]+', '', value).casefold()
    for aliases in MODELS.get(maker_key(maker_aliases(maker)[0]), ()):
        if spelling(text) in {spelling(a) for a in aliases}:
            return aliases[0]
    return text


def search_plan(model, maker):
    """Broader keywords and a full-page lookup, one request per durable step."""
    canonical = canonical_model(model, maker)
    aliases = maker_aliases(maker)
    core = canonical
    for alias in sorted(aliases, key=len, reverse=True):
        match = re.match(re.escape(alias) + r'(?=$|[\s:/-]|\d)', core, flags=re.I)
        if match:
            core = core[match.end():].lstrip(' -:/')
            break
    words = lambda value: ' '.join(re.sub(r'[^\w]+', ' ', value).split())
    brand_query = words(aliases[0] + ' ' + core)
    # The second keyword attempt also handles "PowerBook180" vs "PowerBook 180".
    model_query = words(re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', core))
    full_title = aliases[0] + ' ' + core
    key = model_key(maker, model)
    if key == model_key('HP', 'HP 85'):
        first = {'strategy': 'documented_title', 'titles': 'HP 9800'}
    elif key == model_key('IBM', 'IBM PC 5150'):
        first = {'strategy': 'documented_title', 'titles': 'PC IBM', 'exintro': 1}
    else:
        literal = re.sub(r'["\[\]{}|:]', ' ', canonical).strip()
        first = {'strategy': 'literal', 'query': f'"{literal}" computer'}
    # BBC Model B has no Italian redirect, but its model-specific history is
    # documented in BBC Micro. The passage still has to identify the model.
    bbc = re.fullmatch(r'(?:bbc)?(?:micro)?model([ab])\+?', key[1])
    if aliases[0] == 'Acorn' and bbc:
        full_title = 'BBC Micro'
    plan = [first, {'strategy': 'brand_model', 'query': brand_query},
        {'strategy': 'model_keywords', 'query': model_query},
        {'strategy': 'full_page', 'titles': full_title}]
    if canonical.casefold() != full_title.casefold():
        plan.append({'strategy': 'full_page', 'titles': canonical})
    return plan


def replaceable(model, maker, value):
    """Only missing text and the exact old generated template are eligible."""
    if not (value or '').strip():
        return True
    text = description_text(value).strip()
    category = r'(?:un (?:calcolatore|home computer|personal computer|computer portatile|minicalcolatore|mainframe|microcomputer|supercomputer)|una workstation)'
    pattern = re.escape(model) + r' è ' + category + r' di ' + re.escape(maker) + r'\.(?: Le configurazioni censite riportano [^\n.!?]+\.)?'
    return re.fullmatch(pattern, text) is not None


def improved_retry(model, maker, result):
    """A bounded retry for old rejected candidates or newly corrected names.

    This is a suggestion to research again, never a claim that a page is usable.
    A failed run with the current selector is not suggested repeatedly.
    """
    if result.get('search_version', 0) >= SEARCH_VERSION:
        return False
    if result.get('candidates'):
        return True
    searches = result.get('searches', [])
    if len(searches) < 3:
        return False
    keys = ('strategy', 'query', 'titles', 'exintro')
    clean = lambda search: {k: search[k] for k in keys if k in search}
    return [clean(s) for s in searches[:3]] != [clean(s) for s in search_plan(model, maker)[:3]]


def model_key(maker, model):
    # Research uses the public model name; hardware variants remain in the
    # catalog's configurations and original records, not in search queries.
    title = re.sub(r'\s*\((?:computer|informatica|home computer|personal computer)\)$', '', model, flags=re.I)
    title = canonical_model(title, maker)
    for alias in maker_aliases(maker):
        title = re.sub(r'^' + re.escape(alias) + r'(?=\d)', alias + ' ', title, flags=re.I)
    maker = maker_aliases(maker)[0]
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
    return text if len(text) >= 120 and COMPUTING_CONTEXT.search(text) and re.search(
        r'\b(?:19\d{2}|20\d{2}|svilupp\w*|progett\w*|commercial\w*|introdott\w*|presentat\w*|success\w*|diffus\w*|destinat\w*)\b', text, re.I) else None


def maker_in_text(maker, text):
    aliases = maker_aliases(maker)
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


def family_excerpt(model, maker, page, payload):
    """Quote model-specific passages only in an explicitly linked family page."""
    text = page.get('extract', '')
    lead = text.split('\n\n', 1)[0]
    if not maker_in_text(maker, lead) or not COMPUTING_CONTEXT.search(lead):
        return None
    aliases = maker_aliases(maker)
    core = model_key(maker, model)[1]
    bbc = page['title'] == 'BBC Micro' and aliases[0] == 'Acorn' and re.fullmatch(r'(?:bbc)?(?:micro)?model([ab])(\+)?', core)
    redirect = next((r for r in payload.get('query', {}).get('redirects', [])
        if r.get('to') == page['title'] and model_key(maker, r.get('from', '')) == model_key(maker, model)), None)
    if not bbc and (not redirect or not redirect.get('tofragment')):
        return None
    if bbc:
        suffix = bbc[1] + (bbc[2] or '')
        patterns = [r'(?:model|modello)\s*' + re.escape(suffix)]
    else:
        # Keep all model suffixes. "800" cannot match "800XL" or "180c".
        patterns = [r'[\s_-]*'.join(re.escape(char) for char in core)]
        if core.isdigit():
            patterns = [re.escape(aliases[0]) + r'\s*' + core, r'modell[oi]\s+' + core]
    expression = re.compile(r'(?<![\w+])(?:' + '|'.join(patterns) + r')(?![\w+])', re.I)
    fragment = redirect.get('tofragment', '') if redirect else ''
    numeric_fragment = core.isdigit() and fragment and re.search(r'(?<!\w)' + re.escape(core) + r'(?!\w)', fragment)
    paragraph_matches, path = [], []
    in_fragment = not fragment
    for line in text.splitlines():
        heading = re.fullmatch(r'(={2,6})\s*(.*?)\s*\1', line.strip())
        if heading:
            level, name = len(heading[1]), heading[2]
            path = [(depth, title) for depth, title in path if depth < level] + [(level, name)]
            in_fragment = not fragment or any(title.replace('_', ' ').casefold() == fragment.replace('_', ' ').casefold() for _, title in path)
            continue
        paragraph = line.strip()
        if not in_fragment or len(paragraph) < 60 or not paragraph.endswith(('.', '!', '?')):
            continue
        if any(re.search(r'architettura|specifiche|cronologia|periferiche|software|videogiochi|bibliografia|note|collegamenti', title, re.I) for _, title in path):
            continue
        match = expression.search(paragraph)
        # Numeric model IDs are safe as bare numbers only within the exact
        # model redirect's section, whose heading also identifies that number.
        if not match and numeric_fragment:
            match = re.search(r'(?<!\w)' + re.escape(core) + r'(?!\w)', paragraph)
        if not match:
            continue
        score = (3 if match.start() < 24 else 1) + (2 if re.search(r'\b(?:19\d{2}|20\d{2}|commercial\w*|introd\w*|success\w*|lanciat\w*)', paragraph, re.I) else 0)
        paragraph_matches.append((score, len(paragraph_matches), paragraph, path[-1][1] if path else ''))
    if not paragraph_matches:
        return None
    selected = sorted(sorted(paragraph_matches, key=lambda p: (-p[0], p[1]))[:2], key=lambda p: p[1])
    first_sentence = re.split(r'(?<=[.!?])\s+', lead)[0]
    excerpt = first_sentence + '\n\n' + '\n\n'.join(p[2] for p in selected)
    if len(excerpt) > 1500:
        ends = list(re.finditer(r'[.!?](?=\s|$)', excerpt[:1501]))
        excerpt = excerpt[:ends[-1].end()] if ends else ''
    identified = expression.search(excerpt) or (numeric_fragment and re.search(r'(?<!\w)' + re.escape(core) + r'(?!\w)', excerpt))
    if len(excerpt) < 180 or not identified:
        return None
    return excerpt, fragment or selected[0][3]


def select_result(model, maker, payload, *, full_page=False):
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
        family = family_excerpt(model, maker, page, payload) if full_page and not note else None
        text = note[0] if note else family[0] if family else intro(page.get('extract', ''))
        exact_model = model_key(maker, page['title']) == model_key(maker, model) or pc5150_article(model, maker, page)
        if not text or (not note and not family and (not exact_model or not maker_in_text(maker, text))):
            continue
        if family:
            url += '#' + quote(family[1].replace(' ', '_'))
            if len(url) > 800:
                url = url.split('#', 1)[0]
        accepted.append({'description': text, 'evidence': note[1] if note else text,
            'title': page['title'], 'url': url, 'revision_id': revision,
            'method': 'sintesi editoriale da passaggi italiani' if note else 'passaggi italiani dedicati al modello' if family else 'estratto introduttivo italiano',
            'license_url': LICENSE})
    if len(accepted) == 1:
        return {'status': 'found', **accepted[0], 'candidates': candidates}
    return {'status': 'ambiguous' if accepted else 'no_match', 'candidates': candidates,
        'reason': 'Più voci compatibili: nessuna scelta automatica.' if accepted else 'Nessun testo storico italiano sufficientemente completo con abbinamento certo al modello.'}


async def research(model, maker, *, attempt=0, full_title=None):
    plan = search_plan(model, maker)
    if not 0 <= attempt < len(plan):
        raise ValueError('Tentativo di ricerca non valido')
    search = dict(plan[attempt])
    if search['strategy'] == 'full_page' and full_title:
        search['titles'] = full_title
    params = {'action': 'query', 'format': 'json', 'formatversion': 2, 'maxlag': 5,
        'prop': 'extracts|pageprops|revisions', 'explaintext': 1, 'rvprop': 'ids', 'ppprop': 'disambiguation'}
    if 'titles' in search:
        params.update(titles=search['titles'], redirects=1)
        if search.get('exintro'):
            params['exintro'] = 1
    else:
        params.update(generator='search', gsrsearch=search['query'], gsrnamespace=0, gsrlimit=5, exintro=1, exlimit=5)
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
                result = {'status': 'search_error', 'reason': 'Query rifiutata da Wikipedia; nessuna modifica.'}
            else:
                raise HTTPException(503, 'Wikipedia ha segnalato un errore API. Riprendi per ritentare.', headers={'Retry-After': str(retry)})
        else:
            result = select_result(model, maker, payload, full_page=search['strategy'] == 'full_page')
        result.update(search={**search, 'attempt': attempt + 1}, search_version=SEARCH_VERSION)
        # A matching page with a short introduction may have useful history in
        # its body. Preserve its exact title for the later full-page lookup.
        result['full_title'] = full_title
        for page in payload.get('query', {}).get('pages', []):
            lead = page.get('extract', '').split('\n\n', 1)[0]
            if (not page.get('missing') and 'disambiguation' not in page.get('pageprops', {})
                and model_key(maker, page['title']) == model_key(maker, model)
                and maker_in_text(maker, lead) and COMPUTING_CONTEXT.search(lead)):
                result['full_title'] = page['title']
                break
        if result['status'] in ('no_match', 'search_error') and attempt + 1 < len(plan):
            result['next_attempt'] = attempt + 1
        return result, payload
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(503, 'Risposta Wikipedia non disponibile o non valida. Riprendi per ritentare.', headers={'Retry-After': '30'}) from exc
