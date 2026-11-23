"""Respect previously audited withdrawals during ordinary reimports."""
from sqlalchemy import select
from ..import_models import CatalogReconciliation
from ..importing.normalize import Spec
from ..importing.vocabulary import spec_values, SPEC_FIELDS
from ..measurement_cleanup import normalize_measurement

ANNOTATION = 'Annotazione sulla memoria'

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

