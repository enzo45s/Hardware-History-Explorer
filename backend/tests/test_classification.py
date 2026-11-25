import pytest
from sqlalchemy import select
from app.main import SessionLocal
from app.models import Computer, Category
from app.import_models import ImportClaim, ImportRow
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
    assert c['categories'] == ['Home computer']
    assert client.get('/api/computers').json()['total'] == 10
    detail = client.get('/api/admin/imports/' + str(result.json()['job_id'])).json()
    assert detail['verification_counts'] == {}
    assert all(row['claims'] == [] for row in detail['rows'])
    with SessionLocal() as db:
        claims = db.scalars(select(ImportClaim).join(ImportRow).where(ImportRow.job_id == result.json()['job_id'])).all()
        assert len(claims) == preview['total'] and all(claim.status == 'pending' for claim in claims)
        assert all('Classificazione editoriale' in claim.evidence for claim in claims)
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


@pytest.mark.parametrize('maker,model,category', [
    ('Sun Microsystems, Inc.', 'Ultra 45', 'Workstation'),
    ('NeXT Software Inc.', 'NeXTstation', 'Workstation'),
    ('Silicon Graphics Inc.', 'Indigo2', 'Workstation'),
    ('Hewlett-Packard', 'HP 85', 'Personal computer'),
    ('Atari', 'TT030', 'Workstation'), ('Atari', 'Portfolio', 'Portable'),
    ('Radio Shack', 'TRS-80 Model III', 'Home computer'),
    ('Fujitsu (Japan)', 'FM 11 EX', 'Personal computer'),
    ('Kaypro Corporation', 'Kaypro 4', 'Portable'),
    ('Apple Computer', 'PowerBook 180', 'Portable'),
    ('Commodore', 'DX-64', 'Portable'), ('Sinclair', 'ZX Spectrum', 'Home computer'),
    ('Sharp', 'PC-E220', 'Portable'), ('Cray Research', 'Cray-1', 'Supercomputer'),
    ('Digital Equipment Corporation', 'DEC 2000 Model 500 AXP', 'Server'),
])
def test_extended_families_resolve_brand_aliases(maker, model, category):
    assert classify(maker, model)[0] == category


@pytest.mark.parametrize('url', [
    'https://evil.example/src/mame/msx/msx.cpp',
    'https://github.com/other/mame/blob/rev/src/mame/msx/msx.cpp',
    'https://github.com.evil.example/mamedev/mame/blob/rev/src/mame/msx/msx.cpp',
    'http://github.com/mamedev/mame/blob/rev/src/mame/msx/msx.cpp',
    'https://someone@github.com/mamedev/mame/blob/rev/src/mame/msx/msx.cpp',
])
def test_arbitrary_driver_urls_do_not_assign_categories(url):
    assert classify('Unknown brand', 'Unknown system', [url]) is None


def test_technical_families_do_not_classify_every_product_of_a_manufacturer():
    base = 'https://github.com/mamedev/mame/blob/rev/src/mame/'
    assert classify('Synthetic clone maker', 'Unlisted clone', [base + 'pc/pc.cpp'])[0] == 'Personal computer'
    assert classify('Sony', 'Unlisted device', [base + 'sony/news_68k.cpp'])[0] == 'Workstation'
    assert classify('Sony', 'Unlisted device') is None
    assert classify('Kaypro Corporation', 'Omni II Logic Analyzer', [base + 'kaypro/kaypro.cpp']) is None
    assert classify('Acorn', 'Econet X25 Gateway', [base + 'acorn/bbc.cpp']) is None
    assert classify('Olivetti', 'Olivetti L1 M40') is None


def test_description_requires_the_model_as_subject_and_an_explicit_role():
    assert classify('Acme', 'Model 7', description='Il Model 7 è un computer portatile prodotto per uso professionale.')[0] == 'Portable'
    assert classify('Acme', 'Model 7', description='Il Model 7 era una workstation progettata per la grafica.')[0] == 'Workstation'
    assert classify('Acme', 'Model 7', description='Il Model 8 è un server professionale.') is None
    assert classify('Acme', 'Model 7', description='Il Model 7 è un programma per workstation.') is None
    assert classify('Acme', 'Model 7', description='Il Model 7 non è un server.') is None
    assert classify('Atari', 'Portfolio', description='Portfolio è un personal computer portatile.')[0] == 'Portable'
    assert classify('Atari', 'Portfolio', description='Portfolio è un mainframe.') is None


def test_generic_cleanup_preserves_manual_categories_and_does_not_create_verified_claims(client):
    with SessionLocal() as db:
        c = db.get(Computer, 3)
        custom = Category(name='Categoria curata manualmente')
        c.categories = [custom, Category(name=' Calcolatore ')]
        db.commit()
    preview = client.get('/api/admin/classification/preview').json()
    assert preview['total'] == 0 and preview['cleanup_count'] == 1
    response = client.post('/api/admin/classification/apply', json={'token': preview['token']})
    assert response.status_code == 200, response.text
    assert response.json()['cleaned'] == 1 and response.json()['updated'] == 0
    assert client.get('/api/computers/3').json()['categories'] == ['Categoria curata manualmente']
    assert client.post(f"/api/admin/imports/{response.json()['job_id']}/retry").status_code == 409
    assert client.get('/api/admin/classification/preview').json()['cleanup_count'] == 0


def test_startup_repairs_legacy_generic_entries_and_is_idempotent(client):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.import_models import ImportJob
    with SessionLocal() as db:
        db.get(Computer, 3).categories = [Category(name='Calcolatore')]
        db.commit()
    with TestClient(app) as second:
        assert second.get('/api/computers/3').json()['categories'] == ['Home computer']
    with SessionLocal() as db:
        jobs = len(db.scalars(select(ImportJob)).all())
    with TestClient(app) as third:
        assert third.get('/api/admin/classification/preview').json()['total'] == 0
    with SessionLocal() as db:
        assert len(db.scalars(select(ImportJob)).all()) == jobs


def test_import_classifies_generic_models_and_replay_does_not_restore_generic(client):
    import json
    from app.import_models import ImportJob
    row = {'manufacturer': 'Apple Computer', 'model_name': 'PowerBook 180', 'categories': ['Calcolatore'],
           'source': {'title': 'Synthetic technical fixture', 'url': 'https://example.org/categories'}}
    def run():
        uploaded = client.post('/api/admin/imports/upload', files={'file': ('categories.json', json.dumps([row]), 'application/json')}, data={'rights_confirmed': 'true'})
        assert uploaded.status_code == 201, uploaded.text
        applied = client.post(f"/api/admin/imports/{uploaded.json()['id']}/apply")
        assert applied.status_code == 200, applied.text
        return client.get(f"/api/admin/imports/{uploaded.json()['id']}").json()
    first = run()
    c_id = first['rows'][0]['computer_id']
    assert client.get(f'/api/computers/{c_id}').json()['categories'] == ['Portable']
    assert run()['counts'] == {'unchanged': 1}
    assert client.get(f'/api/computers/{c_id}').json()['categories'] == ['Portable']
    with SessionLocal() as db:
        audits = db.scalars(select(ImportJob)).all()
        classified = [job for job in audits if job.request_options.get('managed_classification')]
        assert len(classified) == 1
        claims = db.scalars(select(ImportClaim).join(ImportRow).where(ImportRow.job_id == classified[0].id)).all()
        assert len(claims) == 1 and claims[0].status == 'pending'
