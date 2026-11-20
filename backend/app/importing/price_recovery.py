"""Recover explicit workbook fields from applied notes, with append-only audit."""
import json
from collections import Counter

from sqlalchemy import select

from ..admin import catalog_lock
from ..models import Computer, Fact
from ..import_models import ImportJob, ImportRow, ImportClaim
from .normalize import Citation, Record
from .prices import release_from_fields

VERSION = 1


def recovery_record(db, claim, row, fact):
    """Use audited workbook cells, not amounts mentioned in free-form notes."""
    normalized = row.normalized if isinstance(row.normalized, dict) else {}
    if normalized.get('releases'):
        return None, 'already_structured'
    if (claim.status not in ('pending', 'verified') or claim.estimated or fact.computer_id != row.computer_id
            or claim.computer_id != fact.computer_id or not isinstance(claim.value, dict) or claim.value.get('value') != fact.statement
            or fact.fact_type != 'Contesto del prezzo'):
        return None, 'modified_or_rejected'
    computer = db.get(Computer, fact.computer_id)
    if computer is None or claim.source_id not in {source.id for source in fact.sources}:
        return None, 'removed_target_or_source'
    try:
        evidence = normalized.get('evidence', '')
        if not isinstance(evidence, str):
            return None, 'missing_workbook_fields'
        metadata = json.loads(evidence)
        if (not isinstance(metadata, dict) or metadata.get('adapter') != 'historical-prices-v1'
                or metadata.get('sheet') != 'Prezzi per modello' or not isinstance(metadata.get('original'), dict)):
            return None, 'missing_workbook_fields'
        # A source edited after import must not be silently replaced by its
        # previous URL. Keep the existing citation ID, title and metadata.
        citation = Citation.model_validate(normalized.get('source')).model_dump(mode='json', exclude_none=True)
        if not citation.get('url') or citation['url'] != claim.source.url:
            return None, 'modified_source'
        citation['title'] = claim.source.title
        release = release_from_fields(metadata['original'], citation, evidence)
        if release is None:
            return None, 'context_only'
        record = {'manufacturer': normalized['manufacturer'], 'model_name': normalized['model_name'],
            'external_id': f'context-price:v{VERSION}:{claim.id}', 'source': citation,
            'evidence': evidence, 'releases': [release]}
        Record.model_validate(record)
        return record, None
    except (ValueError, TypeError, KeyError):
        return None, 'invalid_fields'


def recover_price_contexts(db, *, origin_job_id=None):
    """Idempotent per original claim; preserve notes, edits and prior decisions."""
    from .engine import stage, apply_job
    catalog_lock(db)
    processed = set()
    for options in db.scalars(select(ImportJob.request_options).where(ImportJob.provider == 'historical_prices')):
        marker = options.get('price_context_recovery', {})
        if isinstance(marker, dict):
            processed.update(marker.get('claim_ids', []))
    stmt = (select(ImportClaim, ImportRow, Fact)
        .join(ImportRow, ImportRow.id == ImportClaim.row_id)
        .join(ImportJob, ImportJob.id == ImportRow.job_id)
        .join(Fact, Fact.id == ImportClaim.target_id)
        .where(ImportJob.provider == 'historical_prices', ImportJob.status.in_(['completed', 'partial']),
            ImportRow.status.in_(['imported', 'updated', 'unchanged']),
            ImportClaim.entity == 'Fact', ImportClaim.field == 'statement',
            Fact.fact_type == 'Contesto del prezzo').order_by(ImportClaim.id))
    if origin_job_id is not None:
        stmt = stmt.where(ImportJob.id == origin_job_id)
    candidates = []
    counts = Counter()
    for claim, row, fact in db.execute(stmt).all():
        if claim.id in processed:
            counts['already_processed'] += 1
            continue
        record, reason = recovery_record(db, claim, row, fact)
        if reason:
            counts[reason] += 1
        else:
            candidates.append((claim.id, row.computer_id, record))
    job_ids = []
    for start in range(0, len(candidates), 100):
        batch = candidates[start:start + 100]
        records = [record for _, _, record in batch]
        raw = json.dumps(records, ensure_ascii=False).encode()
        job = stage(db, 'historical_prices', 'recupero-prezzi-note.json', 'json', raw, records=records,
            options={'upload': True, 'existing_only': True,
                'price_context_recovery': {'version': VERSION, 'claim_ids': [cid for cid, _, _ in batch]}}, commit=False)
        # Inherit the original applied association, including approved manual
        # mappings. The normal engine still preserves aliases and price conflicts.
        for imported, (_, computer_id, _) in zip(job.rows, batch):
            if imported.status != 'invalid':
                imported.computer_id, imported.status = computer_id, 'ready'
        apply_job(db, job.id, commit=False)
        counts.update(row.status for row in job.rows)
        job_ids.append(job.id)
    db.commit()
    return {'version': VERSION, 'candidates': len(candidates), 'counts': dict(counts), 'job_ids': job_ids}
