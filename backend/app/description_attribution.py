"""Read attribution retained with the catalog after retirement of research tools."""
import hashlib
from sqlalchemy import select
from sqlalchemy.orm import object_session
from .import_models import CatalogReconciliation, ArchiveReset


def attribution(computer):
    db = object_session(computer)
    if db is None or not computer.description:
        return None
    cache = db.info.get('retained_description_attributions')
    if cache is None:
        cache = {}
        cutoff = db.scalar(select(ArchiveReset.reconciliation_cutoff).order_by(ArchiveReset.id.desc()).limit(1)) or 0
        for snapshot in db.scalars(select(CatalogReconciliation.snapshot).where(
                CatalogReconciliation.entity == 'admin_retirement', CatalogReconciliation.id > cutoff).order_by(CatalogReconciliation.id)):
            for item in snapshot.get('description_attributions', []):
                cache.setdefault(item['description_sha256'], []).append(item)
        db.info['retained_description_attributions'] = cache
    fingerprint = hashlib.sha256(computer.description.encode()).hexdigest()
    sources = {source.url for source in computer.sources}
    for item in reversed(cache.get(fingerprint, [])):
        if item['computer_id'] == computer.id or item['url'] in sources:
            return {key: item[key] for key in ('title', 'url', 'license_url', 'method')}
    return None
