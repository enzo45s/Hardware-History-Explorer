"""Explicit local catalog reset; no schema drops, file removal or automatic reset."""
import hashlib
import json
from datetime import date, datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import select, func, delete, update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .admin import Input
from .models import (Base, Computer, Manufacturer, Category, Market, Configuration, Specification,
                     Release, Sale, Review, Fact, ComputerImage, Source)
from .import_models import ImportJob, ImportRow, ImportClaim, ExternalIdentity, CatalogReconciliation, ArchiveReset

CATALOG = (Manufacturer, Category, Market, Computer, Configuration, Specification, Release, Sale, Review, Fact, ComputerImage)


def serial(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def fingerprint(db):
    # Include values, not just counts: an edit after preview must invalidate it.
    digest = hashlib.sha256()
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        digest.update(table.name.encode())
        for row in db.execute(select(table).order_by(*table.primary_key.columns)):
            digest.update(json.dumps({k: serial(v) for k, v in row._mapping.items()},
                                     sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())
            digest.update(b'\n')
    return digest.hexdigest()


def counts(db):
    result = {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in CATALOG}
    result['sources_retained'] = db.scalar(select(func.count()).select_from(Source))
    result['import_jobs_retained'] = db.scalar(select(func.count()).select_from(ImportJob))
    return result


def catalog_snapshot(db):
    # Original uploads stay in import_jobs; only their prior state is copied.
    # Bibliography is retained live and included for standalone readability.
    preserved = {'import_jobs', 'catalog_reconciliations', 'archive_resets'}
    snapshot = {table.name: [{k: serial(v) for k, v in row._mapping.items()}
                            for row in db.execute(select(table).order_by(*table.primary_key.columns))]
                for table in Base.metadata.sorted_tables if table.name not in preserved}
    snapshot['import_job_states'] = [{'id': job.id, 'status': job.status}
                                   for job in db.scalars(select(ImportJob).order_by(ImportJob.id))]
    return snapshot


class ResetRequest(Input):
    token: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirmation: Literal['SVUOTA ARCHIVIO']
    backup_confirmed: Literal[True]
    note: str = Field(min_length=5, max_length=2000)


def reset_catalog(db, data):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
        names = ', '.join(db.bind.dialect.identifier_preparer.quote(t.name)
                          for t in sorted(Base.metadata.tables.values(), key=lambda t: t.name))
        db.execute(text('LOCK TABLE ' + names + ' IN EXCLUSIVE MODE'))
    elif db.bind.dialect.name == 'sqlite':
        db.execute(text('BEGIN IMMEDIATE'))
    else:
        raise ValueError('Database non supportato per lo svuotamento')
    if fingerprint(db) != data.token:
        raise ValueError('L’archivio è cambiato: prepara una nuova anteprima prima di svuotarlo')
    audit = ArchiveReset(note=data.note, counts=counts(db), snapshot=catalog_snapshot(db),
        reconciliation_cutoff=db.scalar(select(func.max(CatalogReconciliation.id))) or 0)
    db.add(audit)
    # Keep historical decisions and original files, but remove their live mappings.
    db.execute(update(ImportJob).values(status='archived'))
    db.execute(update(ImportRow).values(computer_id=None, candidates=[]))
    db.execute(update(ImportClaim).values(computer_id=None))
    db.execute(delete(ExternalIdentity))
    db.execute(delete(Computer))  # DB cascades cover specifications, images and joins.
    for model in (Manufacturer, Category, Market):
        db.execute(delete(model))
    db.commit()
    return {'reset_id': audit.id, 'computers': 0, 'demo_seed_disabled': True, 'removed': audit.counts}


def create_archive_router(get_db):
    router = APIRouter(prefix='/api/admin/archive', tags=['Archivio locale'])

    @router.get('/preview')
    def preview(db: Session = Depends(get_db)):
        return {'counts': counts(db), 'token': fingerprint(db)}

    @router.post('/reset')
    def reset(data: ResetRequest, db: Session = Depends(get_db)):
        try:
            return reset_catalog(db, data)
        except (ValueError, IntegrityError) as exc:
            db.rollback()
            raise HTTPException(409, str(exc) if isinstance(exc, ValueError) else 'Archivio non svuotato: vincoli incompatibili, ricarica e riprova') from exc

    @router.get('/resets')
    def history(db: Session = Depends(get_db)):
        return [{'id': r.id, 'note': r.note, 'counts': r.counts, 'created_at': r.created_at.isoformat()}
                for r in db.scalars(select(ArchiveReset).order_by(ArchiveReset.id.desc()).limit(30))]

    @router.get('/resets/{reset_id}/original')
    def original(reset_id: int, db: Session = Depends(get_db)):
        audit = db.get(ArchiveReset, reset_id)
        if audit is None:
            raise HTTPException(404, 'Svuotamento non trovato')
        return JSONResponse({'reset_id': audit.id, 'note': audit.note, 'created_at': audit.created_at.isoformat(),
                             'counts': audit.counts, 'tables': audit.snapshot},
                            headers={'Content-Disposition': 'attachment; filename="archive-before-reset.json"',
                                     'X-Content-Type-Options': 'nosniff'})
    return router
