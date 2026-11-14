"""Explicit editorial taxonomy, never an automatic historical verification."""
import hashlib
import json
import re
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload
from ..models import Category, Computer
from ..import_models import ImportJob, ImportRow, ImportClaim
from .engine import reference, source
from .identity import maker_key

VERSION = 'hhe-editorial-categories-v1'
TAXONOMY = ('Home computer', 'Personal computer', 'Workstation', 'Minicomputer', 'Mainframe',
            'Microcomputer', 'Portable', 'Supercomputer')
# Specific families only: maker alone, date, CPU and RAM are not classifications.
RULES = (
    ('apple', r'^(?:Macintosh PowerBook|Macintosh Portable)', 'Portable'),
    ('apple', r'^(?:Apple //(?:c|e)\b|Apple \]\[|Apple II(?:gs)?\b)', 'Home computer'),
    ('apple', r'^Apple I$', 'Microcomputer'),
    ('apple', r'^(?:Macintosh|Power Macintosh|iMac|Lisa|Apple ///)', 'Personal computer'),
    ('commodore', r'^(?:Commodore (?:16|64|116|128)|VIC-|Plus/4|Amiga (?:500|600|1200)\b)', 'Home computer'),
    ('commodore', r'^(?:Amiga (?:1000|2000|3000|4000)|PET |CBM |SuperPET|Commodore PC|PC-1\b)', 'Personal computer'),
    ('ibm', r'^(?:ThinkPad|IBM PC (?:5140|5155))\b', 'Portable'),
    ('ibm', r'^IBM System/(?:360|370|390)\b', 'Mainframe'),
    ('ibm', r'^IBM RT PC\b', 'Workstation'),
    ('ibm', r'^(?:IBM PC|IBM XT|IBM PS/2|Multistation 5550)', 'Personal computer'),
    ('dec', r'^(?:PDP-|MicroVAX|VAX-11)', 'Minicomputer'),
    ('dec', r'^DECstation\b', 'Workstation'),
    ('dec', r'^Rainbow\b', 'Personal computer'),
    ('acorn', r'^(?:BBC |Acorn Electron|Atom\b)', 'Home computer'),
    ('acorn', r'^(?:Acorn R(?:140|225|260)|ABC 210/)', 'Workstation'),
    ('acorn', r'^Acorn A4$', 'Portable'),
    ('acorn', r'^(?:Archimedes|Risc PC|StrongARM Risc PC|J233 StrongARM|Acorn A(?:3010|3020|4000|5000))', 'Personal computer'),
    ('sun microsystems', r'^(?:Sun[- ]|SPARCstation|Ultra (?:1|2|5|10|30|60|80)\b)', 'Workstation'),
    ('hewlett-packard', r'^HP9000/3', 'Workstation'),
    ('hewlett-packard', r'^HP 2100$', 'Minicomputer'),
    ('hewlett-packard', r'^(?:HP 95LX|Jornada 720)$', 'Portable'),
    ('atari', r'^(?:Atari )?(?:400|800|1200XL|600XL|800XL|65XE|130XE|520ST|1040ST)\b', 'Home computer'),
    ('amstrad plc', r'^(?:CPC|GX4000)', 'Home computer'),
    ('amstrad plc', r'^(?:PCW|PC1[56]|PC2[08]|PC3[08])', 'Personal computer'),
    ('sharp', r'^(?:MZ-(?:700|800|1500)|X1\b|X68000|X68030)', 'Home computer'),
    ('nec', r'^PC-(?:6001|6601|8001|8801|88VA)', 'Home computer'),
    ('nec', r'^PC-(?:9801|9821|H98)', 'Personal computer'),
)


def classify(manufacturer, model, urls=()):
    maker = maker_key(manufacturer)
    for rule_maker, pattern, category in RULES:
        if maker == rule_maker and re.search(pattern, model, re.I):
            return category, f'{rule_maker}: {pattern}'
    if any('/src/mame/msx/' in (url or '') for url in urls):
        return 'Home computer', 'Famiglia MSX identificata dalla provenienza del driver ufficiale'
    return None


