import json
from copy import deepcopy

import pytest
from sqlalchemy import func, select

from app.main import SessionLocal
from app.models import Computer, Manufacturer, Configuration, Specification, Source, spec_source
from app.import_models import CatalogReconciliation
from app.importing.vocabulary import spec_values
from app.unit_review import apply, clarify, load_proofs, prepare, still_ambiguous


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
    assert len(data['rules']) == 147 and len(checksum) == 64
    assert len({(r['manufacturer'], r['model_name']) for r in data['rules']}) == 101
    for proof in data['proofs'].values():
        assert proof['source']['url'].startswith('https://')
        assert len(proof['snapshot_sha256']) == 64 and proof['quotes'] and proof['reason']
    for rule in data['rules']:
        assert rule['original_source_url'] and rule['configuration']
        assert clarify(rule['before'], rule['prefixes']) == rule['after']
        assert not still_ambiguous(rule['after'])
        for field in ('component_type', 'component_name', 'property_name'):
            assert rule['before'][field] == rule['after'][field]
    assert not any(r['model_name'] == 'Commodore 64G' for r in data['rules'])


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
