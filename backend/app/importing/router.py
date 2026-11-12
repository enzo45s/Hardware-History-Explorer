import hashlib
import csv
from collections import Counter
from typing import Literal
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session
from ..admin import Input
from ..models import Computer
from ..import_models import ImportJob, ImportRow, ImportClaim
from .normalize import MAX_BYTES, parse_payload
from .engine import stage, apply_job, review_claim
from .providers import PROVIDERS, fetch_provider, retroflops_records, wikidata_records
from .presentation import claim_presentation


def job_data(job):
    counts = Counter(r.status for r in job.rows)
    db = object_session(job)
    verification = dict(db.execute(select(ImportClaim.status, func.count()).join(ImportRow, ImportClaim.row_id == ImportRow.id)
        .where(ImportRow.job_id == job.id).group_by(ImportClaim.status)).all()) if db else {}
    return {'id': job.id, 'provider': job.provider, 'filename': job.filename, 'checksum': job.checksum,
            'format': job.format, 'status': job.status, 'error': job.error, 'retry_of': job.retry_of,
            'created_at': job.created_at.isoformat(), 'total': len(job.rows), 'counts': dict(counts), 'verification_counts': verification}


def claim_data(c):
    return {'id': c.id, 'computer_id': c.computer_id, 'entity': c.entity, 'target_id': c.target_id,
            'field': c.field, 'value': c.value, 'previous': c.previous, 'status': c.status,
            'estimated': c.estimated, 'evidence': c.evidence, 'review_note': c.review_note,
            'reviewed_at': c.reviewed_at.isoformat() if c.reviewed_at else None,
            'source': {'id': c.source.id, 'title': c.source.title, 'url': c.source.url}, 'display': claim_presentation(c)}


class RemoteRequest(Input):
    provider: Literal['wikidata', 'retroflops']
    ids: list[str] = Field(default_factory=list, max_length=20)


class Mapping(Input):
    computer_id: int = Field(gt=0)


class Decision(Input):
    decision: Literal['accept', 'reject']
    note: str = Field(min_length=5, max_length=2000)


