import json
from copy import deepcopy

import pytest
from sqlalchemy import func, select

from app.main import SessionLocal
from app.models import Computer, Manufacturer, Configuration, Specification, Source, spec_source
from app.import_models import CatalogReconciliation
from app.importing.vocabulary import spec_values
from app.unit_review import apply, clarify, load_proofs, prepare, still_ambiguous, resolution, ANNOTATION


def seed_rule(db, rule, *, reviewed=False):
    maker = db.scalar(select(Manufacturer).where(Manufacturer.name == rule['manufacturer'])) or Manufacturer(name=rule['manufacturer'])
    spec = Specification(**rule['before'])
    computer = Computer(manufacturer=maker, model_name=rule['model_name'], description='Descrizione curata.',
        configurations=[Configuration(variant_name=rule['configuration'], specifications=[spec])])
    source = Source(title='Originale sintetico per il test', url=rule['original_source_url'], source_type='website')
    db.add_all([computer, source]); db.flush()
    db.execute(spec_source.insert().values(target_id=spec.id, source_id=source.id,
        evidence='Evidenza originale da conservare.', verification_status='verified' if reviewed else 'pending'))
    db.commit()
    return computer.id, spec.id, source.id


def test_reviewed_proof_set_binds_exact_values_and_real_document_snapshots():
    data, checksum = load_proofs()
    assert len(data['rules']) == 541 and len(checksum) == 64
    assert len({(r['manufacturer'], r['model_name']) for r in data['rules']}) == 372
    for proof in data['proofs'].values():
        assert proof['source']['url'].startswith('https://')
        assert len(proof['snapshot_sha256']) == 64 and proof['quotes'] and proof['reason']
    for rule in data['rules']:
        assert rule['original_source_url'] and rule['configuration']
        assert resolution(rule) == rule['after']
        assert not still_ambiguous(rule['after'])
        for field in ('component_type', 'component_name'):
            assert rule['before'][field] == rule['after'][field]
        if rule.get('action') == 'annotate':
            assert rule['after']['property_name'] == ANNOTATION
            assert rule['after']['numeric_value'] is None and rule['after']['unit'] is None
        else:
            assert rule['before']['property_name'] == rule['after']['property_name']
    assert not any(r['model_name'] == 'Commodore 64Z' for r in data['rules'])


@pytest.mark.parametrize('text', ['16 Kbit', '64Kbit + 32 KB', '1 Mbit', '128 Kb ?'])
def test_explicit_bits_and_uncertain_quantities_are_not_relabelled_as_bytes(text):
    values = dict(component_type='RAM', component_name=None, property_name='Capacità riportata',
                  numeric_value=None, text_value=text, unit=None)
    with pytest.raises(ValueError):
        clarify(values, ['K', 'M'])


def test_a_prefix_proof_does_not_change_a_different_prefix_clocks_or_disks():
    values = dict(component_type='RAM', component_name=None, property_name='Capacità riportata',
                  numeric_value=None, text_value='16 Kb - 64 Kb + 1 MB', unit=None)
    after = clarify(values, ['K'])
    assert after['text_value'] == '16 KiB - 64 KiB + 1 MB' and still_ambiguous(after)
    for component in ('CPU', 'Storage'):
        with pytest.raises(ValueError):
            clarify({**values, 'component_type': component}, ['K'])


