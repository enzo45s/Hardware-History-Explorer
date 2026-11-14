import pytest
from sqlalchemy import select
from app.main import SessionLocal
from app.models import Computer, Category
from app.importing.classification import classify


@pytest.mark.parametrize('maker,model,expected', [('Apple','Apple ][','Home computer'),
    ('Apple Computer','Apple IIgs','Home computer'), ('Apple','Macintosh PowerBook 100','Portable'),
    ('Apple','Macintosh 128K','Personal computer'), ('IBM','IBM System/360','Mainframe'),
    ('Digital Equipment Corporation','PDP-11','Minicomputer'), ('IBM','IBM RT PC Model 010','Workstation'),
    ('Commodore','Commodore 64','Home computer'), ('Hewlett-Packard','HP9000/310','Workstation'),
    ('Apple','Unknown future model',None), ('Other maker','Commodore 64',None)])
def test_explicit_family_rules(maker, model, expected):
    result = classify(maker, model)
    assert (result[0] if result else None) == expected


def test_additive_category_repair_preserves_ids_specs_photos_and_pending_audit(client):
    client.post('/api/computers/3/images', json={'image_url': 'https://example.org/manual.jpg'})
    before = client.get('/api/computers/3').json()
    with SessionLocal() as db:
        generic = Category(name='Calcolatore'); db.add(generic)
        for c in db.scalars(select(Computer)):
            c.categories = [generic]
        db.commit()
    preview = client.get('/api/admin/classification/preview').json()
    assert preview['total'] > 0 and preview['by_category']['Home computer'] == 2
    result = client.post('/api/admin/classification/apply', json={'token': preview['token']})
    assert result.status_code == 200, result.text
    c = client.get('/api/computers/3').json()
    assert c['id'] == before['id'] and c['configurations'] == before['configurations'] and c['images'] == before['images']
    assert c['categories'] == ['Home computer', 'Calcolatore']
    assert client.get('/api/computers').json()['total'] == 10
    detail = client.get('/api/admin/imports/' + str(result.json()['job_id'])).json()
    assert detail['verification_counts'] == {'pending': preview['total']}
    assert all('Classificazione editoriale' in claim['evidence'] for row in detail['rows'] for claim in row['claims'])
    second = client.get('/api/admin/classification/preview').json()
    assert second['total'] == 0
    assert client.post('/api/admin/classification/apply', json={'token': second['token']}).json()['updated'] == 0


def test_custom_specific_category_is_never_replaced_and_stale_preview_rejected(client):
    with SessionLocal() as db:
        db.get(Computer,3).categories = [Category(name='Calcolatore')]; db.commit()
    preview = client.get('/api/admin/classification/preview').json()
    with SessionLocal() as db:
        c = db.get(Computer,3)
        c.categories.append(Category(name='Classificazione personale')); db.commit()
    assert client.post('/api/admin/classification/apply', json={'token':preview['token']}).status_code == 409
    assert 'Classificazione personale' in client.get('/api/computers/3').json()['categories']
    assert client.get('/api/admin/classification/preview').json()['total'] == 0


def test_msx_family_uses_recorded_provenance_not_an_arbitrary_model_substring():
    assert classify('Synthetic maker','Synthetic MSX') is None
    assert classify('Synthetic maker','Synthetic model',['https://github.com/mamedev/mame/blob/rev/src/mame/msx/msx.cpp'])[0] == 'Home computer'
