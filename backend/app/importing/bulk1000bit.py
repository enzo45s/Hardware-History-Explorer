"""Durable linked-page traversal and conservative enrichment of a catalog snapshot.

One network request per step, with a database lease and a persisted deadline.
The browser drives steps; originals, frontier and progress survive restarts.
"""
import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..admin import Input, catalog_lock
from ..models import Base, Computer
from ..import_models import ImportJob, ImportRow, ImportClaim
from .bit1000 import decode_html, html_record, sheet_url
from .collect_1000bit import (AGENT, USER_AGENT, MAX_PAGE_BYTES, MAX_ROBOTS_BYTES,
                            origin, page_url, robots_rules, robots_interval, snapshot)
from .engine import stage, apply_job, catalog_candidates
from .identity import provider_computer_key
from .normalize import Record

INDEX = 'https://www.1000bit.it/database.asp?by=S_NOM'  # Link in the supplied real sheet.
SEED = 'https://www.1000bit.it/scheda.asp?id=282'
MAX_QUEUE = 50000
INDEX_PATHS = {'/database.asp', '/database2.asp', '/database4.asp'}
UNSAFE_QUERY = {'coll', 'user', 'username', 'login', 'logout', 'delete', 'del', 'action', 'cmd', 'token', 'password', 'session'}


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class BulkJob(Base):
    __tablename__ = 'bit1000_bulk_jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    active_key: Mapped[str | None] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(30), default='ready')
    error: Mapped[str | None] = mapped_column(Text)
    interval_seconds: Mapped[float] = mapped_column(default=5.0)
    max_requests: Mapped[int] = mapped_column(default=20000)
    requests: Mapped[int] = mapped_column(default=0)
    robots: Mapped[dict] = mapped_column(JSON, default=dict)
    next_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BulkTarget(Base):
    __tablename__ = 'bit1000_bulk_targets'
    __table_args__ = (UniqueConstraint('job_id', 'original_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('bit1000_bulk_jobs.id', ondelete='CASCADE'), index=True)
    original_id: Mapped[int]
    computer_id: Mapped[int | None] = mapped_column(ForeignKey('computers.id', ondelete='SET NULL'), index=True)
    model_name: Mapped[str] = mapped_column(String(180))
    manufacturer: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default='pending')


class BulkPage(Base):
    __tablename__ = 'bit1000_bulk_pages'
    __table_args__ = (UniqueConstraint('job_id', 'url'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('bit1000_bulk_jobs.id', ondelete='CASCADE'), index=True)
    url: Mapped[str] = mapped_column(String(800))
    status: Mapped[str] = mapped_column(String(30), default='pending', index=True)
    error: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(180))
    manufacturer: Mapped[str | None] = mapped_column(String(160))
    checksum: Mapped[str | None] = mapped_column(String(64))
    # Successful matched/review originals are retained by ImportJob instead.
    import_job_id: Mapped[int | None] = mapped_column(ForeignKey('import_jobs.id'), index=True)


def crawl_url(value, base=INDEX):
    """Only observed database/sheet links, never forms, media or ID enumeration."""
    if not isinstance(value, str) or not value.strip() or value.startswith('#'):
        raise ValueError('Collegamento non utilizzabile.')
    value = urljoin(base, value.strip())
    if value.startswith('http://'):
        value = 'https://' + value[7:]
    parsed = urlsplit(page_url(value.split('#', 1)[0]))
    path = parsed.path.casefold()
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key.casefold() in UNSAFE_QUERY for key, _ in query):
        raise ValueError('Collegamento a dati personali o azioni escluso.')
    if path == '/scheda.asp':
        canonical = urlsplit(sheet_url(value.split('#', 1)[0]))
        return urlunsplit(('https', parsed.netloc, canonical.path, canonical.query, ''))
    if path not in INDEX_PATHS:
        raise ValueError('Sono ammessi solo indici e schede del database 1000bit.')
    # Sorting changes do not identify additional records. Keep one stable order.
    query = [(key, val) for key, val in query if key.casefold() not in ('by', 'sort', 'order')]
    if path == '/database.asp':
        query.append(('by', 'S_NOM'))
    return page_url(urlunsplit(('https', parsed.netloc, path, urlencode(sorted(query)), '')))


