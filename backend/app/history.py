"""One Italian research request per leased step, with durable progress and claims."""
import json
import uuid
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, object_session, selectinload
from .admin import Input, catalog_lock
from .models import Computer
from .history_models import HistoryJob, HistoryItem, now
from . import history_sources
from .commons import retry_seconds
from .importing.engine import stage, attribute


def utc(value):
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class SkipHistory(Input):
    item_id: int = Field(gt=0)


def get_job(db, job_id):
    job = db.get(HistoryJob, job_id)
    if job is None:
        raise HTTPException(404, 'Ricerca storica non trovata')
    return job


def item_data(item):
    return {'id': item.id, 'computer_id': item.computer_id, 'model_name': item.model_name,
        'manufacturer': item.manufacturer, 'status': item.status, 'error': item.error,
        'description': item.result.get('description'), 'url': item.result.get('url'),
        'candidates': item.result.get('candidates', []), 'import_job_id': item.import_job_id}


def details(db, job):
    counts = dict(db.execute(select(HistoryItem.status, func.count()).where(HistoryItem.job_id == job.id).group_by(HistoryItem.status)).all())
    current = db.scalar(select(HistoryItem).where(HistoryItem.job_id == job.id, HistoryItem.status == 'pending').order_by(HistoryItem.position).limit(1))
    recent = db.scalars(select(HistoryItem).where(HistoryItem.job_id == job.id, HistoryItem.status.not_in(['pending', 'preserved'])).order_by(HistoryItem.position.desc()).limit(10))
    return {'id': job.id, 'status': job.status, 'total': sum(counts.values()), 'counts': counts, 'error': job.error,
        'current': item_data(current) if current and job.status in ('ready', 'paused') else None,
        'recent': [item_data(item) for item in recent],
        'next_request_at': utc(job.next_request_at).isoformat() if job.next_request_at else None,
        'lease_until': utc(job.lease_until).isoformat() if job.lease_token and job.lease_until else None}


def attribution(computer):
    """Only cite a research result while its text is still the displayed description."""
    db = object_session(computer)
    if db is None:
        return None
    rows = db.scalars(select(HistoryItem).where(HistoryItem.computer_id == computer.id,
        HistoryItem.status == 'updated').order_by(HistoryItem.id.desc()))
    for item in rows:
        if item.result.get('description') == computer.description:
            return {key: item.result[key] for key in ('title', 'url', 'license_url', 'method')}
    return None


def apply_description(db, item, computer, result, raw):
    citation = {'title': 'Wikipedia in italiano · ' + result['title'], 'url': result['url'],
        'publisher': 'Wikipedia', 'author': 'Collaboratori di Wikipedia', 'source_type': 'encyclopedia',
        'access_date': now().date().isoformat(), 'license': 'CC BY-SA 4.0 · ' + result['license_url']}
    record = {'manufacturer': computer.manufacturer.name, 'model_name': computer.model_name,
        'description': result['description'], 'source': citation, 'evidence': result['evidence'][:2800]}
    job = stage(db, 'italian_history', f'wikipedia-it-{item.id}.json', 'json',
        json.dumps(raw, ensure_ascii=False).encode(), records=[record], options={'existing_only': True, 'managed_history': True}, commit=False)
    row = job.rows[0]
    row.computer_id, row.candidates = computer.id, [computer.id]
    before = computer.description
    # The caller has rechecked the exact original and locked the catalog. Only
    # recognized generated text may be replaced; attribute records the old text.
    attribute(db, row, computer, 'description', result['description'], citation, record['evidence'])
    computer.description = result['description']
    # Replacing a recognized placeholder is not a human verification or conflict.
    from .import_models import ImportClaim
    claim = db.scalar(select(ImportClaim).where(ImportClaim.row_id == row.id))
    claim.status = 'pending'
    assert claim.previous['value'] == before
    row.status, job.status, item.import_job_id = 'updated', 'completed', job.id