def test_apply_is_exact_audited_idempotent_and_does_not_trust_plan_operations(client):
    rule = load_proofs()[0]['rules'][0]
    with SessionLocal() as db:
        cid, sid, original_source_id = seed_rule(db, rule)
        c = db.get(Computer, cid)
        # Identical text in a different configuration is outside this rule.
        other = Specification(**rule['before'])
        c.configurations.append(Configuration(variant_name='Configurazione distinta', specifications=[other]))
        db.commit(); other_id = other.id
        original = spec_values(db.get(Specification, sid))
        count = db.scalar(select(func.count()).select_from(Specification))
        plan = prepare(db)
        assert plan['summary']['documented_corrections'] == 1
        edited = deepcopy(plan); edited['changes'][0]['after']['numeric_value'] = 999
        result = apply(db, edited)
        assert result['updated'] == 1 and result['audit_id']
        assert spec_values(db.get(Specification, sid)) == rule['after']
        assert spec_values(db.get(Specification, other_id)) == original
        assert db.get(Computer, cid).description == 'Descrizione curata.'
        assert db.scalar(select(func.count()).select_from(Specification)) == count
        links = db.execute(select(spec_source).where(spec_source.c.target_id == sid)).mappings().all()
        old = next(link for link in links if link['source_id'] == original_source_id)
        assert old['evidence'] == 'Evidenza originale da conservare.' and old['verification_status'] == 'pending'
        assert all(link['verification_status'] == 'pending' for link in links)
        audit = db.get(CatalogReconciliation, result['audit_id'])
        assert audit.entity == 'unit_review' and audit.snapshot['changes'][0]['before'] == original
        assert audit.snapshot['previous_source_links'][0]['evidence'] == old['evidence']
        fresh = prepare(db)
        assert fresh['summary']['documented_corrections'] == 0
        assert apply(db, fresh)['audit_id'] is None


def test_existing_document_link_keeps_evidence_and_review_status_without_duplicate_citations(client):
    rule = next(r for r in load_proofs()[0]['rules'] if r['model_name'] == 'DECstation 2100')
    with SessionLocal() as db:
        _, sid, source_id = seed_rule(db, rule, reviewed=True)
        result = apply(db, prepare(db))
        assert result['updated'] == 1
        links = db.execute(select(spec_source).where(spec_source.c.target_id == sid)).mappings().all()
        assert len(links) == 1 and links[0]['source_id'] == source_id
        assert links[0]['verification_status'] == 'verified'
        assert links[0]['evidence'].startswith('Evidenza originale da conservare.')
        assert 'Chiarimento documentato dell’unità' in links[0]['evidence']


@pytest.mark.parametrize('changed', ['source', 'quantity', 'model', 'configuration'])
def test_changed_quantity_or_source_refuses_the_old_plan(client, changed):
    rule = load_proofs()[0]['rules'][0]
    with SessionLocal() as db:
        cid, sid, source_id = seed_rule(db, rule)
        plan = prepare(db)
        if changed == 'source':
            db.get(Source, source_id).url = 'https://example.org/different-document'
        elif changed == 'quantity':
            db.get(Specification, sid).text_value = '129 Kb'
        elif changed == 'model':
            db.get(Computer, cid).model_name = 'Altro modello curato'
        else:
            db.get(Computer, cid).configurations[0].variant_name = 'Ambito curato diverso'
        db.commit(); before = spec_values(db.get(Specification, sid))
        with pytest.raises(ValueError, match='cambiati'):
            apply(db, plan)
        db.rollback()
        assert spec_values(db.get(Specification, sid)) == before
        assert prepare(db)['summary']['documented_corrections'] == 0


def test_a_changed_proof_set_invalidates_the_preview(client, monkeypatch, tmp_path):
    import app.unit_review as review
    data = load_proofs()[0]; rule = data['rules'][0]
    path = tmp_path / 'proofs.json'; path.write_text(json.dumps(data))
    monkeypatch.setattr(review, 'DATA', path)
    with SessionLocal() as db:
        _, sid, _ = seed_rule(db, rule); plan = prepare(db)
        data['proofs'][rule['proof_ids'][0]]['reason'] += ' Revisione della prova.'
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match='prove sono cambiati'):
            apply(db, plan)
        db.rollback()
        assert spec_values(db.get(Specification, sid)) == rule['before']


def test_partial_prefix_clarification_stays_in_the_remaining_review_list(client, monkeypatch, tmp_path):
    import app.unit_review as review
    data = load_proofs()[0]; rule = deepcopy(data['rules'][0])
    rule['before'].update(numeric_value=None, text_value='128 Kb + 1 MB', unit=None)
    rule['prefixes'] = ['K']; rule['after'] = clarify(rule['before'], ['K'])
    data['rules'] = [rule]; path = tmp_path / 'synthetic-proof.json'; path.write_text(json.dumps(data))
    monkeypatch.setattr(review, 'DATA', path)
    with SessionLocal() as db:
        _, sid, _ = seed_rule(db, rule)
        plan = prepare(db)
        assert any(row.get('id') == sid for row in plan['remaining'])
        assert plan['summary']['documented_corrections'] == 1