class Links(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.links, self.skip = base, set(), 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'form'):
            self.skip += 1
        if self.skip or tag != 'a':
            return
        try:
            self.links.add(crawl_url(dict(attrs).get('href'), self.base))
        except ValueError:
            pass

    def handle_endtag(self, tag):
        if self.skip and tag in ('script', 'style', 'noscript', 'form'):
            self.skip -= 1


def links_from(raw, url, content_type):
    parser = Links(url)
    parser.feed(decode_html(raw, content_type))
    return sorted(parser.links)


def fetch(url, limit):
    """A single bounded request. Redirects are persisted as later queue work."""
    with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False,
                      headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain;q=0.9'}) as client:
        with client.stream('GET', url) as response:
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > limit:
                    raise ValueError('Risposta troppo grande: raccolta in pausa.')
            return response.status_code, bytes(body), response.headers.get('content-type', ''), {
                'location': response.headers.get('location', ''), 'retry-after': response.headers.get('retry-after', '')}


def retry_delay(value):
    try:
        seconds = int(value) if value.isascii() and value.isdigit() else (parsedate_to_datetime(value) - now()).total_seconds()
    except (ValueError, TypeError, AttributeError):
        seconds = 60
    return max(5, min(86400, seconds))


def queue(db, job, urls):
    existing = set(db.scalars(select(BulkPage.url).where(BulkPage.job_id == job.id)))
    additions = sorted(set(urls) - existing)
    if len(existing) + len(additions) > MAX_QUEUE:
        raise ValueError('Limite della coda raggiunto (50.000 collegamenti). Nessun completamento dichiarato.')
    db.add_all(BulkPage(job_id=job.id, url=url) for url in additions)


def target_status(target, status):
    # A second source with identical values must not erase a prior update.
    if target and not (target.status == 'updated' and status == 'unchanged'):
        target.status = status


def refresh_reviews(db, job):
    pages = db.scalars(select(BulkPage).where(BulkPage.job_id == job.id, BulkPage.status == 'review'))
    for page in pages:
        imported = db.get(ImportJob, page.import_job_id)
        seen = set()
        while imported.id not in seen:
            seen.add(imported.id)
            retry = db.scalar(select(ImportJob).where(ImportJob.retry_of == imported.id).order_by(ImportJob.id.desc()).limit(1))
            if retry is None:
                break
            imported = retry
        page.import_job_id = imported.id
        if imported.status not in ('completed', 'partial'):
            continue
        row = db.scalar(select(ImportRow).where(ImportRow.job_id == imported.id))
        if row.status in ('updated', 'unchanged'):
            page.status = row.status
            target = db.scalar(select(BulkTarget).where(BulkTarget.job_id == job.id, BulkTarget.computer_id == row.computer_id))
            target_status(target, row.status)
        elif row.status == 'skipped':
            page.status = 'skipped'


def finish(db, job):
    if not db.scalar(select(BulkPage.id).where(BulkPage.job_id == job.id, BulkPage.status == 'pending').limit(1)):
        job.status, job.active_key = 'completed', None
        db.execute(update(BulkTarget).where(BulkTarget.job_id == job.id, BulkTarget.computer_id.is_(None))
                   .values(status='removed').execution_options(synchronize_session=False))
        db.execute(update(BulkTarget).where(BulkTarget.job_id == job.id, BulkTarget.status == 'pending')
                   .values(status='not_found').execution_options(synchronize_session=False))


