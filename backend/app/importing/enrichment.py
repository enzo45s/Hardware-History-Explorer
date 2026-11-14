"""Existing-only enrichment from a versioned, licensed snapshot and Italian summaries."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from ..models import Computer, Configuration, Release
from .engine import stage, apply_job
from .identity import computer_key
from .regional_names import regional_name
from .normalize import Record
from .router import job_data

DATA = Path(__file__).parent / 'data/catalog-enrichment-v1.json'
PAGE = 100


@lru_cache(maxsize=1)
def bundle():
    raw = DATA.read_bytes()
    data = json.loads(raw)
    index = {computer_key(r['manufacturer'],r['model_name']):r for r in data['records']}
    return data, index, hashlib.sha256(raw).hexdigest()


def italian_summary(c):
    categories = [cat.name for cat in c.categories if cat.name != 'Calcolatore']
    noun={'Home computer':'un home computer','Personal computer':'un personal computer','Workstation':'una workstation',
          'Portable':'un computer portatile','Minicomputer':'un minicalcolatore','Mainframe':'un mainframe',
          'Microcomputer':'un microcomputer','Supercomputer':'un supercomputer'}
    category = next((noun[name] for name in categories if name in noun),'un calcolatore')
    first = f'{c.model_name} è {category} di {c.manufacturer.name}.'
    cpus = sorted({s.text_value for cfg in c.configurations for s in cfg.specifications
                   if s.property_name == 'Modello emulato (MAME)' and s.text_value})
    years = sorted({r.release_date.year for r in c.releases if r.release_date and any(s.publisher == 'MAME' for s in r.sources)})
    if len(years) == 1:
        first += f' MAME associa il modello all’anno {years[0]}.'
    if cpus:
        first += ' Le configurazioni emulate documentano ' + ', '.join(cpus[:2]) + (' e altre CPU.' if len(cpus)>2 else '.')
    return first


def owners(db, upper):
    """Attach shared model data to one existing record until optional consolidation."""
    chosen={}
    for c in db.scalars(select(Computer).where(Computer.id<=upper).options(selectinload(Computer.manufacturer))):
        key=computer_key(c.manufacturer.name,c.model_name)
        priority=(regional_name(c.model_name)!=c.model_name,len(c.model_name),c.id)
        if key not in chosen or priority<chosen[key][0]:chosen[key]=(priority,c.id)
    return {key:value[1] for key,value in chosen.items()}


def proposals(db, after=0, upper=None):
    data,index,checksum = bundle()
    upper = upper if upper is not None else (db.scalar(select(func.max(Computer.id))) or 0)
    selected_owners=owners(db,upper)
    rows = db.scalars(select(Computer).where(Computer.id>after,Computer.id<=upper).order_by(Computer.id).limit(PAGE)
        .options(selectinload(Computer.manufacturer),selectinload(Computer.categories),selectinload(Computer.sources),
                 selectinload(Computer.configurations).selectinload(Configuration.specifications),
                 selectinload(Computer.releases).selectinload(Release.sources))).all()
    planned=[]
    for c in rows:
        key=computer_key(c.manufacturer.name,c.model_name)
        original=index.get(key) if selected_owners.get(key)==c.id else None
        record=deepcopy(original) if original else {'source':{'title':'HHE · Sintesi italiana del catalogo','publisher':'Hardware History Explorer','source_type':'editorial_summary'}}
        record.update(manufacturer=c.manufacturer.name,model_name=c.model_name)
        if not record.get('description'):
            record['source']={'title':'HHE · Sintesi italiana del catalogo','publisher':'Hardware History Explorer','source_type':'editorial_summary'}
        # An existing operator-written description is never rewritten.
        if not (c.description or '').strip():
            record['description']=record.get('description') or italian_summary(c)
            record['evidence']=(record.get('evidence','')+' Sintesi italiana HHE dei dati registrati, non nuova verifica storica. Riferimenti: '+
                json.dumps([{'title':s.title,'url':s.url} for s in c.sources[:3]],ensure_ascii=False))[:3000]
        else:
            record.pop('description',None)
        if not record.get('description') and not any(record.get(k) for k in ('configurations','releases','facts')):
            continue
        Record.model_validate(record)
        planned.append({'computer_id':c.id,'record':record})
    token=hashlib.sha256(json.dumps({'checksum':checksum,'ids':[c.id for c in rows],'planned':planned},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    cursor=rows[-1].id if rows else after
    return {'token':token,'after_id':after,'upper_id':upper,'next_id':cursor,'has_more':bool(db.scalar(select(Computer.id).where(Computer.id>cursor,Computer.id<=upper).limit(1))),
            'total':db.scalar(select(func.count()).select_from(Computer).where(Computer.id<=upper)),
            'processed':len(rows),'planned':planned,'version':data['version'],'checksum':checksum}


class Apply(BaseModel):
    token: str = Field(pattern=r'^[a-f0-9]{64}$')
    after_id: int = Field(default=0,ge=0)
    upper_id: int = Field(ge=0)


def create_enrichment_router(get_db):
    router=APIRouter(prefix='/api/admin/enrichment',tags=['Arricchimento archivio esistente'])

    @router.get('/preview')
    def preview(after_id:int=Query(0,ge=0),upper_id:int|None=Query(None,ge=0),db:Session=Depends(get_db)):
        result=proposals(db,after_id,upper_id)
        data,index,_=bundle()
        selected_owners=owners(db,result['upper_id'])
        matched=[index[key] for key in selected_owners if key in index]
        result['coverage']={'models_with_additions':len(matched),'models_with_prices':sum(any(x.get('price') is not None for x in r.get('releases',[])) for r in matched),
                            'missing_descriptions':db.scalar(select(func.count()).select_from(Computer).where(Computer.description.is_(None) | (func.trim(Computer.description)=='')))}
        result['examples']=[{'model_name':p['record']['model_name'],'description':p['record'].get('description'),
             'prices':sum(x.get('price') is not None for x in p['record'].get('releases',[]))} for p in result['planned'][:5]]
        result.pop('planned')
        return result

    @router.post('/apply')
    def apply(data:Apply,db:Session=Depends(get_db)):
        plan=proposals(db,data.after_id,data.upper_id)
        if plan['token']!=data.token:
            raise HTTPException(409,'Le schede sono cambiate: prepara nuovamente l’anteprima di arricchimento.')
        job=None
        if plan['planned']:
            corpus,_,_=bundle()
            keys={computer_key(p['record']['manufacturer'],p['record']['model_name']) for p in plan['planned']}
            metadata={**corpus['metadata'],'originals':[r for r in corpus['metadata']['originals'] if computer_key(r['manufacturer'],r['model_name']) in keys]}
            records=[p['record'] for p in plan['planned']]
            raw=json.dumps({'_metadata':metadata,'records':records},ensure_ascii=False).encode()
            job=stage(db,'manual',f"{plan['version']}-after-{data.after_id}.json",'json',raw,records=records,
                      options={'upload':True,'existing_only':True,'enrichment_checksum':plan['checksum']})
            for row,p in zip(job.rows,plan['planned']):
                row.computer_id=p['computer_id'];row.candidates=[p['computer_id']];row.status='ready'
            db.commit()
            job=apply_job(db,job.id)
        return {'next_id':plan['next_id'],'has_more':plan['has_more'],'processed':plan['processed'],
                'job':job_data(job) if job else None}

    return router