def create_history_router(get_db):
    router = APIRouter(prefix='/api/admin/history', tags=['Cenni storici in italiano'])

    @router.get('')
    def status(db: Session = Depends(get_db)):
        computers = db.scalars(select(Computer).options(selectinload(Computer.manufacturer)))
        eligible = sum(history_sources.replaceable(c.model_name, c.manufacturer.name, c.description) for c in computers)
        job = db.scalar(select(HistoryJob).order_by(HistoryJob.id.desc()).limit(1))
        return {'eligible': eligible, 'job': details(db, job) if job else None}

    @router.post('', status_code=201)
    def create(db: Session = Depends(get_db)):
        catalog_lock(db)
        active = db.scalar(select(HistoryJob).where(HistoryJob.active_key == 'italian'))
        if active:
            return details(db, active)
        previous = db.scalar(select(HistoryJob).order_by(HistoryJob.id.desc()).limit(1))
        deadline = utc(previous.next_request_at) if previous else None
        job = HistoryJob(active_key='italian', next_request_at=deadline)
        db.add(job); db.flush()
        pending = 0
        for position, c in enumerate(db.scalars(select(Computer).options(selectinload(Computer.manufacturer)).order_by(Computer.id)), 1):
            eligible = history_sources.replaceable(c.model_name, c.manufacturer.name, c.description)
            db.add(HistoryItem(job_id=job.id, position=position, computer_id=c.id, model_name=c.model_name,
                manufacturer=c.manufacturer.name, previous=c.description, status='pending' if eligible else 'preserved'))
            pending += eligible
        if not pending:
            job.status, job.active_key = 'completed', None
        db.commit()
        return details(db, job)

    @router.post('/{job_id}/pause')
    def pause(job_id: int, db: Session = Depends(get_db)):
        get_job(db, job_id)
        db.execute(update(HistoryJob).where(HistoryJob.id == job_id, HistoryJob.status == 'ready')
            .values(status='paused').execution_options(synchronize_session=False))
        db.commit()
        return details(db, get_job(db, job_id))

    @router.post('/{job_id}/resume')
    def resume(job_id: int, db: Session = Depends(get_db)):
        get_job(db, job_id)
        db.execute(update(HistoryJob).where(HistoryJob.id == job_id, HistoryJob.status == 'paused', HistoryJob.active_key == 'italian')
            .values(status='ready', error=None).execution_options(synchronize_session=False))
        db.commit()
        return details(db, get_job(db, job_id))

    @router.post('/{job_id}/skip')
    def skip(job_id: int, data: SkipHistory, db: Session = Depends(get_db)):
        catalog_lock(db)
        job = get_job(db, job_id)
        if job.status != 'paused' or (job.lease_token and utc(job.lease_until) > now()):
            raise HTTPException(409, 'Metti in pausa e attendi la conclusione della richiesta prima di saltare.')
        item = db.scalar(select(HistoryItem).where(HistoryItem.job_id == job_id, HistoryItem.status == 'pending').order_by(HistoryItem.position).limit(1))
        if item is None or item.id != data.item_id:
            raise HTTPException(409, 'La ricerca è avanzata: aggiorna il pannello prima di saltare il sistema.')
        item.status, item.error = 'skipped', 'Saltato esplicitamente; descrizione conservata.'
        job.lease_token, job.lease_until = None, None
        job.error = None
        db.flush()
        finish(db, job)
        db.commit()
        return details(db, job)

    @router.get('/{job_id}/report')
    def report(job_id: int, db: Session = Depends(get_db)):
        job = get_job(db, job_id)
        items = db.scalars(select(HistoryItem).where(HistoryItem.job_id == job_id).order_by(HistoryItem.position))
        return JSONResponse({'job': details(db, job), 'items': [item_data(item) for item in items]},
            headers={'Content-Disposition': 'attachment; filename="ricerca-storica-italiana.json"'})

    @router.post('/{job_id}/step')
    async def step(job_id: int, db: Session = Depends(get_db)):
        job = get_job(db, job_id)
        if job.status != 'ready':
            return details(db, job)
        timestamp, token = now(), str(uuid.uuid4())
        acquired = db.execute(update(HistoryJob).where(HistoryJob.id == job_id, HistoryJob.status == 'ready',
            (HistoryJob.lease_until.is_(None) | (HistoryJob.lease_until <= timestamp)),
            (HistoryJob.next_request_at.is_(None) | (HistoryJob.next_request_at <= timestamp)))
            .values(lease_token=token, lease_until=timestamp + timedelta(seconds=90))
            .execution_options(synchronize_session=False)).rowcount
        db.commit()
        if not acquired:
            raise HTTPException(429, 'Richiesta già in corso o pausa richiesta dalla fonte.', headers={'Retry-After': '2'})
        item = db.scalar(select(HistoryItem).where(HistoryItem.job_id == job_id, HistoryItem.status == 'pending').order_by(HistoryItem.position).limit(1))
        if item is None:
            job = get_job(db, job_id)
            job.status, job.active_key, job.lease_token, job.lease_until = 'completed', None, None, None
            db.commit()
            return details(db, job)
        item_id, computer_id = item.id, item.computer_id
        model, maker, previous = item.model_name, item.manufacturer, item.previous
        computer = db.get(Computer, computer_id) if computer_id else None
        unchanged = computer and (computer.model_name, computer.manufacturer.name, computer.description) == (model, maker, previous)
        db.rollback()  # No transaction or lock across the network.
        result, raw, failure = {}, {}, None
        if unchanged:
            try:
                result, raw = await history_sources.research(model, maker)
            except HTTPException as exc:
                failure = exc
        catalog_lock(db)
        job = db.scalar(select(HistoryJob).where(HistoryJob.id == job_id).with_for_update().execution_options(populate_existing=True))
        if job.lease_token != token or job.status == 'archived':
            db.rollback()
            return details(db, get_job(db, job_id))
        item = db.get(HistoryItem, item_id)
        computer = db.scalar(select(Computer).where(Computer.id == computer_id).with_for_update().execution_options(populate_existing=True)) if computer_id else None
        job.lease_token, job.lease_until = None, None
        job.next_request_at = now() + timedelta(seconds=2)
        if failure:
            delay = retry_seconds((failure.headers or {}).get('Retry-After', '')) or 30
            job.next_request_at = now() + timedelta(seconds=max(2, delay))
            job.status, job.error, item.error = 'paused', str(failure.detail), str(failure.detail)
        elif not computer or (computer.model_name, computer.manufacturer.name, computer.description) != (model, maker, previous):
            item.status, item.error = 'changed', 'Scheda rimossa o modificata: nessun testo sovrascritto.'
        elif not history_sources.replaceable(model, maker, computer.description):
            item.status = 'preserved'
        else:
            item.result, item.raw_payload = result, raw
            item.error = result.get('reason')
            if result['status'] == 'found':
                apply_description(db, item, computer, result, raw)
                item.status = 'updated'
            else:
                item.status = result['status']
        db.flush()
        finish(db, job)
        db.commit()
        return details(db, job)

    return router


def finish(db, job):
    if not db.scalar(select(HistoryItem.id).where(HistoryItem.job_id == job.id, HistoryItem.status == 'pending').limit(1)):
        job.status, job.active_key = 'completed', None
