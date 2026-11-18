"""Reader/admin bibliography cleanup must not destroy catalog data or ETL audit."""
import json

import pytest
from sqlalchemy import func, select

from app.main import EAGER, SessionLocal, full
from app.assistant_context import retrieve
from app.import_models import ImportClaim, ImportJob
from app.models import Computer, Configuration, Fact, Release, Review, Sale, Source, Specification
from app.source_policy import is_mame_source


@pytest.mark.parametrize('citation', [
    {'title': 'MAME 0.276 - data'}, {'publisher': 'MAME Development Team'}, {'author': 'Mamedev'},
    {'source_type': 'mame_dataset'}, {'title': 'ＭＡＭＥ · reference'},
    {'url': 'https://www.mamedev.org/release.html'}, {'url': 'https://docs.mamedev.org/techspecs'},
    {'url': 'https://github.com/mamedev/mame/blob/rev/src/mame/example.cpp'},
    {'url': 'https://raw.githubusercontent.com/mamedev/mame/rev/hash/example.xml'},
    {'url': 'https://codeload.github.com/mamedev/mame/tar.gz/refs/tags/mame0276'},
    {'url': 'https://github.com/MAMEDEV/MAME.git'},
])
def test_recognizes_mame_citations(citation):
    assert is_mame_source(citation)


@pytest.mark.parametrize('citation', [
    {'title': 'Manuale Apple II'}, {'title': 'David Mamet'}, {'publisher': 'Another maker'},
    {'url': 'https://example.org/?source=mame'}, {'url': 'https://mamedev.org.example.org/data'},
    {'url': 'https://github.com/mamedev/mame-tools'}, {'url': 'https://example.org/mamedev/mame'},
    {'url': 'https://www.1000bit.it/scheda.asp?id=935'}, {'url': 'https://github.com/AppleDB/appledb'},
])
def test_preserves_independent_sources_and_avoids_substring_false_positives(citation):
    assert not is_mame_source(citation)


def test_legacy_mame_source_is_absent_from_all_public_bibliographies_but_data_is_unchanged(client):
    with SessionLocal() as db:
        computer = db.get(Computer, 1)
        mame = Source(title='MAME test document', url='https://github.com/mamedev/mame', publisher='MAME')
        independent = Source(title='Independent hardware manual', url='https://example.org/manual')
        db.add_all([mame, independent]); db.flush()
        computer.sources = [mame, independent]
        spec = computer.configurations[0].specifications[0]
        spec.sources = [mame, independent]
        release = computer.releases[0]
        release.price, release.currency, release.sources = 3298, 'USD', [mame, independent]
        market = release.market
        computer.sales.append(Sale(market=market, units_sold=123, sources=[mame, independent]))
        computer.reviews.append(Review(publication='Synthetic review', summary='Review text', sources=[mame, independent]))
        computer.facts.append(Fact(fact_type='Synthetic fact', statement='Fact text', sources=[mame, independent]))
        db.commit()
        mame_id, keep_id, spec_id = mame.id, independent.id, spec.id
        protected = [Computer, Configuration, Specification, Release, Sale, Review, Fact]
        before = {model.__name__: db.execute(select(*model.__table__.columns).order_by(model.id)).all() for model in protected}
    listed = client.get('/api/sources').json()
    assert [source['id'] for source in listed] == [keep_id]
    assert client.get(f'/api/sources/{mame_id}').status_code == 404
    assert client.put(f'/api/sources/{mame_id}', json={'title': 'Rename hidden source'}).status_code == 404
    assert client.get(f'/api/sources/{keep_id}').status_code == 200
    data = client.get('/api/computers/1').json()
    groups = [data, *data['releases'], *data['display_releases'], *data['sales'], *data['reviews'], *data['facts'],
              *[s for cfg in data['configurations'] for s in cfg['specifications']]]
    for group in groups:
        assert [source['id'] for source in group['sources']] == [keep_id]
    assert client.get('/api/compare?ids=1,2').json()[0] == data
    # Saving an unrelated editor field retains even the hidden technical references.
    editor = client.get('/api/admin/computers/1').json()
    response = client.put('/api/computers/1', json={key: value for key, value in editor.items() if key != 'id'})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        context = retrieve(db, data['model_name'], EAGER, full)
        item = next(row for row in context['computers'] if row['id'] == 1)
        assert [source['id'] for source in item['sources']] == [keep_id]
        assert db.get(Source, mame_id).publisher == 'MAME'
        assert {source.id for source in db.get(Specification, spec_id).sources} == {mame_id, keep_id}
        for model in protected:
            assert db.execute(select(*model.__table__.columns).order_by(model.id)).all() == before[model.__name__]


def test_manual_mame_sources_cannot_reappear_in_source_panel(client):
    for citation in [{'title': 'MAME driver'}, {'title': 'Dataset', 'url': 'https://www.mamedev.org/'},
                     {'title': 'Dataset', 'publisher': 'MAME'}]:
        assert client.post('/api/sources', json=citation).status_code == 422
    keep = client.post('/api/sources', json={'title': 'Independent manual'}).json()
    assert client.put(f"/api/sources/{keep['id']}", json={'title': 'MAME driver'}).status_code == 422
    assert client.get(f"/api/sources/{keep['id']}").json()['title'] == 'Independent manual'


def test_mame_import_stays_idempotent_and_keeps_audit_without_visible_claims(client):
    record = {'manufacturer': 'Synthetic maker', 'model_name': 'Synthetic source-policy computer',
        'source': {'title': 'MAME synthetic dataset', 'url': 'https://github.com/mamedev/mame'},
        'description': 'A synthetic computer', 'categories': ['Test category'],
        'configurations': [{'variant_name': 'Test variant', 'specifications': [
            {'component_type': 'CPU', 'property_name': 'Clock', 'numeric_value': 2, 'unit': 'MHz'}]}]}
    raw = json.dumps([record]).encode()
    def upload_apply():
        response = client.post('/api/admin/imports/upload', data={'provider': 'manual', 'rights_confirmed': 'true'},
            files={'file': ('synthetic.json', raw, 'application/json')})
        assert response.status_code == 201, response.text
        job_id = response.json()['id']
        response = client.post(f'/api/admin/imports/{job_id}/apply')
        assert response.status_code == 200, response.text
        return client.get(f'/api/admin/imports/{job_id}').json()
    first = upload_apply()
    assert first['counts'] == {'imported': 1}
    assert first['verification_counts'] == {} and first['rows'][0]['claims'] == []
    assert first['rows'][0]['raw']['source']['title'] == 'MAME synthetic dataset'
    assert client.get('/api/sources').json() == []
    second = upload_apply()
    assert second['counts'] == {'unchanged': 1}
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Source)) == 1
        claim = db.scalar(select(ImportClaim).order_by(ImportClaim.id))
        assert claim is not None and claim.source.title == record['source']['title']
        assert claim.status == 'pending'
        claim_id = claim.id
        assert db.get(ImportJob, first['id']).raw_payload == raw.decode()
        context = retrieve(db, record['model_name'], EAGER, full)
        item = next(row for row in context['computers'] if row['id'] == first['rows'][0]['computer_id'])
        assert item['import_assertions'] == [] and item['sources'] == []
    response = client.post(f'/api/admin/imports/claims/{claim_id}/review', json={'decision': 'accept', 'note': 'Synthetic review'})
    assert response.status_code == 404
