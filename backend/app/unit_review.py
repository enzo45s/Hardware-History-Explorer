"""Resolve documented legacy memory notation with an offline, reviewed proof set.

The proof set identifies exact model/configuration/value/source combinations.
It is not a global rule equating KB, Kb and KiB. Historical verification states
and imported originals remain intact; unit decisions have their own audit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .admin import catalog_lock
from .catalog_revision import prepare as catalog_snapshot, digest
from .import_models import CatalogReconciliation
from .models import Computer, Configuration, Manufacturer, Source, Specification, spec_source
from .importing.engine import source as import_source
from .importing.identity import computer_key
from .importing.normalize import Citation, Spec
from .importing.vocabulary import spec_values, SPEC_FIELDS
from .measurement_cleanup import normalize_measurement

VERSION = 'hhe-unit-review-v2'
LEGACY_DATA = Path(__file__).parent / 'importing/data/unit-proofs-v1.json'
DATA = Path(__file__).parent / 'importing/data/unit-proofs-v2.json'
ANNOTATION = 'Annotazione sulla memoria'
TOKEN = re.compile(r'(?<=\d)\s*([kKmMgG])(?:[bB])?\b')
IEC = {'K': 'KiB', 'M': 'MiB', 'G': 'GiB'}


def still_ambiguous(values):
    return values.get('unit') in ('KB', 'kB', 'MB', 'GB', 'kb', 'Kb', 'mb', 'Mb', 'gb', 'Gb') or bool(
        re.search(r'\d\s*[kKmMgG][bB]\b', values.get('text_value') or ''))


def clarify(values, prefixes):
    """Only change the scale notation authorized by this exact-value proof."""
    if values['component_type'] not in ('RAM', 'ROM', 'Memoria', 'Cache'):
        raise ValueError('La prova riguarda solo quantità di memoria.')
    if not prefixes or not set(prefixes) <= set(IEC):
        raise ValueError('Prefissi della prova non validi.')
    result = dict(values)
    unit = values.get('unit')
    if isinstance(unit, str) and re.fullmatch('[kKmMgG][bB]', unit) and unit[0].upper() in prefixes:
        result['unit'] = IEC[unit[0].upper()]
    text = values.get('text_value')
    if text:
        # Explicit bit quantities, incomplete source values and unclear density
        # statements are never silently rewritten into bytes.
        if re.search(r'(?<![A-Za-z])(?:[kKmMgG]?bits?|bit/s)\b|\?', text):
            raise ValueError('Testo con bit espliciti o quantità incerta: revisione manuale.')
        result['text_value'] = TOKEN.sub(lambda m: ' ' + IEC[m[1].upper()] if m[1].upper() in prefixes else m[0], text)
    return normalize_measurement(result)


def resolution(rule):
    action = rule.get('action', 'clarify')
    if action == 'clarify':
        return clarify(rule['before'], rule['prefixes'])
    if action not in ('correct', 'annotate') or not rule.get('interpretation'):
        raise ValueError('Decisione documentale non valida.')
    before, after = rule['before'], rule['after']
    if before['component_type'] not in ('RAM', 'ROM', 'Memoria', 'Cache') or after['component_type'] != before['component_type']:
        raise ValueError('La decisione riguarda solo lo stesso tipo di memoria.')
    if after['component_name'] != before['component_name'] or still_ambiguous(after):
        raise ValueError('La decisione deve preservare il componente e chiarire la notazione.')
    if action == 'annotate':
        if after['numeric_value'] is not None or after['unit'] is not None or after['property_name'] != ANNOTATION:
            raise ValueError('Un’annotazione non può diventare una capacità numerica.')
    elif after['property_name'] != before['property_name'] or normalize_measurement(after) != after:
        raise ValueError('La correzione deve mantenere l’ambito e usare unità standard.')
    Spec.model_validate(after)
    return after


def load_proofs():
    raw = DATA.read_bytes()
    payload = json.loads(raw)
    if payload.get('extends'):
        if payload['extends'] != LEGACY_DATA.name:
            raise ValueError('Set di prove di base non valido.')
        legacy_raw = LEGACY_DATA.read_bytes()
        legacy = json.loads(legacy_raw)
        if set(legacy['proofs']) & set(payload['proofs']):
            raise ValueError('Identificativo della prova duplicato.')
        payload = {**payload, 'proofs': {**legacy['proofs'], **payload['proofs']},
                   'rules': legacy['rules'] + payload['rules']}
        payload.pop('extends')  # The returned object is a materialized proof set.
        raw = legacy_raw + b'\0' + raw
    proofs = payload['proofs']
    seen = set()
    for rule in payload['rules']:
        if rule['id'] in seen:
            raise ValueError('Identificativo della regola duplicato.')
        seen.add(rule['id'])
        if not rule['proof_ids']:
            raise ValueError('Serve almeno una prova documentale.')
        for identifier in rule['proof_ids']:
            proof = proofs[identifier]
            Citation.model_validate(proof['source'])
            if proof['basis'] not in ('explicit_iec', 'binary_definition', 'byte_count', 'address_map',
                                      'semiconductor_convention', 'unquantifiable_source', 'native_organization') or not proof['quotes'] or not proof['reason']:
                raise ValueError('Prova della scala mancante.')
        result = resolution(rule)
        if result != rule['after']:
            raise ValueError('La trasformazione non coincide con il risultato documentato nella regola.')
        Spec.model_validate(result)
    return payload, hashlib.sha256(raw).hexdigest()


def prepare(db):
    payload, checksum = load_proofs()
    base = catalog_snapshot(db)
    metadata = [list(row) for row in db.execute(select(Source.id, Source.title, Source.url, Source.publisher).order_by(Source.id))]
    token = digest({'version': VERSION, 'catalog': base['token'], 'proof_set': checksum, 'sources': metadata})
    specs = db.execute(select(Specification, Configuration, Computer, Manufacturer)
        .join(Configuration, Specification.configuration_id == Configuration.id)
        .join(Computer, Configuration.computer_id == Computer.id)
        .join(Manufacturer, Computer.manufacturer_id == Manufacturer.id)).all()
    links = {}
    for sid, url in db.execute(select(spec_source.c.target_id, Source.url).join(Source, Source.id == spec_source.c.source_id)):
        links.setdefault(sid, set()).add(url)
    by_identity = {}; by_config = {}
    for spec, cfg, computer, maker in specs:
        identity = (computer_key(maker.name, computer.model_name), cfg.variant_name)
        by_identity.setdefault(identity, []).append((spec, computer))
        by_config.setdefault(cfg.id, []).append(spec_values(spec))
    annotated = {s.id: s for s, _, _, _ in specs if s.property_name == ANNOTATION}
    prior = {}
    if annotated:
        for audit in db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity == 'unit_review')
                                .order_by(CatalogReconciliation.id.desc())):
            for row in (audit.snapshot or {}).get('changes', []):
                target = annotated.get(row['id'])
                if target is not None and row.get('action') == 'annotate' and spec_values(target) == row['after']:
                    prior.setdefault(target.id, []).append(row)

    def original_annotation(spec, rule):
        return any(row['before'] == rule['before'] and row.get('original_source_url') == rule['original_source_url']
                   for row in prior.get(spec.id, []))

    changes = []; selected = set(); unavailable = []; already_resolved = []; unquantified = []; partial = []
    for rule in payload['rules']:
        identity = (computer_key(rule['manufacturer'], rule['model_name']), rule['configuration'])
        candidates = [(s, c) for s, c in by_identity.get(identity, [])
                      if rule['original_source_url'] in links.get(s.id, set())
                      and all(expected in by_config[s.configuration_id] for expected in rule.get('context_specs', []))]
        matches = [(s, c) for s, c in candidates if spec_values(s) == rule['before']
                   or (rule.get('action') != 'annotate' and original_annotation(s, rule))]
        after = resolution(rule)
        if rule.get('action') == 'annotate':
            for spec, computer in candidates:
                if spec_values(spec) in (rule['before'], after) or original_annotation(spec, rule):
                    unquantified.append({'id': spec.id, 'computer_id': computer.id, 'model': computer.model_name,
                        'reason': rule['interpretation'], 'original': rule['before'],
                        'annotation': spec.text_value if spec.property_name == ANNOTATION else after['text_value']})
        elif re.search(r'non (?:documentat|determinat|quantificat)', after.get('text_value') or ''):
            for spec, computer in candidates:
                if spec_values(spec) in (rule['before'], after) or original_annotation(spec, rule):
                    partial.append({'id': spec.id, 'computer_id': computer.id, 'model': computer.model_name,
                                    'value': after['text_value'], 'reason': rule.get('interpretation')})
        for spec, computer in matches:
            if spec.id in selected:
                raise ValueError('Più regole propongono modifiche alla stessa specifica.')
            if after == rule['before']:
                continue
            selected.add(spec.id)
            changes.append({'id': spec.id, 'computer_id': computer.id, 'model': computer.model_name,
                'action': rule.get('action', 'clarify'),
                'original_source_url': rule['original_source_url'],
                'rule_id': rule['id'], 'before': spec_values(spec), 'after': after,
                'original_assertion': rule['before'],
                'interpretation': rule.get('interpretation'), 'origin_context': rule.get('origin_context'),
                'proofs': [payload['proofs'][i] for i in rule['proof_ids']]})
        if not matches and any(spec_values(s) == after for s, _ in candidates):
            already_resolved.append(rule['id'])
        elif not matches:
            unavailable.append(rule['id'])
    # Older decisions or manual annotations must stay visible even if no rule
    # in the current proof set targets them. A proposed completion supersedes
    # its annotation only in the projected result, never by hiding a lacuna.
    visible_annotations = {row['id'] for row in unquantified}
    completing = {row['id'] for row in changes if row['after']['property_name'] != ANNOTATION}
    for spec, cfg, computer, maker in specs:
        if spec.id in annotated and spec.id not in visible_annotations | completing:
            unquantified.append({'id': spec.id, 'computer_id': computer.id, 'model': computer.model_name,
                'reason': 'Annotazione attuale conservata; nessuna nuova prova applicabile.',
                'original': prior.get(spec.id, [{}])[0].get('before'), 'annotation': spec.text_value})
        details=spec.catalog_details or {}
        if (details.get('clean')
                and any('annotazione sulla memoria' in note.lower() for note in details.get('notes',[]))
                and spec.id not in {r['id'] for r in unquantified}):
            note='\n'.join(details.get('notes',[]))
            unquantified.append({'id':spec.id,'computer_id':computer.id,'model':computer.model_name,
                'reason':'Quantità non documentata; indicazioni originali conservate nell’audit della pulizia.',
                'original':None,'annotation':note or spec.text_value})
        if (details.get('clean') and details.get('resolution_state')!='unknown' and spec.property_name!=ANNOTATION
                and re.search(r'non (?:documentat|determinat|quantificat)',spec.text_value or '',re.I)
                and spec.id not in {r['id'] for r in partial}):
            partial.append({'id':spec.id,'computer_id':computer.id,'model':computer.model_name,
                'value':spec.text_value,'reason':'Indicazione parziale conservata dopo la pulizia fisica.'})
    clarified = {row['id'] for row in changes if not still_ambiguous(row['after'])}
    identities = {s.id: (s, cfg, c, m) for s, cfg, c, m in specs}
    memory_review = [row for row in base['review'] if row.get('id') in identities
                     and identities[row['id']][0].component_type in ('RAM', 'ROM', 'Memoria', 'Cache')]
    remaining = [row for row in memory_review if row['id'] not in clarified]
    for row in remaining:
        if row.get('id') not in identities:
            continue
        spec, cfg, computer, maker = identities[row['id']]
        row.update(manufacturer=maker.name, configuration=cfg.variant_name, values=spec_values(spec),
                   sources=[{'title': src.title, 'url': src.url} for src in spec.sources])
    return {'version': VERSION, 'token': token, 'proof_set_sha256': checksum,
        'summary': {'memory_entries_requiring_review': len(memory_review),
                    'documented_corrections': len(changes), 'affected_computers': len({r['computer_id'] for r in changes}),
                    'remaining_entries': len(remaining), 'already_resolved_rules': len(already_resolved),
                    'units_clarified': sum(r['action'] == 'clarify' for r in changes),
                    'quantities_corrected': sum(r['action'] == 'correct' for r in changes),
                    'annotations_proposed': sum(r['action'] == 'annotate' for r in changes),
                    'unquantified_entries': len(unquantified), 'partially_quantified_entries': len(partial)},
        'changes': changes, 'remaining': remaining, 'rules_already_resolved': already_resolved,
        'unquantified': unquantified,
        'partially_quantified': partial,
        'rules_not_matching_current_values': unavailable}


def reviewed_import_target(db, specifications, incoming, citation):
    """An unchanged, withdrawn assertion must not recreate a capacity on reimport.

    Restrict this to exact audited originals, their source URL and a currently
    unchanged annotation in the same configuration. A genuinely new source or
    a human-edited value is outside the guard and follows normal conflict rules.
    """
    candidates = {s.id: s for s in specifications if s.property_name == ANNOTATION}
    if not candidates:
        return None
    values = Spec.model_validate(normalize_measurement({k: incoming.get(k) for k in SPEC_FIELDS})).model_dump(include=set(SPEC_FIELDS))
    audits = db.scalars(select(CatalogReconciliation).where(CatalogReconciliation.entity == 'unit_review')
                       .order_by(CatalogReconciliation.id.desc()))
    for audit in audits:
        for row in (audit.snapshot or {}).get('changes', []):
            target = candidates.get(row['id'])
            if (target is None or row.get('action') != 'annotate'
                or row.get('original_source_url') != citation.get('url')
                or spec_values(target) != row['after']):
                continue
            before = Spec.model_validate(normalize_measurement(row['before'])).model_dump(include=set(SPEC_FIELDS))
            if before == values:
                return target
    return None


def apply(db, plan):
    catalog_lock(db)
    current = prepare(db)
    if plan.get('version') != VERSION or plan.get('token') != current['token']:
        raise ValueError('Il catalogo o le prove sono cambiati: prepara una nuova anteprima.')
    if not current['changes']:
        db.rollback()
        return {'updated': 0, 'sources_linked': 0, 'audit_id': None}
    identifiers = [row['id'] for row in current['changes']]
    before_links = [dict(row._mapping) for row in db.execute(select(spec_source).where(spec_source.c.target_id.in_(identifiers)))]
    linked = []
    for row in current['changes']:
        spec = db.get(Specification, row['id'])
        for field, value in row['after'].items():
            setattr(spec, field, value)
        for proof in row['proofs']:
            # Prefer an already attached citation for this document; keep its
            # chapter title and every previous review decision/evidence intact.
            src = db.scalar(select(Source).join(spec_source, spec_source.c.source_id == Source.id)
                .where(spec_source.c.target_id == spec.id, Source.url == proof['source']['url']).order_by(Source.id))
            if src is None:
                src = import_source(db, proof['source'])
            evidence = json.dumps({'unit_review': VERSION, 'rule_id': row['rule_id'], 'proof': proof}, ensure_ascii=False)
            old = db.execute(select(spec_source).where(spec_source.c.target_id == spec.id, spec_source.c.source_id == src.id)).mappings().one_or_none()
            if old:
                db.execute(spec_source.update().where(spec_source.c.target_id == spec.id, spec_source.c.source_id == src.id)
                    .values(evidence=(old['evidence'] or '') + '\n\nChiarimento documentato dell’unità:\n' + evidence))
            else:
                db.execute(spec_source.insert().values(target_id=spec.id, source_id=src.id, evidence=evidence, verification_status='pending'))
            linked.append({'specification_id': spec.id, 'source_id': src.id})
    audit = CatalogReconciliation(entity='unit_review', source_id=0, target_id=0,
        note='Revisione documentata della memoria: unità, correzioni puntuali e indicazioni non quantificabili. Stati di verifica storica conservati.',
        snapshot={'version': VERSION, 'token': current['token'], 'proof_set_sha256': current['proof_set_sha256'],
                  'changes': current['changes'], 'previous_source_links': before_links, 'proof_links': linked})
    db.add(audit); db.flush(); identifier = audit.id; db.commit()
    return {'updated': len(identifiers), 'sources_linked': len(linked), 'audit_id': identifier}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('preview').add_argument('--output', type=Path, required=True)
    commands.add_parser('apply').add_argument('--plan', type=Path, required=True)
    args = parser.parse_args(); url = os.getenv('DATABASE_URL')
    if not url:
        parser.error('DATABASE_URL deve indicare esplicitamente il database.')
    engine = create_engine(url)
    with Session(engine) as db:
        if args.command == 'preview':
            plan = prepare(db)
            with args.output.open('x', encoding='utf-8') as out:
                json.dump(plan, out, ensure_ascii=False, indent=2)
            print(json.dumps(plan['summary'], ensure_ascii=False))
        else:
            try:
                print(json.dumps(apply(db, json.loads(args.plan.read_text(encoding='utf-8'))), ensure_ascii=False))
            except ValueError as exc:
                db.rollback(); raise SystemExit(str(exc))
    engine.dispose()


if __name__ == '__main__':
    main()