@pytest.mark.parametrize('model,component,number', [
    ('M20 BC', 'ROM', 8), ('M20 ST', 'ROM', 8), ('Commodore 116', 'RAM', 16),
    ('KIM-1', 'ROM', 2), ('CBM 8296-D', 'RAM', 128),
])
def test_documentary_corrections_distinguish_bits_available_memory_and_total_bytes(model, component, number):
    rule = next(r for r in load_proofs()[0]['rules'] if r['model_name'] == model and r['before']['component_type'] == component)
    assert rule['action'] == 'correct'
    assert resolution(rule)['numeric_value'] == number and resolution(rule)['unit'] == 'KiB'


def test_native_memory_and_rounded_quantities_do_not_become_false_exact_byte_counts():
    from app.ram_research import documented_ram
    rules = load_proofs()[0]['rules']
    for model in ('Elea 6001', 'P652'):
        rule = next(r for r in rules if r['model_name'] == model)
        after = resolution(rule)
        assert after['numeric_value'] is None and after['unit'] is None
        assert 'bit' in after['text_value'] and documented_ram(after)
    rule = next(r for r in rules if r['model_name'] == 'Toshiba T1000' and r['before']['component_type'] == 'RAM')
    assert '1280 KiB' in resolution(rule)['text_value']
    assert '1.2' not in resolution(rule)['text_value']


@pytest.mark.parametrize('compact_units', [False, True])
def test_annotation_api_keeps_originals_and_prevents_reimport_and_ram_recovery_of_withdrawn_quantity(client, compact_units):
    from app.importing.engine import stage, apply_job
    from app.import_models import ImportClaim
    from app.catalog_quality import ram_preview
    from app.ram_research import documented_ram
    rule = next(r for r in load_proofs()[0]['rules'] if r['model_name'] == 'BCS 2030' and r['action'] == 'annotate')
    with SessionLocal() as db:
        cid, sid, source_id = seed_rule(db, rule, reviewed=True)
    plan = client.get('/api/admin/catalog-quality/units').json()
    assert plan['summary']['annotations_proposed'] == 1
    assert plan['summary']['unquantified_entries'] == 1
    assert sid not in {row['id'] for row in plan['remaining']}
    report = client.get('/api/admin/catalog-quality/units/report')
    assert report.status_code == 200 and 'attachment' in report.headers['content-disposition']
    assert report.json()['changes'][0]['before'] == rule['before']
    response = client.post('/api/admin/catalog-quality/units/apply', json={'token': plan['token']})
    assert response.status_code == 200 and response.json()['updated'] == 1
    with SessionLocal() as db:
        value = spec_values(db.get(Specification, sid))
        assert value == rule['after'] and not documented_ram(value)
        old = db.execute(select(spec_source).where(spec_source.c.target_id == sid, spec_source.c.source_id == source_id)).mappings().one()
        assert old['verification_status'] == 'verified' and old['evidence'].startswith('Evidenza originale')
        incoming = deepcopy(rule['before'])
        if compact_units:
            incoming['text_value'] = incoming['text_value'].replace(' ', '')
        record = {'manufacturer': rule['manufacturer'], 'model_name': rule['model_name'],
                  'source': {'title': 'Originale sintetico per il test', 'url': rule['original_source_url'], 'source_type': 'website'},
                  'configurations': [{'variant_name': rule['configuration'], 'specifications': [incoming]}]}
        job = stage(db, 'manual', 'original.json', 'json', json.dumps([record]).encode())
        apply_job(db, job.id)
        assert job.status == 'completed'
        db.expire_all()
        assert sum(len(cfg.specifications) for cfg in db.get(Computer, cid).configurations) == 1
        assert spec_values(db.get(Specification, sid)) == rule['after']
        assert db.scalar(select(ImportClaim).where(ImportClaim.entity == 'Specification', ImportClaim.target_id == sid)).status == 'conflict'
        assert cid not in ram_preview(db)['records']
    fresh = client.get('/api/admin/catalog-quality/units').json()
    assert fresh['summary']['documented_corrections'] == 0 and fresh['summary']['unquantified_entries'] == 1
    assert client.post('/api/admin/catalog-quality/units/apply', json={'token': fresh['token']}).json()['audit_id'] is None


