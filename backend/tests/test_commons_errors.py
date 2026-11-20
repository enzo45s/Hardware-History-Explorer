import httpx
import pytest

from app import commons


def stub(monkeypatch, *, payload=None, status=200, error=None, headers=None):
    class Client:
        def __init__(self, **kwargs):
            assert kwargs['headers']['User-Agent'] == commons.USER_AGENT
            assert 'https://github.com/enzo45s/Hardware-History-Explorer' in kwargs['headers']['User-Agent']
            assert kwargs['timeout'].read == 30
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, params):
            assert url == 'https://commons.wikimedia.org/w/api.php'
            assert params['formatversion'] == '1'
            assert params['gsrnamespace'] == '6'
            if error:
                raise error
            return httpx.Response(status, json=payload, headers=headers, request=httpx.Request('GET', url))
    monkeypatch.setattr(commons.httpx, 'AsyncClient', Client)


@pytest.mark.parametrize('status,expected,detail', [
    (403, 502, 'HTTP 403'), (429, 503, 'HTTP 429'),
    (503, 503, 'HTTP 503'), (500, 502, 'HTTP 500'),
])
def test_http_errors_are_actionable_and_keep_retry_after(client, monkeypatch, status, expected, detail):
    stub(monkeypatch, status=status, payload={}, headers={'Retry-After': '60'})
    r = client.get('/api/images/search?q=Altair')
    assert r.status_code == expected
    assert detail in r.json()['detail']
    assert r.headers['retry-after'] == '60'


@pytest.mark.parametrize('error,expected,detail', [
    (httpx.ReadTimeout('remote timeout'), 504, 'tempo'),
    (httpx.ConnectError('offline'), 502, 'connessione Internet'),
    (httpx.ConnectError('CERTIFICATE_VERIFY_FAILED'), 502, 'certificato HTTPS'),
    (httpx.ProxyError('private proxy credentials must not appear'), 502, 'proxy'),
    (httpx.RemoteProtocolError('bad response'), 502, 'Errore di rete'),
])
def test_transport_failure_does_not_leak_raw_details(client, monkeypatch, caplog, error, expected, detail):
    stub(monkeypatch, error=error)
    r = client.get('/api/images/search?q=private-search-term')
    assert r.status_code == expected
    assert detail in r.json()['detail']
    assert 'private proxy credentials' not in r.text + caplog.text
    assert 'private-search-term' not in caplog.text


@pytest.mark.parametrize('code,status', [('maxlag', 503), ('ratelimited', 503), ('readonly', 503), ('badsearch', 422), ('unexpected', 502)])
def test_mediawiki_errors_are_not_empty_results(client, monkeypatch, code, status):
    stub(monkeypatch, payload={'error': {'code': code, 'info': 'Do not expose raw upstream data'}})
    r = client.get('/api/images/search?q=Altair')
    assert r.status_code == status
    assert 'Do not expose' not in r.text


@pytest.mark.parametrize('payload', [[], {'query': []}, {'query': {'pages': []}}])
def test_unexpected_response_has_distinct_message(client, monkeypatch, payload):
    stub(monkeypatch, payload=payload)
    r = client.get('/api/images/search?q=Altair')
    assert r.status_code == 502
    assert 'risposta inattesa' in r.json()['detail']


def test_no_matches_are_not_an_outage(client, monkeypatch):
    stub(monkeypatch, payload={'batchcomplete': ''})
    r = client.get('/api/images/search?q=NoMatch')
    assert r.status_code == 200
    assert r.json()['items'] == []


@pytest.mark.parametrize('code', sorted(commons.INVALID_SEARCH))
def test_permanent_search_errors_are_identified_without_exposing_upstream_info(client, monkeypatch, code):
    stub(monkeypatch, payload={'error': {'code': code, 'info': 'private query and internal server details'}})
    response = client.get('/api/images/search?q=Apple%20%5D%5B')
    assert response.status_code == 422
    assert code in response.json()['detail']
    assert 'private query' not in response.text


@pytest.mark.parametrize('code', sorted(commons.BUSY))
def test_busy_backend_never_becomes_an_empty_search_result(client, monkeypatch, code):
    stub(monkeypatch, payload={'error': {'code': code}})
    response = client.get('/api/images/search?q=Altair')
    assert response.status_code == 503 and code in response.json()['detail']


@pytest.mark.parametrize('code', [[], {}, '<script>alert(1)</script>', 'secret:' + 'x' * 200])
def test_malformed_error_code_cannot_crash_or_inject_upstream_data(client, monkeypatch, code):
    stub(monkeypatch, payload={'error': {'code': code, 'info': 'private upstream info'}})
    response = client.get('/api/images/search?q=Altair')
    assert response.status_code == 502
    assert 'script' not in response.text and 'private upstream info' not in response.text


def test_retry_after_http_date_is_converted_to_a_safe_delay(client, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime
    deadline = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=90), usegmt=True)
    stub(monkeypatch, status=429, payload={}, headers={'Retry-After': deadline})
    response = client.get('/api/images/search?q=Altair')
    assert response.status_code == 503 and 85 <= int(response.headers['retry-after']) <= 90


def test_extreme_retry_after_is_bounded_without_integer_conversion_failure():
    assert commons.retry_seconds('9' * 5000) == 86400


