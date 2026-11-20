"""Synthetic HTTP fixtures, not copies or verified data from the real archive."""
import base64
import hashlib
import json

import httpx
import pytest

from app.importing.collect_1000bit import Collector, MIN_INTERVAL, page_url

URL = 'https://www.1000bit.it/synthetic-example?id=1'


class Clock:
    def __init__(self):
        self.value = 0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def collect(handler, urls=None):
    clock = Clock()
    with httpx.Client(transport=httpx.MockTransport(handler), headers={'User-Agent': 'HardwareHistoryExplorer'}) as client:
        result = Collector(client, clock=clock.now, sleep=clock.sleep).collect(urls or [URL])
    return result, clock


def test_original_bytes_and_attribution_survive_without_extracting_unverified_data():
    body = '<html><table><tr><td>Fixture sintetica, nessun dato storico</td></tr></table></html>'.encode('cp1252')
    calls = []
    def handler(request):
        calls.append(str(request.url))
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nAllow: /\nCrawl-delay: 9')
        return httpx.Response(200, content=body, headers={'content-type': 'text/html; charset=windows-1252'})
    result, clock = collect(handler, [URL, URL])
    assert calls == ['https://www.1000bit.it/robots.txt', URL]
    assert clock.value >= 9
    page = result['pages'][0]
    assert base64.b64decode(page['body_base64']) == body
    assert page['sha256'] == hashlib.sha256(body).hexdigest()
    assert page['url'] == URL and page['requested_url'] == URL
    assert page['content_type'] == 'text/html; charset=windows-1252'
    assert len(result['robots']) == 1 and result['errors'] == []
    assert 'records' not in result and 'verified' not in result


@pytest.mark.parametrize('url', [
    'http://www.1000bit.it/synthetic', 'https://localhost/synthetic',
    'https://www.1000bit.it.evil.example/synthetic', 'https://1000bit.it:8443/synthetic',
    'https://user:secret@www.1000bit.it/synthetic', 'https://www.1000bit.it/synthetic#fragment',
    'https://www.1000bit.it/synthetic\n', '//www.1000bit.it/synthetic',
])
def test_invalid_urls_are_rejected_before_any_network_request(url):
    calls = []
    with pytest.raises(ValueError):
        collect(lambda request: calls.append(request), [URL, url])
    assert not calls


def test_robots_denial_stops_batch_and_keeps_later_urls_pending():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, text='User-agent: HardwareHistoryExplorer\nDisallow: /')
    result, _ = collect(handler, [URL, URL + '2'])
    assert calls == ['/robots.txt']
    assert not result['pages'] and 'robots.txt' in result['errors'][0]['error']
    assert result['pending_urls'] == [URL + '2']


def test_redirect_to_another_service_is_never_requested():
    calls = []
    def handler(request):
        calls.append(str(request.url))
        if request.url.path == '/robots.txt':
            return httpx.Response(404)
        return httpx.Response(302, headers={'location': 'https://example.org/private'})
    result, _ = collect(handler)
    assert calls == ['https://www.1000bit.it/robots.txt', URL]
    assert not result['pages'] and result['errors']


def test_same_host_redirect_is_checked_against_robots():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /private')
        return httpx.Response(302, headers={'location': '/private'})
    result, _ = collect(handler)
    assert calls == ['/robots.txt', '/synthetic-example']
    assert not result['pages'] and result['errors']


@pytest.mark.parametrize('status', [403, 429, 503])
def test_refused_robot_request_never_triggers_page_requests(status):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(status)
    result, _ = collect(handler)
    assert calls == ['/robots.txt']
    assert not result['pages'] and len(result['errors']) == 1


def test_proxy_errors_do_not_leak_credentials_into_artifacts():
    def handler(request):
        raise httpx.ProxyError('secret-user:secret-password@proxy.example')
    result, _ = collect(handler)
    assert 'secret' not in json.dumps(result)
    assert not result['pages'] and result['errors']


@pytest.mark.parametrize('body', ['Access temporarily denied', '<!-- banner --><html>Challenge</html>'])
def test_success_status_with_non_robot_content_does_not_allow_collection(body):
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, text=body)
    result, _ = collect(handler)
    assert calls == ['/robots.txt']
    assert not result['pages'] and result['errors']


def test_too_large_pages_are_rejected_without_truncating_them(monkeypatch):
    monkeypatch.setattr('app.importing.collect_1000bit.MAX_PAGE_BYTES', 10)
    def handler(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(404)
        return httpx.Response(200, content=b'x' * 11, headers={'content-type': 'text/html'})
    result, _ = collect(handler)
    assert not result['pages'] and result['errors']


def test_spacing_applies_to_all_requests_and_honors_the_robots_request_rate():
    clock, calls = Clock(), []
    def handler(request):
        calls.append(clock.now())
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nAllow: /\nRequest-rate: 1/12')
        return httpx.Response(200, text='<html>synthetic fixture</html>', headers={'content-type': 'text/html'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Collector(client, clock=clock.now, sleep=clock.sleep).collect([URL, URL + '2'])
    assert calls == [0, 12, 24]
    assert len(result['pages']) == 2 and result['interval_seconds'] == 12


@pytest.mark.parametrize('urls', [[], [URL] * 6])
def test_no_implicit_catalog_scan(urls):
    with pytest.raises(ValueError):
        Collector(None).collect(urls)


@pytest.mark.parametrize('interval', [0, MIN_INTERVAL - 1, float('nan'), float('inf')])
def test_interval_cannot_disable_throttling(interval):
    with pytest.raises(ValueError):
        Collector(None, interval)


def test_default_https_port_is_canonicalized():
    assert page_url('https://1000bit.it:443/synthetic?id=1') == 'https://1000bit.it/synthetic?id=1'