def details(db, job):
    counts = dict(db.execute(select(BulkTarget.status, func.count()).where(BulkTarget.job_id == job.id).group_by(BulkTarget.status)).all())
    pages = dict(db.execute(select(BulkPage.status, func.count()).where(BulkPage.job_id == job.id).group_by(BulkPage.status)).all())
    recent = db.scalars(select(BulkPage).where(BulkPage.job_id == job.id, BulkPage.status != 'pending')
                        .order_by(BulkPage.id.desc()).limit(10)).all()
    reviews = db.scalars(select(BulkPage).where(BulkPage.job_id == job.id, BulkPage.status == 'review').limit(25)).all()
    conflicts = db.scalar(select(func.count()).select_from(ImportClaim).join(ImportRow, ImportClaim.row_id == ImportRow.id)
        .join(BulkPage, BulkPage.import_job_id == ImportRow.job_id).where(BulkPage.job_id == job.id, ImportClaim.status == 'conflict'))
    return {'id': job.id, 'status': job.status, 'error': job.error, 'counts': counts, 'total': sum(counts.values()),
            'pages': pages, 'queued': sum(pages.values()), 'requests': job.requests, 'max_requests': job.max_requests,
            'interval_seconds': job.interval_seconds, 'conflicts': conflicts,
            'next_request_at': utc(job.next_request_at).isoformat() if job.next_request_at else None,
            'lease_until': utc(job.lease_until).isoformat() if job.lease_token and job.lease_until else None,
            'recent': [{'url': p.url, 'model_name': p.model_name, 'manufacturer': p.manufacturer, 'status': p.status, 'error': p.error,
                        'import_job_id': p.import_job_id} for p in recent],
            'reviews': [{'url': p.url, 'model_name': p.model_name, 'import_job_id': p.import_job_id} for p in reviews],
            'not_found': [{'id': t.original_id, 'computer_id': t.computer_id, 'model_name': t.model_name, 'manufacturer': t.manufacturer, 'status': t.status}
                          for t in db.scalars(select(BulkTarget).where(BulkTarget.job_id == job.id,
                              BulkTarget.status.in_(['not_found', 'ambiguous', 'stale', 'removed'])).limit(25))]}


def import_page(db, job, page, raw, content_type):
    record = Record.model_validate(html_record(raw, page.url, content_type)).model_dump(mode='json', exclude_none=True)
    page.model_name, page.manufacturer = record['model_name'], record['manufacturer']
    candidates, ambiguous = catalog_candidates(db, record, '1000bit')
    targets = list(db.scalars(select(BulkTarget).where(BulkTarget.job_id == job.id, BulkTarget.computer_id.in_(candidates))))
    valid = []
    for target in targets:
        computer = db.get(Computer, target.computer_id)
        if provider_computer_key('1000bit', computer.manufacturer.name, computer.model_name) != provider_computer_key('1000bit', target.manufacturer, target.model_name):
            target_status(target, 'stale')
        else:
            valid.append(target)
    # Prefer the original variant's snapshot row, even though several rows now
    # share the same surviving catalog owner.
    from .catalog_aliases import alias_for
    alias = alias_for(db, record['manufacturer'], record['model_name'])
    original_ids = {member.get('computer_id') for member in alias.original.get('members', [alias.original])} if alias else set()
    scoped_targets = [target for target in valid if target.original_id in original_ids]
    if scoped_targets:
        valid = scoped_targets
    # Consolidated configurations share a catalog owner, not an ambiguous match.
    valid = list({target.computer_id: target for target in valid}.values())
    imported = stage(db, '1000bit', f'1000bit-bulk-{job.id}-{page.id}.html', 'html', raw, records=[record],
                     options={'upload': True, 'existing_only': True, 'bulk_job_id': job.id, 'source_url': page.url}, commit=False)
    page.import_job_id = imported.id
    row = db.scalar(select(ImportRow).where(ImportRow.job_id == imported.id))
    if not valid:
        page.status = 'unmatched'
        page.error = f'Nessuna corrispondenza nel catalogo iniziale per {record["manufacturer"]} · {record["model_name"]}.'
        row.status, row.error, imported.status = 'skipped', page.error, 'completed'
        return
    if row.status == 'invalid':
        page.status = 'review'
        for target in valid:
            if target.status == 'pending':
                target.status = 'ambiguous'
        return
    if ambiguous or len(valid) > 1:
        row.status, row.computer_id, row.candidates = 'ambiguous', None, candidates
        page.status = 'review'
        for target in valid:
            if target.status in ('pending', 'not_found'):
                target.status = 'ambiguous'
        return
    row.computer_id, row.status, row.candidates = valid[0].computer_id, 'ready', [valid[0].computer_id]
    db.flush()
    apply_job(db, imported.id, commit=False)
    page.status = row.status if row.status in ('updated', 'unchanged') else 'review'
    target_status(valid[0], row.status if row.status in ('updated', 'unchanged') else 'ambiguous')
    for target in scoped_targets[1:]:
        target_status(target, row.status if row.status in ('updated', 'unchanged') else 'ambiguous')


