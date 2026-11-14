"""Durable, opt-in Commons cover search. One bounded request per step; no worker."""
from datetime import datetime, timedelta, timezone
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func, select, update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .models import Base, Computer, ComputerImage


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class PhotoJob(Base):
    __tablename__ = 'commons_photo_jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    # Only one unfinished queue, even across concurrent API processes.
    active_key: Mapped[str | None] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(20), default='ready')
    error: Mapped[str | None] = mapped_column(Text)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PhotoItem(Base):
    __tablename__ = 'commons_photo_items'
    __table_args__ = (UniqueConstraint('job_id', 'position'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('commons_photo_jobs.id', ondelete='CASCADE'), index=True)
    position: Mapped[int]
    computer_id: Mapped[int | None] = mapped_column(ForeignKey('computers.id', ondelete='SET NULL'), index=True)
    model_name: Mapped[str] = mapped_column(String(180))
    query: Mapped[str] = mapped_column(String(90))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    error: Mapped[str | None] = mapped_column(Text)
    image_id: Mapped[int | None] = mapped_column(ForeignKey('computer_images.id', ondelete='SET NULL'))
    source_url: Mapped[str | None] = mapped_column(String(1600))


def missing_images():
    return ~Computer.images.any() & ((Computer.image_url.is_(None)) | (Computer.image_url == ''))


def reusable(item):
    """Automation requires attribution and a recognizable free licence, unlike manual review."""
    licence = (item.get('license_name') or '').strip().casefold()
    if re.search(r'\b(?:nc|nd)\b', licence):
        return False
    free = (re.match(r'^cc[ -]by(?:[ -]sa)?[ -]?\d+(?:\.\d+)?\b', licence)
            or licence in ('cc0', 'cc0 1.0', 'public domain', 'public domain mark', 'pdm')
            or licence.startswith('pd-'))
    return bool(free and item.get('author') and item.get('source_url'))


def job_data(db, job):
    counts = dict(db.execute(select(PhotoItem.status, func.count()).where(PhotoItem.job_id == job.id)
                            .group_by(PhotoItem.status)).all())
    recent = db.scalars(select(PhotoItem).where(PhotoItem.job_id == job.id, PhotoItem.status != 'pending')
                        .order_by(PhotoItem.position.desc()).limit(10)).all()
    return {'id': job.id, 'status': job.status, 'counts': counts, 'total': sum(counts.values()),
            'error': job.error, 'next_request_at': utc(job.next_request_at).isoformat() if job.next_request_at else None,
            'recent': [{'computer_id': row.computer_id, 'model_name': row.model_name, 'status': row.status,
                        'error': row.error, 'source_url': row.source_url} for row in recent]}


def get_job(db, job_id):
    job = db.get(PhotoJob, job_id)
    if job is None:
        raise HTTPException(404, 'Ricerca fotografica non trovata')
    return job


def create_photo_router(get_db, search):
    router = APIRouter(prefix='/api/admin/photos', tags=['Fotografie automatiche locali'])

    @router.get('')
    def status(db: Session = Depends(get_db)):
        job = db.scalar(select(PhotoJob).order_by(PhotoJob.id.desc()).limit(1))
        return {'missing': db.scalar(select(func.count()).select_from(Computer).where(missing_images())),
                'job': job_data(db, job) if job else None}

    @router.post('', status_code=201)
    def create(db: Session = Depends(get_db)):
        active = db.scalar(select(PhotoJob).where(PhotoJob.active_key == 'commons'))
        if active:
            return job_data(db, active)
        job = PhotoJob(active_key='commons')
        try:
            db.add(job); db.flush()
        except IntegrityError:
            db.rollback()
            return job_data(db, db.scalar(select(PhotoJob).where(PhotoJob.active_key == 'commons')))
        for position, computer in enumerate(db.scalars(select(Computer).where(missing_images()).order_by(Computer.id)), 1):
            db.add(PhotoItem(job_id=job.id, position=position, computer_id=computer.id,
                             model_name=computer.model_name, query=computer.model_name.strip()[:90]))
        db.commit()
        return job_data(db, job)

    @router.post('/{job_id}/pause')
    def pause(job_id: int, db: Session = Depends(get_db)):
        job = get_job(db, job_id)
        db.execute(update(PhotoJob).where(PhotoJob.id == job_id, PhotoJob.status == 'ready',
                   PhotoJob.active_key == 'commons').values(status='paused').execution_options(synchronize_session=False))
        db.commit(); db.refresh(job)
        return job_data(db, job)

    @router.post('/{job_id}/resume')
    def resume(job_id: int, db: Session = Depends(get_db)):
        job = get_job(db, job_id)
        db.execute(update(PhotoJob).where(PhotoJob.id == job_id, PhotoJob.status == 'paused',
                   PhotoJob.active_key == 'commons').values(status='ready', error=None).execution_options(synchronize_session=False))
        db.commit(); db.refresh(job)
        return job_data(db, job)

    @router.post('/{job_id}/step')
    async def step(job_id: int, db: Session = Depends(get_db)):
        job = get_job(db, job_id)
        if job.status != 'ready':
            return job_data(db, job)
        timestamp, token = now(), str(uuid.uuid4())
        acquired = db.execute(update(PhotoJob).where(PhotoJob.id == job_id, PhotoJob.status == 'ready',
            (PhotoJob.lease_until.is_(None) | (PhotoJob.lease_until <= timestamp)),
            (PhotoJob.next_request_at.is_(None) | (PhotoJob.next_request_at <= timestamp)))
            .values(lease_token=token, lease_until=timestamp + timedelta(seconds=90))
            .execution_options(synchronize_session=False)).rowcount
        db.commit()
        if not acquired:
            raise HTTPException(429, 'Ricerca già in corso o in attesa: riprova fra qualche secondo.', headers={'Retry-After': '2'})
        row = db.scalar(select(PhotoItem).where(PhotoItem.job_id == job_id, PhotoItem.status == 'pending')
                        .order_by(PhotoItem.position).limit(1))
        if row is None:
            job = get_job(db, job_id)
            job.status = 'completed'; job.active_key = None; job.lease_token = None; job.lease_until = None
            db.commit()
            return job_data(db, job)
        row_id, computer_id, model_name, query = row.id, row.computer_id, row.model_name, row.query
        c = db.get(Computer, computer_id) if computer_id else None
        already_present = c is not None and (c.image_url or db.scalar(select(ComputerImage.id).where(ComputerImage.computer_id == c.id).limit(1)))
        skip = not c or c.model_name != model_name or already_present or len(query) < 2
        db.rollback()  # Never keep a database transaction/row lock open across the network.
        response, failure = None, None
        if not skip:
            try:
                response = await search(query, 12)
            except HTTPException as exc:
                failure = exc
        # Lock in the same order as reset/manual image operations. The lease
        # must still belong to us (a reset can archive it during the request).
        if db.bind.dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
        else:
            db.execute(text('BEGIN IMMEDIATE'))
        c = db.scalar(select(Computer).where(Computer.id == computer_id).with_for_update()) if computer_id else None
        job = db.scalar(select(PhotoJob).where(PhotoJob.id == job_id).with_for_update().execution_options(populate_existing=True))
        if job.status == 'archived' or job.lease_token != token:
            db.rollback()
            return job_data(db, get_job(db, job_id))
        row = db.get(PhotoItem, row_id)
        job.lease_token = None; job.lease_until = None
        job.next_request_at = now() + timedelta(seconds=2)
        if failure:
            job.status = 'paused'; job.error = str(failure.detail); row.error = job.error
            retry = (failure.headers or {}).get('Retry-After', '30')
            delay = min(86400, max(2, int(retry))) if retry.isascii() and retry.isdigit() else 30
            job.next_request_at = now() + timedelta(seconds=delay)
        elif skip or c is None or c.model_name != model_name or c.image_url or db.scalar(select(ComputerImage.id).where(ComputerImage.computer_id == c.id).limit(1)):
            row.status = 'skipped'; row.error = 'Scheda rimossa, rinominata, non ricercabile o già provvista di foto.'
        else:
            selected = next((item for item in response['items'] if reusable(item)), None)
            if selected is None:
                row.status = 'no_match'; row.error = 'Nessun risultato con immagine, attribuzione e licenza utilizzabili automaticamente.'
            else:
                image = ComputerImage(computer_id=c.id, remote_url=selected['image_url'], thumbnail_url=selected['thumbnail_url'],
                    caption=('Scelta automatica Commons · ' + selected['title'])[:300], author=selected['author'],
                    license_name=selected['license_name'], license_url=selected['license_url'], source_url=selected['source_url'], is_primary=True)
                db.add(image); db.flush()
                row.status = 'added'; row.image_id = image.id; row.source_url = image.source_url; row.error = None
        db.flush()
        if not failure and not db.scalar(select(PhotoItem.id).where(PhotoItem.job_id == job_id, PhotoItem.status == 'pending').limit(1)):
            job.status = 'completed'; job.active_key = None
        db.commit()
        return job_data(db, job)

    return router