def create_import_router(get_db):
    router = APIRouter(prefix='/api/admin/imports', tags=['Importazioni locali'])

    def job_or_404(db, job_id):
        job = db.get(ImportJob, job_id)
        if job is None:
            raise HTTPException(404, 'Importazione non trovata')
        return job

    def remote_job(db, provider, options, retry_of=None):
        try:
            raw, records = fetch_provider(provider, options)
            return stage(db, provider, provider + '.json', 'json', raw, records=records, options=options, retry_of=retry_of)
        except Exception as exc:
            db.rollback()
            # Network errors never leak proxy credentials, response bodies or connection strings.
            message = str(exc)[:1000] if isinstance(exc, ValueError) else 'Fonte non raggiungibile o risposta rifiutata. Verifica rete, policy e limiti del servizio; poi usa Riprova.'
            job = ImportJob(provider=provider, filename=provider + '.json', format='json', checksum=hashlib.sha256(b'').hexdigest(), raw_payload='',
                            status='failed', error=message, request_options=options, retry_of=retry_of)
            db.add(job)
            db.commit()
            return job

    @router.get('/providers')
    def providers():
        return PROVIDERS

    @router.get('')
    def jobs(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
        return [job_data(j) for j in db.scalars(select(ImportJob).order_by(ImportJob.id.desc()).offset(offset).limit(limit))]

    @router.post('/upload', status_code=201)
    def upload(file: UploadFile = File(...), provider: str = Form('manual'),
               rights_confirmed: bool = Form(False), db: Session = Depends(get_db)):
        if provider not in {p['id'] for p in PROVIDERS}:
            raise HTTPException(422, 'Fonte sconosciuta')
        if not rights_confirmed:
            raise HTTPException(422, 'Conferma di avere il diritto di importare il dataset')
        try:
            raw = file.file.read(MAX_BYTES + 1)
        finally:
            file.file.close()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, 'Massimo 8 MB')
        filename = (file.filename or 'dataset').replace('\\', '/').split('/')[-1][:250]
        format = filename.rsplit('.', 1)[-1].lower()
        try:
            if provider in ('wikidata', 'retroflops') and format == 'json':
                import json
                payload = json.loads(raw.decode('utf-8-sig'))
                records = retroflops_records(payload) if provider == 'retroflops' else wikidata_records(payload)
                job = stage(db, provider, filename, format, raw, records=records,
                            options={'upload': True, 'rights_confirmed': True})
            else:
                job = stage(db, provider, filename, format, raw, options={'upload': True, 'rights_confirmed': True})
        except (ValueError, TypeError, KeyError, RecursionError, csv.Error) as exc:
            db.rollback()
            raise HTTPException(422, 'Dataset non valido: ' + str(exc)[:2000]) from exc
        return job_data(job)

    @router.post('/remote', status_code=201)
    def remote(data: RemoteRequest, db: Session = Depends(get_db)):
        return job_data(remote_job(db, data.provider, {'ids': data.ids}))

    @router.get('/{job_id}')
    def detail(job_id: int, offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100), db: Session = Depends(get_db)):
        job = job_or_404(db, job_id)
        rows = db.scalars(select(ImportRow).where(ImportRow.job_id == job_id).order_by(ImportRow.position).offset(offset).limit(limit))
        def computer_label(computer_id):
            c = db.get(Computer, computer_id) if computer_id else None
            return f'{c.manufacturer.name} · {c.model_name}' if c else None
        return {**job_data(job), 'rows': [{'id': r.id, 'position': r.position, 'raw': r.raw, 'normalized': r.normalized,
                  'status': r.status, 'error': r.error, 'computer_id': r.computer_id, 'candidates': r.candidates,
                  'computer_label': computer_label(r.computer_id),
                  'candidate_labels': [computer_label(cid) or f'Voce rimossa (ID {cid})' for cid in r.candidates],
                  'claims': [claim_data(c) for c in r.claims]} for r in rows]}

    @router.get('/{job_id}/original')
    def original(job_id: int, db: Session = Depends(get_db)):
        from fastapi.responses import Response
        job = job_or_404(db, job_id)
        return Response(job.raw_payload, media_type='text/plain; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="import-original.txt"', 'X-Content-Type-Options': 'nosniff'})

    @router.post('/{job_id}/apply')
    def apply(job_id: int, db: Session = Depends(get_db)):
        job_or_404(db, job_id)
        try:
            return job_data(apply_job(db, job_id))
        except ValueError as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc

    @router.post('/{job_id}/retry', status_code=201)
    def retry(job_id: int, db: Session = Depends(get_db)):
        previous = job_or_404(db, job_id)
        options = previous.request_options
        if not options.get('upload'):
            return job_data(remote_job(db, previous.provider, options, retry_of=previous.id))
        raw = previous.raw_payload.encode('utf-8')
        records = None
        if previous.provider in ('wikidata', 'retroflops') and previous.format == 'json':
            import json
            payload = json.loads(raw)
            records = retroflops_records(payload) if previous.provider == 'retroflops' else wikidata_records(payload)
        return job_data(stage(db, previous.provider, previous.filename, previous.format, raw, records=records,
                              options=options, retry_of=previous.id))

    @router.post('/{job_id}/rows/{row_id}/skip')
    def skip(job_id: int, row_id: int, db: Session = Depends(get_db)):
        job = job_or_404(db, job_id)
        row = db.get(ImportRow, row_id)
        if row is None or row.job_id != job_id:
            raise HTTPException(404, 'Riga non trovata')
        if job.status != 'ready':
            raise HTTPException(409, 'Puoi escludere righe solo prima di applicare l’importazione')
        row.status = 'skipped'
        db.commit()
        return {'status': 'skipped'}

    @router.post('/{job_id}/rows/{row_id}/match')
    def match(job_id: int, row_id: int, data: Mapping, db: Session = Depends(get_db)):
        job = job_or_404(db, job_id)
        row = db.get(ImportRow, row_id)
        if row is None or row.job_id != job_id:
            raise HTTPException(404, 'Riga non trovata')
        if job.status != 'ready' or row.status not in ('ready', 'ambiguous'):
            raise HTTPException(409, 'Crea una nuova anteprima con Riprova prima di cambiare la corrispondenza')
        if db.get(Computer, data.computer_id) is None:
            raise HTTPException(422, 'Calcolatore inesistente')
        row.computer_id, row.status = data.computer_id, 'ready'
        db.commit()
        return {'status': 'ready', 'computer_id': row.computer_id}

    @router.post('/claims/{claim_id}/review')
    def review(claim_id: int, data: Decision, db: Session = Depends(get_db)):
        c = db.scalar(select(ImportClaim).where(ImportClaim.id == claim_id).with_for_update())
        if c is None:
            raise HTTPException(404, 'Asserzione non trovata')
        try:
            review_claim(db, c, data.decision, data.note)
        except (ValueError, IntegrityError) as exc:
            db.rollback()
            raise HTTPException(409, str(exc) if isinstance(exc, ValueError) else 'Decisione incompatibile con i vincoli: controlla i dati correlati') from exc
        return claim_data(c)

    return router
