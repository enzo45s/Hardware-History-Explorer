"""Transactional consolidation of existing regional records, retaining all children."""
import hashlib
import json
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text, func
from sqlalchemy.orm import Session
from ..models import Computer
from ..import_models import CatalogReconciliation
from ..photo_jobs import PhotoItem
from .identity import computer_key
from .regional_names import regional_name
from . import reconcile


def preview(db):
    groups = defaultdict(list)
    for c in db.scalars(select(Computer).order_by(Computer.id)):
        groups[computer_key(c.manufacturer.name, c.model_name)].append(c)
    plans, originals = [], []
    for items in groups.values():
        if len(items) < 2 or not any(regional_name(c.model_name) != c.model_name for c in items):
            continue
        target = min(items, key=lambda c: (regional_name(c.model_name) != c.model_name, len(c.model_name), c.id))
        sources = sorted((c for c in items if c.id != target.id), key=lambda c:c.id)
        for c in sources:
            originals.append(reconcile.prepare(db, 'computer', c.id, target.id)[2])
        plans.append({'target_id': target.id, 'model_name': regional_name(target.model_name),
                      'manufacturer': target.manufacturer.name,
                      'sources': [{'id': c.id, 'name': c.model_name} for c in sources]})
    token = hashlib.sha256(json.dumps({'plans':plans,'originals':originals},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'token': token, 'groups': plans, 'removed': sum(len(g['sources']) for g in plans), 'remaining':
            db.scalar(select(func.count()).select_from(Computer)) - sum(len(g['sources']) for g in plans)}


class Apply(BaseModel):
    token: str = Field(pattern=r'^[a-f0-9]{64}$')


def create_regional_router(get_db):
    router = APIRouter(prefix='/api/admin/regional', tags=['Varianti regionali'])

    @router.get('/preview')
    def get_preview(db: Session = Depends(get_db)):
        return preview(db)

    @router.post('/apply')
    def apply(data: Apply, db: Session = Depends(get_db)):
        if db.bind.dialect.name == 'sqlite': db.execute(text('BEGIN IMMEDIATE'))
        else:
            db.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
            # Freeze every table represented in the audit token, including sources and images.
            db.execute(text('LOCK TABLE ' + ', '.join(db.bind.dialect.identifier_preparer.quote(t.name)
                for t in sorted(Computer.metadata.tables.values(),key=lambda t:t.name)) + ' IN EXCLUSIVE MODE'))
        plan = preview(db)
        if plan['token'] != data.token:
            raise HTTPException(409, 'L’archivio è cambiato: aggiorna l’anteprima delle varianti regionali.')
        audits = []
        for group in plan['groups']:
            for source in group['sources']:
                p = reconcile.prepare(db,'computer',source['id'],group['target_id'])[3]
                result = reconcile.apply(db,'computer',source['id'],group['target_id'],p['token'],
                    'Accorpamento esplicito delle varianti geografiche; revisioni e configurazioni conservate.',commit=False)
                audits.append(result['reconciliation_id'])
            target = db.get(Computer,group['target_id'])
            if target.model_name != group['model_name']:
                audit = db.get(CatalogReconciliation,audits[-1])
                audit.snapshot = {**audit.snapshot,'regional_target_rename':{'before':target.model_name,'after':group['model_name']}}
                target.model_name = group['model_name']
                for row in db.scalars(select(PhotoItem).where(PhotoItem.computer_id == target.id,PhotoItem.status == 'pending')):
                    row.model_name = target.model_name; row.query = target.model_name.strip()[:90]
        db.commit()
        return {'removed': plan['removed'], 'remaining': plan['remaining'], 'reconciliation_ids': audits}

    return router
