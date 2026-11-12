from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app, UPLOAD_DIR


def png_bytes():
    f = BytesIO()
    Image.new('RGBA', (30, 20), (44, 55, 66, 255)).save(f, format='PNG')
    return f.getvalue()


def test_images_url_cover_delete_and_validation():
    with TestClient(app) as client:
        initial = client.get('/api/computers/1/images')
        assert initial.status_code == 200
        first = client.post('/api/computers/1/images', json={
            'image_url': 'https://example.org/original.jpg',
            'caption': 'Fotografia di esempio',
            'author': 'Tester', 'license_name': 'CC BY 4.0',
            'source_url': 'https://example.org/source'
        })
        assert first.status_code == 201, first.text
        a = first.json()['id']
        assert first.json()['is_primary'] is True
        assert client.get('/api/computers/1').json()['image_url'] == 'https://example.org/original.jpg'

        second = client.post('/api/computers/1/images', json={
            'image_url': 'https://example.org/second.jpg', 'is_primary': True
        })
        assert second.status_code == 201, second.text
        b = second.json()['id']
        listed = client.get('/api/computers/1/images').json()
        assert [v['id'] for v in listed[:2]] == [b, a]
        assert sum(v['is_primary'] for v in listed) == 1
        assert client.post(f'/api/computers/1/images/{a}/primary').status_code == 200
        assert client.get('/api/computers').json()['items'][0]['image_url'] == 'https://example.org/original.jpg'
        assert client.delete(f'/api/computers/1/images/{a}').status_code == 204
        assert client.get('/api/computers/1/images').json()[0]['id'] == b
        assert client.get('/api/computers/1/images').json()[0]['is_primary']
        assert client.delete(f'/api/computers/1/images/{b}').status_code == 204
        assert client.get('/api/computers/1').json()['image_count'] == 0
        assert client.post('/api/computers/1/images', json={'image_url': 'http://unsafe.example/image.jpg'}).status_code == 422
        assert client.post('/api/computers/999999/images', json={'image_url':'https://example.org/a.jpg'}).status_code == 404


def test_upload_preview_and_removal():
    with TestClient(app) as client:
        res = client.post('/api/computers/2/images/upload',
            data={'caption': 'Uploaded picture', 'license_name': 'Personal photo'},
            files={'file': ('photo.png', png_bytes(), 'image/png')})
        assert res.status_code == 201, res.text
        data = res.json()
        assert data['storage'] == 'local'
        assert data['url'].startswith('/media/')
        file = UPLOAD_DIR / data['url'].split('/')[-1]
        assert file.exists()
        with Image.open(file) as image:
            assert image.format == 'WEBP'
            assert image.size == (30, 20)
        media = client.get(data['url'])
        assert media.status_code == 200, media.text
        assert media.headers['content-type'] == 'image/webp'
        assert client.delete(f"/api/computers/2/images/{data['id']}").status_code == 204
        assert not file.exists()
        bad = client.post('/api/computers/2/images/upload', files={
            'file': ('fake.png', b'not a real image', 'image/png')})
        assert bad.status_code == 415


def test_commons_search(monkeypatch):
    import app.main as module

    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {'query': {'pages': {'1': {
                'title': 'File:Photo.jpg',
                'imageinfo': [{
                    'url': 'https://upload.wikimedia.org/example.jpg',
                    'thumburl': 'https://upload.wikimedia.org/thumb.jpg',
                    'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Photo.jpg',
                    'mime': 'image/jpeg',
                    'extmetadata': {'Artist': {'value': '<a href="/wiki/Alice">Alice</a>'},
                                    'LicenseShortName': {'value': 'CC BY-SA 4.0'},
                                    'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by-sa/4.0/'}}
                }]
            }}}}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, params):
            assert url == 'https://commons.wikimedia.org/w/api.php'
            assert params['gsrnamespace'] == '6'
            return FakeResponse()

    monkeypatch.setattr(module.httpx, 'AsyncClient', FakeClient)
    with TestClient(app) as client:
        response = client.get('/api/images/search?q=Commodore')
        assert response.status_code == 200, response.text
        result = response.json()['items'][0]
        assert result['author'] == 'Alice'
        assert result['license_name'] == 'CC BY-SA 4.0'
        assert result['source_url'].startswith('https://commons.wikimedia.org')


def test_upload_strips_exif_and_uses_first_gif_frame(client):
    exif = Image.Exif()
    exif[271] = 'Private camera metadata'
    jpeg = BytesIO()
    Image.new('RGB', (20, 30), 'red').save(jpeg, format='JPEG', exif=exif)
    first = Image.new('RGB', (20, 30), 'red')
    gif = BytesIO()
    first.save(gif, format='GIF', save_all=True, append_images=[Image.new('RGB', (20, 30), 'blue')], duration=100)
    for name, content in [('metadata.jpg', jpeg.getvalue()), ('animated.gif', gif.getvalue())]:
        r = client.post('/api/computers/1/images/upload', files={'file': (name, content)})
        assert r.status_code == 201, r.text
        with Image.open(BytesIO(client.get(r.json()['url']).content)) as result:
            assert result.format == 'WEBP'
            assert not result.getexif()
            assert not getattr(result, 'is_animated', False)
            red, green, blue = result.convert('RGB').getpixel((10, 10))
            assert red > blue and red > green


def test_upload_limits_and_database_failure_cleanup(client, monkeypatch):
    import app.main as module
    monkeypatch.setattr(module, 'MAX_UPLOAD_BYTES', 100)
    r = client.post('/api/computers/1/images/upload', files={'file': ('too-big.png', b'x' * 101)})
    assert r.status_code == 413
    monkeypatch.setattr(module, 'MAX_UPLOAD_BYTES', 10 * 1024 * 1024)
    before = set(UPLOAD_DIR.iterdir())
    def fail(*args): raise RuntimeError('database unavailable')
    monkeypatch.setattr(module, 'save_image', fail)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post('/api/computers/1/images/upload', files={'file': ('a.png', png_bytes())})
        assert r.status_code == 500
    assert set(UPLOAD_DIR.iterdir()) == before


def test_commons_filters_invalid_media_and_supports_import(client, monkeypatch):
    import app.main as module
    good = {'title': 'File:Altair.jpg', 'imageinfo': [{
        'url': 'https://upload.wikimedia.org/altair.jpg', 'mime': 'image/jpeg',
        'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Altair.jpg',
        'extmetadata': {'Artist': {'value': '<b>Alice</b>'}, 'LicenseShortName': {'value': 'CC BY 4.0'}}
    }]}
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'query': {'pages': {
            '1': good, '2': {'imageinfo': [{'url': 'https://example.org/a.svg', 'mime': 'image/svg+xml'}]},
            '3': {'imageinfo': [{'url': 'https://', 'mime': 'image/png'}]}, '4': None
        }}}
    class Commons:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, params):
            assert url == 'https://commons.wikimedia.org/w/api.php'
            assert params['gsrnamespace'] == '6'
            return Response()
    monkeypatch.setattr(module.httpx, 'AsyncClient', Commons)
    r = client.get('/api/images/search?q=Altair')
    assert r.status_code == 200
    assert len(r.json()['items']) == 1
    item = r.json()['items'][0]
    assert item['author'] == 'Alice'
    imported = client.post('/api/computers/1/images', json={
        **{k: v for k, v in item.items() if k != 'title'}, 'caption': item['title']
    })
    assert imported.status_code == 201, imported.text
    assert imported.json()['source_url'] == item['source_url']