def thumbnail_failure_then(monkeypatch, payload, *, status=200, headers=None, first_headers=None):
    from types import SimpleNamespace
    calls, waits = [], []
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, params):
            calls.append(dict(params))
            first = len(calls) == 1
            return httpx.Response(200 if first else status,
                json={'error': {'code': 'urlparamnormal'}} if first else payload,
                headers=first_headers if first else headers, request=httpx.Request('GET', url))
    async def sleep(seconds): waits.append(seconds)
    monkeypatch.setattr(commons.httpx, 'AsyncClient', Client)
    monkeypatch.setattr(commons, 'asyncio', SimpleNamespace(sleep=sleep))
    return calls, waits


def test_thumbnail_failure_retries_same_search_and_retains_mime_filter(client, monkeypatch):
    metadata = {'url': 'https://upload.wikimedia.org/original.jpg',
        'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Original.jpg', 'mime': 'image/jpeg',
        'extmetadata': {'Artist': {'value': 'Alice'}, 'LicenseShortName': {'value': 'CC BY-SA 4.0'}}}
    calls, waits = thumbnail_failure_then(monkeypatch, {'query': {'pages': {
        '1': {'title': 'File:Original.jpg', 'imageinfo': [metadata]},
        '2': {'title': 'File:Manual.pdf', 'imageinfo': [{**metadata, 'mime': 'application/pdf'}]},
    }}})
    response = client.get('/api/images/search?q=MicroMainFrame%209000')
    assert response.status_code == 200, response.text
    items = response.json()['items']
    assert len(items) == 1 and items[0]['image_url'] == metadata['url']
    assert items[0]['thumbnail_url'] == metadata['url']
    assert items[0]['author'] == 'Alice' and items[0]['license_name'] == 'CC BY-SA 4.0'
    assert len(calls) == 2 and waits == [2]
    assert calls[0].pop('iiurlwidth') == '500' and calls[0] == calls[1]
    assert calls[1]['gsrsearch'] == 'MicroMainFrame 9000'


def test_repeated_thumbnail_error_is_bounded_and_not_an_empty_result(client, monkeypatch):
    calls, waits = thumbnail_failure_then(monkeypatch, {'error': {'code': 'urlparamnormal'}})
    response = client.get('/api/images/search?q=MicroMainFrame%209000')
    assert response.status_code == 502 and 'urlparamnormal' in response.text
    assert len(calls) == 2 and waits == [2]


def test_thumbnail_retry_preserves_rate_limit_and_current_queue_item(client, monkeypatch):
    from app.main import SessionLocal
    from app.photo_jobs import PhotoItem
    from sqlalchemy import select
    job = client.post('/api/admin/photos').json()
    with SessionLocal() as db:
        current_id = db.scalar(select(PhotoItem.id).where(PhotoItem.job_id == job['id']).order_by(PhotoItem.position).limit(1))
    calls, waits = thumbnail_failure_then(monkeypatch, {}, status=429, headers={'Retry-After': '90'})
    response = client.post(f"/api/admin/photos/{job['id']}/step").json()
    assert response['status'] == 'paused' and response['counts'] == {'pending': job['total']}
    assert response['current']['id'] == current_id and 'HTTP 429' in response['error']
    assert len(calls) == 2 and waits == [2]
    client.post(f"/api/admin/photos/{job['id']}/resume")
    assert client.post(f"/api/admin/photos/{job['id']}/step").status_code == 429


def test_thumbnail_failure_honors_long_retry_after_without_holding_a_lease(client, monkeypatch):
    calls, waits = thumbnail_failure_then(monkeypatch, {}, first_headers={'Retry-After': '60'})
    response = client.get('/api/images/search?q=Altair')
    assert response.status_code == 503 and response.headers['retry-after'] == '60'
    assert len(calls) == 1 and waits == []


def test_paused_existing_queue_recovers_thumbnail_error_without_losing_photos(client, monkeypatch):
    from app.main import SessionLocal
    from app.models import Computer
    from app.photo_jobs import PhotoItem, PhotoJob
    from sqlalchemy import select
    existing = client.post('/api/computers/1/images', json={'image_url': 'https://example.org/preserved.jpg'}).json()
    job = client.post('/api/admin/photos').json()
    with SessionLocal() as db:
        rows = db.scalars(select(PhotoItem).where(PhotoItem.job_id == job['id']).order_by(PhotoItem.position)).all()
        current = rows[-1]
        current.model_name = current.query = 'MicroMainFrame 9000'
        db.get(Computer, current.computer_id).model_name = current.model_name
        for row in rows[:-1]: row.status = 'no_match'
        saved = db.get(PhotoJob, job['id'])
        saved.status, saved.error = 'paused', 'Previous urlparamnormal failure'
        cid = current.computer_id
        db.commit()
    thumbnail_failure_then(monkeypatch, {'query': {'pages': {'1': {
        'title': 'File:Synthetic.jpg', 'imageinfo': [{
            'url': 'https://upload.wikimedia.org/synthetic.jpg', 'mime': 'image/jpeg',
            'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Synthetic.jpg',
            'extmetadata': {'Artist': {'value': 'Alice'}, 'LicenseShortName': {'value': 'CC0'}}
        }]} }}})
    client.post(f"/api/admin/photos/{job['id']}/resume")
    response = client.post(f"/api/admin/photos/{job['id']}/step").json()
    assert response['id'] == job['id'] and response['status'] == 'completed'
    assert response['counts'] == {'added': 1, 'no_match': job['total'] - 1}
    assert client.get('/api/computers/1/images').json() == [existing]
    photos = client.get(f'/api/computers/{cid}/images').json()
    assert len(photos) == 1 and photos[0]['author'] == 'Alice' and photos[0]['license_name'] == 'CC0'
