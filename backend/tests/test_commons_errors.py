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