def step(db, job_id, fetcher=None):
    fetcher = fetcher or fetch
    job = db.get(BulkJob, job_id)
    if job.status != 'ready':
        return details(db, job)
    refresh_reviews(db, job)
    if job.requests >= job.max_requests:
        job.status = 'limited'; db.commit()
        return details(db, job)
    token, timestamp = str(uuid.uuid4()), now()
    acquired = db.execute(update(BulkJob).where(BulkJob.id == job_id, BulkJob.status == 'ready',
        (BulkJob.lease_until.is_(None) | (BulkJob.lease_until <= timestamp)),
        (BulkJob.next_request_at.is_(None) | (BulkJob.next_request_at <= timestamp)))
        .values(lease_token=token, lease_until=timestamp + timedelta(seconds=180)).execution_options(synchronize_session=False)).rowcount
    db.commit()
    if not acquired:
        db.expire_all(); return details(db, db.get(BulkJob, job_id))
    db.expire_all(); job = db.get(BulkJob, job_id)
    page = db.scalar(select(BulkPage).where(BulkPage.job_id == job_id, BulkPage.status == 'pending').order_by(BulkPage.id).limit(1))
    if page is None:
        finish(db, job); job.lease_token = None; job.lease_until = None; db.commit()
        return details(db, job)
    page_id, url = page.id, page.url
    host, robots = origin(url), dict(job.robots)
    cached = robots.get(host)
    purpose = 'robots' if not cached or 'redirect' in cached else 'page'
    request_url = (cached or {}).get('redirect', host + '/robots.txt') if purpose == 'robots' else url
    blocked = False
    if purpose == 'page':
        rules = robots_rules(base64.b64decode(cached['body_base64']), cached['content_type'], cached['http_status'])
        blocked = not rules.can_fetch(AGENT, url)
    db.rollback()  # No database locks/transaction across the network.
    response, failure = None, None
    if not blocked:
        try:
            response = fetcher(request_url, MAX_ROBOTS_BYTES if purpose == 'robots' else MAX_PAGE_BYTES)
        except (httpx.HTTPError, ValueError) as exc:
            failure = str(exc) if isinstance(exc, ValueError) else 'Rete/proxy non disponibile; nessuna scheda saltata automaticamente.'
    # Same lock order as the catalog reset and regular import application.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
    else:
        db.execute(text('BEGIN IMMEDIATE'))
    job = db.scalar(select(BulkJob).where(BulkJob.id == job_id).with_for_update().execution_options(populate_existing=True))
    if job.lease_token != token or job.status not in ('ready', 'paused'):
        db.rollback(); return details(db, db.get(BulkJob, job_id))
    page = db.get(BulkPage, page_id)
    job.lease_token = None; job.lease_until = None
    if blocked:
        page.status, page.error = 'blocked', 'Percorso escluso da robots.txt.'
    else:
        job.requests += 1
        job.next_request_at = now() + timedelta(seconds=job.interval_seconds)
        if failure:
            job.status, job.error, page.error = 'paused', failure, failure
            job.next_request_at = now() + timedelta(seconds=max(60, job.interval_seconds))
        else:
            status, raw, content_type, headers = response
            try:
                if status in (301, 302, 303, 307, 308):
                    location = headers.get('location')
                    if not location:
                        raise ValueError('Redirect senza destinazione.')
                    if purpose == 'robots':
                        hops = (cached or {}).get('hops', 0) + 1
                        if hops > 4:
                            raise ValueError('Troppi redirect di robots.txt.')
                        robots[host] = {'redirect': page_url(urljoin(request_url, location)), 'hops': hops}
                        job.robots = robots
                    else:
                        destination = crawl_url(location, url)
                        if destination == url:
                            raise ValueError('Redirect circolare della pagina.')
                        queue(db, job, [destination]); page.status = 'redirect'
                elif purpose == 'robots' and status in (200, 404):
                    rules = robots_rules(raw, content_type, status)
                    job.interval_seconds = robots_interval(rules, job.interval_seconds)
                    robots[host] = {**snapshot(request_url, raw, content_type), 'http_status': status}
                    job.robots = robots
                    job.next_request_at = now() + timedelta(seconds=job.interval_seconds)
                elif status != 200:
                    raise ValueError(f'HTTP {status} da 1000bit: raccolta in pausa, riprova più tardi.')
                else:
                    if content_type.split(';', 1)[0].strip().casefold() not in ('text/html', 'application/xhtml+xml'):
                        raise ValueError('Pagina non HTML: raccolta in pausa.')
                    discovered = links_from(raw, url, content_type)
                    # Use a savepoint: parse/import failures cannot leave catalog or frontier half-written.
                    with db.begin_nested():
                        queue(db, job, discovered)
                        page.checksum = hashlib.sha256(raw).hexdigest()
                        if urlsplit(url).path.casefold() == '/scheda.asp':
                            import_page(db, job, page, raw, content_type)
                        else:
                            page.status = 'indexed'
                        if page.status != 'unmatched':
                            page.error = None
            except (ValueError, TypeError, KeyError) as exc:
                job.status = 'paused'; job.error = page.error = str(exc)[:2000]
                delay = retry_delay(headers.get('retry-after', '')) if status in (429, 503) else 60
                job.next_request_at = now() + timedelta(seconds=max(delay, job.interval_seconds))
    db.flush()
    if job.status == 'ready':
        finish(db, job)
    db.commit()
    return details(db, job)