def test_api_rejects_stale_snapshot_and_unlisted_memory_is_not_assumed_binary(client):
    rule = load_proofs()[0]['rules'][0]
    with SessionLocal() as db:
        cid, sid, _ = seed_rule(db, rule)
    plan = client.get('/api/admin/catalog-quality/units').json()
    with SessionLocal() as db:
        db.get(Computer, cid).model_name = 'Modello non compreso nel set'
        db.commit()
    assert client.post('/api/admin/catalog-quality/units/apply', json={'token': plan['token']}).status_code == 409
    fresh = client.get('/api/admin/catalog-quality/units').json()
    assert fresh['summary']['documented_corrections'] == 0
    assert sid in {row['id'] for row in fresh['remaining']}
    with SessionLocal() as db:
        assert spec_values(db.get(Specification, sid)) == rule['before']


def test_invalid_annotation_cannot_be_used_to_smuggle_a_numeric_capacity():
    rule = deepcopy(next(r for r in load_proofs()[0]['rules'] if r.get('action') == 'annotate'))
    rule['after'].update(numeric_value=64, text_value=None, unit='KiB')
    with pytest.raises(ValueError, match='annotazione'):
        resolution(rule)


@pytest.mark.parametrize('interference', [None, 'annotation', 'source'])
def test_new_evidence_can_complete_an_old_unchanged_annotation_without_losing_its_audit(client, monkeypatch, tmp_path, interference):
    import app.unit_review as review
    data = load_proofs()[0]
    rule = deepcopy(next(r for r in data['rules'] if r['model_name'] == 'M111'))
    old_rule = {**deepcopy(rule), 'action': 'annotate', 'after': {**rule['before'],
        'property_name': ANNOTATION, 'numeric_value': None, 'unit': None,
        'text_value': 'Dato sintetico non quantificabile nella prima revisione.'}}
    path = tmp_path / 'evolving-proofs.json'
    path.write_text(json.dumps({**data, 'rules': [old_rule]}))
    monkeypatch.setattr(review, 'DATA', path)
    with SessionLocal() as db:
        _, sid, source_id = seed_rule(db, rule)
        first = apply(db, prepare(db))
        assert spec_values(db.get(Specification, sid)) == old_rule['after']
        if interference == 'annotation':
            db.get(Specification, sid).text_value = 'Annotazione curata manualmente.'
        elif interference == 'source':
            db.get(Source, source_id).url = 'https://example.org/different-source'
        db.commit()
        path.write_text(json.dumps({**data, 'rules': [rule]}))
        plan = prepare(db)
        if interference:
            assert not plan['changes'] and plan['summary']['unquantified_entries'] == 1
            assert plan['unquantified'][0]['id'] == sid
            return
        assert len(plan['changes']) == 1 and plan['summary']['unquantified_entries'] == 0
        assert plan['changes'][0]['before'] == old_rule['after']
        assert plan['changes'][0]['original_assertion'] == rule['before']
        second = apply(db, plan)
        assert second['updated'] == 1
        assert spec_values(db.get(Specification, sid)) == rule['after']
        assert db.get(CatalogReconciliation, first['audit_id']).snapshot['changes'][0]['before'] == rule['before']
        assert db.get(CatalogReconciliation, second['audit_id']).snapshot['changes'][0]['before'] == old_rule['after']
        fresh = prepare(db)
        assert not fresh['changes'] and fresh['summary']['unquantified_entries'] == 0
