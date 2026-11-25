"""Pending generated queries upgrade safely; custom queries, covers and leases survive."""
from datetime import timedelta
import pytest
from sqlalchemy import select
from fastapi import HTTPException
from app import main
from app.main import SessionLocal
from app.models import Computer
from app.photo_jobs import PhotoItem, PhotoJob
from test_photo_jobs import clock, single_queue


def test_resume_updates_only_pending_generated_queries_and_keeps_covers_and_mode(client, clock):
    photo=client.post('/api/computers/1/images',json={'image_url':'https://example.org/keep.jpg'}).json()
    job=client.post('/api/admin/photos').json();jid=job['id']
    with SessionLocal() as db:
        rows=db.scalars(select(PhotoItem).where(PhotoItem.job_id==jid).order_by(PhotoItem.position)).all()
        rows[0].query='MITS - Altair 8800'; rows[1].query='Custom - exact query'
        rows[2].query='Commodore - 64';rows[2].status='no_match'
        saved=db.get(PhotoJob,jid);saved.status='paused';saved.next_request_at=clock[0]+timedelta(seconds=60)
        original=[(r.id,r.status) for r in rows];ids=[r.id for r in rows];db.commit()
    resumed=client.post(f'/api/admin/photos/{jid}/resume').json()
    assert resumed['replace_existing'] is False and resumed['total']==job['total']
    assert client.post(f'/api/admin/photos/{jid}/step').status_code==429
    assert client.get('/api/computers/1/images').json()==[photo]
    with SessionLocal() as db:
        assert db.get(PhotoItem,ids[0]).query=='MITS Altair 8800'
        assert db.get(PhotoItem,ids[1]).query=='Custom - exact query'
        assert db.get(PhotoItem,ids[2]).query=='Commodore - 64'
        assert [(r.id,r.status) for r in db.scalars(select(PhotoItem).where(PhotoItem.job_id==jid).order_by(PhotoItem.position))]==original


def test_legacy_queue_step_persists_plain_query_even_on_upstream_failure(client, monkeypatch, clock):
    jid,cid=single_queue(client)
    with SessionLocal() as db:
        row=db.scalar(select(PhotoItem).where(PhotoItem.job_id==jid));row.query='IBM - System/360';db.commit()
    seen=[]
    async def search(query,limit):
        seen.append(query);raise HTTPException(503,'Synthetic busy source',headers={'Retry-After':'30'})
    monkeypatch.setattr(main,'search_pages',search)
    response=client.post(f'/api/admin/photos/{jid}/step').json()
    assert seen==['IBM System/360'] and response['status']=='paused'
    assert response['current']['query']=='IBM System/360' and response['replace_existing'] is False
    assert client.get(f'/api/computers/{cid}/images').json()==[]


def test_resume_does_not_mutate_an_inflight_query_and_step_upgrades_after_lease_expiry(client, monkeypatch, clock):
    jid,cid=single_queue(client)
    with SessionLocal() as db:
        row=db.scalar(select(PhotoItem).where(PhotoItem.job_id==jid));row.query='IBM - System/360'
        job=db.get(PhotoJob,jid);job.status='paused';job.lease_token='existing-worker';job.lease_until=clock[0]+timedelta(seconds=90)
        db.commit()
    response=client.post(f'/api/admin/photos/{jid}/resume').json()
    assert response['current']['query']=='IBM - System/360'
    assert client.post(f'/api/admin/photos/{jid}/step').status_code==429
    clock[0]+=timedelta(seconds=91)
    async def search(query,limit):assert query=='IBM System/360';return {}
    monkeypatch.setattr(main,'search_pages',search)
    result=client.post(f'/api/admin/photos/{jid}/step').json()
    assert result['counts']=={'no_match':1}


def test_simplified_legacy_fallback_and_pre_cleanup_model_names_upgrade(client, clock):
    jid,cid=single_queue(client)
    with SessionLocal() as db:
        row=db.scalar(select(PhotoItem).where(PhotoItem.job_id==jid));row.query='IBM - System 360'
        row.error='Ricerca rifiutata: vecchio fallback.';db.commit()
    assert client.post(f'/api/admin/photos/{jid}/resume').json()['current']['query']=='IBM System/360'
    with SessionLocal() as db:
        computer=db.get(Computer,cid);computer.model_name='System-80 (50 Hz)'
        row=db.scalar(select(PhotoItem).where(PhotoItem.job_id==jid));row.model_name=computer.model_name
        row.query='IBM - System-80 (50 Hz)';db.commit()
    assert client.post(f'/api/admin/photos/{jid}/resume').json()['current']['query']=='IBM System-80'