def prepare(db):
    proposals, unresolved = [], 0
    rows = db.scalars(select(Computer).options(selectinload(Computer.manufacturer), selectinload(Computer.categories),
                     selectinload(Computer.sources)).order_by(Computer.id)).all()
    for c in rows:
        if any(cat.name != 'Calcolatore' for cat in c.categories):
            continue  # Preserve every existing specific/manual classification.
        urls = [s.url for s in c.sources]
        match = classify(c.manufacturer.name, c.model_name, urls)
        if match is None:
            unresolved += 1; continue
        category, rule = match
        proposals.append({'id': c.id, 'manufacturer': c.manufacturer.name, 'model_name': c.model_name,
                          'category': category, 'rule': rule, 'previous': sorted(cat.name for cat in c.categories)})
    raw = json.dumps({'version': VERSION, 'proposals': proposals}, ensure_ascii=False, sort_keys=True).encode()
    return {'token': hashlib.sha256(raw).hexdigest(), 'version': VERSION, 'total': len(proposals), 'unresolved': unresolved,
            'by_category': dict(Counter(p['category'] for p in proposals)), 'proposals': proposals}


class Apply(BaseModel):
    token: str = Field(pattern=r'^[a-f0-9]{64}$')


def create_classification_router(get_db):
    router = APIRouter(prefix='/api/admin/classification', tags=['Classificazione editoriale'])

    @router.get('/preview')
    def preview(db: Session = Depends(get_db)):
        return prepare(db)

    @router.post('/apply')
    def apply(data: Apply, db: Session = Depends(get_db)):
        if db.bind.dialect.name == 'sqlite':
            db.execute(text('BEGIN IMMEDIATE'))
        else:
            db.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
            db.execute(select(Computer.id).order_by(Computer.id).with_for_update()).all()
        preview = prepare(db)
        if data.token != preview['token']:
            raise HTTPException(409, 'Le schede sono cambiate: aggiorna l’anteprima delle categorie.')
        if not preview['total']:
            return {'updated': 0, 'job_id': None, 'unresolved': preview['unresolved']}
        # One bounded audit job per click; additional candidates remain for the next preview.
        selected = preview['proposals'][:1000]
        records = [{'manufacturer': p['manufacturer'], 'model_name': p['model_name'], 'categories': [p['category']],
            'source': {'title': 'HHE · Classificazione editoriale v1', 'publisher': 'Hardware History Explorer', 'source_type': 'editorial_rule'},
            'evidence': f"Classificazione editoriale da verificare, non attestazione MAME. Regola {VERSION}: {p['rule']}. Categorie precedenti: {p['previous']}."}
            for p in selected]
        raw = json.dumps(records, ensure_ascii=False)
        job = ImportJob(provider='manual', filename=VERSION + '.json', format='json', checksum=hashlib.sha256(raw.encode()).hexdigest(),
                        raw_payload=raw, status='completed', request_options={'upload': True, 'classification_version': VERSION})
        db.add(job); db.flush()
        for name in TAXONOMY:
            reference(db, Category, name)
        citation = source(db, records[0]['source'])
        for position, (proposal, record) in enumerate(zip(selected, records), 1):
            c = db.get(Computer, proposal['id']); cat = reference(db, Category, proposal['category'])
            row = ImportRow(job_id=job.id, position=position, raw=record, normalized=record, computer_id=c.id, status='updated', candidates=[c.id])
            db.add(row); db.flush()
            c.categories.append(cat)
            if citation not in c.sources: c.sources.append(citation)
            db.add(ImportClaim(row_id=row.id, computer_id=c.id, source_id=citation.id, entity='Computer', target_id=c.id,
                field='category', value={'value': cat.id}, previous={'value': None}, status='pending', estimated=False, evidence=record['evidence']))
        db.commit()
        return {'updated': len(selected), 'job_id': job.id, 'unresolved': preview['unresolved']}

    return router