class Start(Input):
    interval_seconds: float = Field(default=5, ge=5, le=3600)
    max_requests: int = Field(default=20000, ge=1, le=50000)


class Resume(Input):
    max_requests: int | None = Field(default=None, ge=1, le=50000)


def create_bulk_router(get_db):
    router = APIRouter(prefix='/api/admin/1000bit/bulk', tags=['Arricchimento automatico 1000bit'])

    def get(db, job_id):
        job = db.get(BulkJob, job_id)
        if job is None:
            raise HTTPException(404, 'Raccolta 1000bit non trovata.')
        return job

    @router.get('')
    def status(db: Session = Depends(get_db)):
        job = db.scalar(select(BulkJob).order_by(BulkJob.id.desc()).limit(1))
        return {'catalog_total': db.scalar(select(func.count()).select_from(Computer)), 'job': details(db, job) if job else None}

    @router.post('', status_code=201)
    def start(data: Start, db: Session = Depends(get_db)):
        active = db.scalar(select(BulkJob).where(BulkJob.active_key == '1000bit'))
        if active:
            return details(db, active)
        job = BulkJob(active_key='1000bit', interval_seconds=data.interval_seconds, max_requests=data.max_requests)
        try:
            db.add(job); db.flush()
        except IntegrityError:
            db.rollback()
            return details(db, db.scalar(select(BulkJob).where(BulkJob.active_key == '1000bit')))
        targets = list(db.scalars(select(Computer).order_by(Computer.id)))
        db.add_all(BulkTarget(job_id=job.id, original_id=c.id, computer_id=c.id, model_name=c.model_name,
                              manufacturer=c.manufacturer.name) for c in targets)
        if targets:
            queue(db, job, [INDEX, SEED])
        else:
            job.status, job.active_key = 'completed', None
        db.commit()
        return details(db, job)

    @router.post('/{job_id}/step')
    def advance(job_id: int, db: Session = Depends(get_db)):
        get(db, job_id)
        return step(db, job_id)

    @router.post('/{job_id}/pause')
    def pause(job_id: int, db: Session = Depends(get_db)):
        job = get(db, job_id)
        if job.status == 'ready':
            job.status = 'paused'
        db.commit(); return details(db, job)

    @router.post('/{job_id}/resume')
    def resume(job_id: int, data: Resume, db: Session = Depends(get_db)):
        job = get(db, job_id)
        if job.status in ('paused', 'limited', 'ready'):
            if data.max_requests is not None:
                job.max_requests = max(job.requests, data.max_requests)
            if job.requests >= job.max_requests:
                raise HTTPException(409, 'Aumenta il limite richieste prima di riprendere.')
            job.status, job.error = 'ready', None
        db.commit(); return details(db, job)

    @router.post('/{job_id}/refresh')
    def refresh(job_id: int, db: Session = Depends(get_db)):
        job = get(db, job_id); refresh_reviews(db, job); db.commit()
        return details(db, job)

    @router.post('/{job_id}/retry-unmatched')
    def retry_unmatched(job_id: int, data: Resume, db: Session = Depends(get_db)):
        catalog_lock(db)
        job = db.scalar(select(BulkJob).where(BulkJob.id == job_id).with_for_update())
        if job is None:
            raise HTTPException(404, 'Raccolta 1000bit non trovata.')
        if job.status not in ('ready', 'paused', 'limited', 'completed'):
            raise HTTPException(409, 'Questa sessione non può essere ripresa.')
        if job.lease_token and job.lease_until and utc(job.lease_until) > now():
            raise HTTPException(409, 'Attendi la conclusione della richiesta corrente prima di ritentare gli abbinamenti.')
        active = db.scalar(select(BulkJob.id).where(BulkJob.active_key == '1000bit', BulkJob.id != job_id))
        if active is not None:
            raise HTTPException(409, 'Un’altra sessione è attiva: continua quella corrente.')
        if data.max_requests is not None:
            job.max_requests = max(job.requests, data.max_requests)
        if job.requests >= job.max_requests:
            raise HTTPException(409, 'Aumenta il limite richieste prima di ritentare le pagine non abbinate.')
        pages = db.scalars(select(BulkPage).where(BulkPage.job_id == job_id, BulkPage.status == 'unmatched')).all()
        if not pages:
            raise HTTPException(409, 'Nessuna pagina non abbinata da ritentare.')
        for page in pages:
            page.status, page.error = 'pending', None
        # Preserve successes, human reviews, the snapshot and remote cooldown.
        db.execute(update(BulkTarget).where(BulkTarget.job_id == job_id, BulkTarget.status == 'not_found', BulkTarget.computer_id.is_not(None))
                   .values(status='pending').execution_options(synchronize_session=False))
        job.status, job.active_key, job.error = 'paused', '1000bit', None
        job.lease_token = None; job.lease_until = None
        db.commit()
        return details(db, job)

    @router.get('/{job_id}/report')
    def report(job_id: int, db: Session = Depends(get_db)):
        job = get(db, job_id)
        data = {'job': details(db, job), 'targets': [
            {'original_id': t.original_id, 'computer_id': t.computer_id, 'model_name': t.model_name,
             'manufacturer': t.manufacturer, 'status': t.status}
            for t in db.scalars(select(BulkTarget).where(BulkTarget.job_id == job_id).order_by(BulkTarget.original_id))],
            'pages': [{'url': p.url, 'model_name': p.model_name, 'manufacturer': p.manufacturer,
                       'status': p.status, 'error': p.error, 'checksum': p.checksum, 'import_job_id': p.import_job_id}
                      for p in db.scalars(select(BulkPage).where(BulkPage.job_id == job_id).order_by(BulkPage.id))]}
        return JSONResponse(data, headers={'Content-Disposition': f'attachment; filename="1000bit-session-{job_id}.json"',
                                           'X-Content-Type-Options': 'nosniff'})

    @router.post('/{job_id}/skip')
    def skip(job_id: int, db: Session = Depends(get_db)):
        job = get(db, job_id)
        if job.status != 'paused' or (job.lease_token and utc(job.lease_until) > now()):
            raise HTTPException(409, 'Metti in pausa e attendi la richiesta corrente prima di saltarla.')
        page = db.scalar(select(BulkPage).where(BulkPage.job_id == job_id, BulkPage.status == 'pending').order_by(BulkPage.id).limit(1))
        if page:
            page.status, page.error = 'skipped', 'Pagina saltata esplicitamente dall’operatore.'
        job.error = None; db.commit(); return details(db, job)

    @router.post('/{job_id}/cancel')
    def cancel(job_id: int, db: Session = Depends(get_db)):
        job = get(db, job_id)
        if job.status not in ('completed', 'archived', 'cancelled'):
            job.status, job.active_key, job.lease_token, job.lease_until = 'cancelled', None, None, None
        db.commit(); return details(db, job)

    return router
