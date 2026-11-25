"""Explicit editorial taxonomy, never an automatic historical verification."""
import hashlib
import json
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload
from ..models import Category, Computer
from ..import_models import ImportJob, ImportRow, ImportClaim
from .engine import reference, source
from .classification_rules import family_category, description_category
from ..admin import catalog_lock
from .normalize import name_key

VERSION = 'hhe-editorial-categories-v2'
TAXONOMY = ('Home computer', 'Personal computer', 'Workstation', 'Minicomputer', 'Mainframe',
            'Microcomputer', 'Portable', 'Supercomputer', 'Server')
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


def classify_details(manufacturer, model, urls=(), description=''):
    family = family_category(manufacturer, model, urls, RULES)
    declared = description_category(manufacturer, model, description)
    # A precise family is more useful than a broad "personal computer" phrase.
    # Specific, incompatible roles need operator review instead of a guess.
    if family and declared and family['category'] != declared['category']:
        broad = {'Personal computer', 'Microcomputer'}
        if declared['category'] in broad:
            return family
        if family['category'] in broad:
            return declared
        return None
    return family or declared


def classify(manufacturer, model, urls=(), description=''):
    decision = classify_details(manufacturer, model, urls, description)
    return (decision['category'], decision['rule']) if decision else None


def generic(name):
    return name_key(name) == 'calcolatore'


def prepare(db, computer_ids=None):
    proposals, unresolved, cleanup = [], [], []
    query = select(Computer).options(selectinload(Computer.manufacturer), selectinload(Computer.categories),
                     selectinload(Computer.sources)).order_by(Computer.id)
    if computer_ids is not None:
        query = query.where(Computer.id.in_(computer_ids))
    rows = db.scalars(query).all()
    for c in rows:
        specific = [cat.name for cat in c.categories if not generic(cat.name)]
        if specific:
            if any(generic(cat.name) for cat in c.categories):
                cleanup.append({'id': c.id, 'manufacturer': c.manufacturer.name, 'model_name': c.model_name,
                    'categories': sorted(specific), 'previous': sorted(cat.name for cat in c.categories)})
            continue  # Preserve every existing specific/manual classification.
        urls = [s.url for s in c.sources]
        decision = classify_details(c.manufacturer.name, c.model_name, urls, c.description or '')
        if decision is None:
            unresolved.append({'id': c.id, 'manufacturer': c.manufacturer.name, 'model_name': c.model_name})
            continue
        proposals.append({'id': c.id, 'manufacturer': c.manufacturer.name, 'model_name': c.model_name,
                          **decision, 'previous': sorted(cat.name for cat in c.categories)})
    raw = json.dumps({'version': VERSION, 'proposals': proposals, 'cleanup': cleanup}, ensure_ascii=False, sort_keys=True).encode()
    return {'token': hashlib.sha256(raw).hexdigest(), 'version': VERSION, 'total': len(proposals), 'unresolved': len(unresolved),
            'catalog_total': len(rows), 'generic_only': len(proposals) + len(unresolved),
            'cleanup_count': len(cleanup), 'cleanup': cleanup, 'unresolved_records': unresolved,
            'current_categories': dict(Counter(cat.name for c in rows for cat in c.categories if not generic(cat.name))),
            'by_category': dict(Counter(p['category'] for p in proposals)), 'proposals': proposals}


def apply_plan(db, preview, limit=1000):
    selected = preview['proposals'][:limit]
    cleanup = preview['cleanup'][:max(0, limit - len(selected))]
    if not selected and not cleanup:
        return {'updated': 0, 'cleaned': 0, 'job_id': None, 'unresolved': preview['unresolved']}
    citation_data = {'title': 'HHE · Classificazione editoriale v2', 'publisher': 'Hardware History Explorer', 'source_type': 'editorial_rule'}
    records = [{'manufacturer': p['manufacturer'], 'model_name': p['model_name'],
        'categories': [p['category']] if 'category' in p else p['categories'], 'source': citation_data,
        'evidence': f"Classificazione editoriale da verificare. Regola {VERSION}: {p.get('rule', 'Rimozione etichetta generica ridondante')}. Categorie precedenti: {p['previous']}."}
        for p in [*selected, *cleanup]]
    raw = json.dumps(records, ensure_ascii=False)
    job = ImportJob(provider='manual', filename=VERSION + '.json', format='json', checksum=hashlib.sha256(raw.encode()).hexdigest(),
        raw_payload=raw, status='completed', request_options={'classification_version': VERSION, 'managed_classification': True})
    db.add(job); db.flush()
    for name in TAXONOMY:
        reference(db, Category, name)
    citation = source(db, citation_data)
    for position, (proposal, record) in enumerate(zip([*selected, *cleanup], records), 1):
        c = db.get(Computer, proposal['id'])
        row = ImportRow(job_id=job.id, position=position, raw=record, normalized=record, computer_id=c.id, status='updated', candidates=[c.id])
        db.add(row); db.flush()
        c.categories = [cat for cat in c.categories if not generic(cat.name)]
        if 'category' in proposal:
            cat = reference(db, Category, proposal['category'])
            if cat not in c.categories:
                c.categories.append(cat)
            if citation not in c.sources:
                c.sources.append(citation)
            db.add(ImportClaim(row_id=row.id, computer_id=c.id, source_id=citation.id, entity='Computer', target_id=c.id,
                field='category', value={'value': cat.id}, previous={'value': None}, status='pending', estimated=False, evidence=record['evidence']))
    db.flush()
    return {'updated': len(selected), 'cleaned': len(cleanup), 'job_id': job.id, 'unresolved': preview['unresolved']}


def normalize_categories(db, computer_ids=None):
    """Backfill generic entries only; preserve every specific operator category."""
    catalog_lock(db)
    total, cleaned, jobs = 0, 0, []
    while True:
        plan = prepare(db, computer_ids)
        result = apply_plan(db, plan)
        total += result['updated']; cleaned += result['cleaned']
        if result['job_id'] is None:
            break
        jobs.append(result['job_id'])
    db.commit()
    return {'updated': total, 'cleaned': cleaned, 'job_ids': jobs, 'unresolved': plan['unresolved']}


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
        result = apply_plan(db, preview)
        db.commit()
        return result

    return router
