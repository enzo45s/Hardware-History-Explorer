"""Offline Sun chronology and selected photographs; existing computers only.

Workbook notes supply a reported reference year, never an automatically verified
launch. Precisely identified obsolete base dates may be replaced, curated dates
and price amounts are preserved. Explicit invocation, no startup/network work.
"""
import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from sqlalchemy import select
from ..admin import catalog_lock, historical_date
from ..models import Computer, Manufacturer, Release, Market, ComputerImage, release_source
from ..import_models import CatalogReconciliation, ImportClaim
from ..source_policy import is_internal_source, is_mame_source
from .normalize import Citation, Record
from .engine import stage, source, reference, serialize
from .ibm_ps_dates import date_text, verified

PACKAGE = Path(__file__).parent / 'data/sun-dates-photos-v1.json'
ENTITY = 'sun_research'
AUTO_PHOTO = 'Scelta automatica Commons ·'


def load(path=PACKAGE):
    raw = Path(path).read_bytes(); data = json.loads(raw)
    models = set(data['models'])
    if len(models) != 24 or len(models) != len(data['models']): raise ValueError('Ambito Sun inatteso o duplicato.')
    if not set(data['photos']) <= models or not set(data['context_date_corrections']) <= models:
        raise ValueError('Foto o rettifiche fuori dall’ambito Sun.')
    seen = set()
    for item in data['dates']:
        if item['model_name'] not in models or item['model_name'] in seen: raise ValueError('Cronologia Sun duplicata o inattesa.')
        seen.add(item['model_name']); historical_date(item['release_date']); Citation.model_validate(item['source'])
        if item['kind'] not in ('reference','documented_launch') or not item.get('evidence') or not item.get('note'):
            raise ValueError('Cronologia senza tipo o evidenza.')
    from ..main import ImageLinkInput
    for proposals in data['photos'].values():
        for photo in proposals:
            if not photo.get('permission_basis'): raise ValueError('Foto senza condizioni documentate.')
            ImageLinkInput.model_validate({k: v for k,v in photo.items() if k != 'permission_basis'})
    return data, hashlib.sha256(raw).hexdigest()


def context_year(computer):
    candidates = []
    for fact in computer.facts:
        if fact.fact_type != 'Contesto del prezzo': continue
        years = set(re.findall(r'(?:^|;)\s*Anno lancio:\s*([12]\d{3})(?=\s*(?:;|$))', fact.statement))
        citations = [s for s in fact.sources if s.url and not is_internal_source(s)]
        if len(years) != 1 or not citations: continue
        year = next(iter(years))
        if int(year) > date.today().year: continue
        for s in citations:
            citation = Citation(title=s.title, url=s.url, author=s.author, publisher=s.publisher,
                                source_type=s.source_type).model_dump(mode='json', exclude_none=True)
            candidates.append({'year': year, 'source': citation, 'fact_id': fact.id, 'statement': fact.statement})
    if len({c['year'] for c in candidates}) != 1: return None
    chosen = candidates[0]
    return {'release_date': chosen['year'], 'kind': 'reference', 'source': chosen['source'],
            'evidence': 'Anno trascritto dal campo «Anno lancio» della nota di prezzo importata, non da un importo o da una data nel testo libero.',
            'note': 'Anno riportato nel contesto del prezzo importato; è un riferimento della ricerca, non una conferma indipendente del primo lancio.',
            'contexts': candidates}


def protected_date(db, release):
    return bool((release.catalog_details or {}).get('date_manual') or verified(db,'Release',release.id,'release_date') or
        db.scalar(select(release_source.c.source_id).where(release_source.c.target_id == release.id,
                  release_source.c.verification_status == 'verified').limit(1)))


def exact_base_date(db, computer, release):
    if release.release_date is None: return False
    expected = {'value': release.release_date.isoformat(), 'precision': release.release_precision}
    return any(c.value == expected and c.status == 'pending' and is_mame_source(c.source)
        for c in db.scalars(select(ImportClaim).where(ImportClaim.computer_id == computer.id,
            ImportClaim.entity == 'Release', ImportClaim.target_id == release.id, ImportClaim.field == 'release_date')))


def plan(db, path=PACKAGE):
    data, checksum = load(path)
    maker_names = {n.casefold() for n in data['manufacturer_names']}
    makers = [m.id for m in db.scalars(select(Manufacturer)) if m.name.casefold() in maker_names]
    if len(makers) > 1: raise ValueError('Produttore Sun ambiguo; nessuna modifica applicata.')
    computers = list(db.scalars(select(Computer).where(Computer.manufacturer_id.in_(makers))))
    dates = {d['model_name']: d for d in data['dates']}; selected = []; skipped = []; preserved = []
    for name in data['models']:
        matches = [c for c in computers if c.model_name.casefold() == name.casefold()]
        if len(matches) != 1:
            skipped.append({'model_name': name, 'reason': 'Scheda assente o ambigua; nessun sistema creato.'}); continue
        c = matches[0]; desired = dates.get(name) or context_year(c); actions = []
        if not desired and not any(r.release_date for r in c.releases):
            preserved.append({'model_name': name, 'reason': 'Anno assente nelle note o non univoco: nessuna data inventata.'})
        if desired:
            for target in list(c.releases) or [None]:
                old = date_text(target,'release_date') if target else None
                if target and protected_date(db,target):
                    preserved.append({'model_name': name, 'release_id': target.id, 'reason': 'Data curata o verificata.'}); continue
                if old == desired['release_date']: continue
                # Context-only corrections are deliberately restricted. A later
                # price list for Sun 2/120 must never replace its existing year.
                allowed = name in dates or name in data['context_date_corrections']
                if old and not (allowed and exact_base_date(db,c,target)):
                    preserved.append({'model_name': name, 'release_id': target.id, 'reason': 'Data esistente non riconducibile esattamente al dato di base.'}); continue
                if target and target.discontinuation_date and historical_date(desired['release_date'])[0] > target.discontinuation_date:
                    preserved.append({'model_name': name, 'release_id': target.id, 'reason': 'Anno successivo alla fine commercializzazione.'}); continue
                actions.append({'target': target, 'desired': desired})
        retire = [i for i in c.images if i.source_url in data['wrong_automatic_photos'].get(name,[]) and (i.caption or '').startswith(AUTO_PHOTO)]
        photos = [p for p in data['photos'].get(name,[]) if not any(i.remote_url == p['image_url'] for i in c.images)]
        if actions or retire or photos: selected.append({'computer': c, 'date_actions': actions, 'retire': retire, 'photos': photos})
    return data, checksum, selected, skipped, preserved


def preview(db, path=PACKAGE):
    data, checksum, selected, skipped, preserved = plan(db,path)
    return {'version': data['version'], 'checksum': checksum,
            'models_to_update': [i['computer'].model_name for i in selected],
            'dates_to_update': sum(len(i['date_actions']) for i in selected),
            'photos_to_add': sum(len(i['photos']) for i in selected),
            'wrong_automatic_photos_to_retire': sum(len(i['retire']) for i in selected),
            'skipped': skipped, 'preserved': preserved, 'research': data['research']}


def photo_citation(model, photo):
    return {'title': 'Fotografia — '+model, 'url': photo['source_url'], 'author': photo.get('author'),
            'source_type': 'image', 'access_date': date(2026,11,24).isoformat()}


def apply(db, path=PACKAGE):
    try: return _apply(db,path)
    except Exception:
        db.rollback(); raise


def _apply(db,path):
    catalog_lock(db)
    data, checksum, selected, skipped, preserved = plan(db,path)
    report = {'version': data['version'], 'checksum': checksum, 'updated': 0, 'dates_filled': 0, 'dates_corrected': 0,
              'release_rows_created': 0, 'photos_added': 0, 'wrong_automatic_photos_retired': 0,
              'skipped': skipped, 'preserved': preserved}
    if not selected:
        db.rollback(); return {**report, 'already_applied': True}
    records = []; contexts = []
    for item in selected:
        c = item['computer']
        citation = item['date_actions'][0]['desired']['source'] if item['date_actions'] else photo_citation(c.model_name,item['photos'][0]) if item['photos'] else {'title': 'Fotografia preesistente — '+c.model_name, 'url': item['retire'][0].source_url}
        record = {'manufacturer': c.manufacturer.name, 'model_name': c.model_name, 'source': citation,
                  'evidence': 'Revisione esplicita Sun: sole date e immagini; nessun nuovo computer o prezzo.'}
        Record.model_validate(record); records.append(record)
        for action in item['date_actions']: contexts.extend(action['desired'].get('contexts',[]))
    raw = json.dumps({'version': data['version'], 'records': records, 'context_notes': contexts, 'package': data}, ensure_ascii=False).encode()
    job = stage(db,'manual',Path(path).name,'json',raw,records=records,
                options={'upload': True, 'existing_only': True, 'sun_research': data['version']},commit=False)
    changes = []; photo_changes = []
    for row,item in zip(job.rows,selected):
        if row.status == 'invalid': raise ValueError('Riga Sun non valida; operazione annullata.')
        c = item['computer']; row.computer_id = c.id
        for action in item['date_actions']:
            desired = action['desired']; target = action['target']; before = None
            citation = source(db,desired['source'],accessed=False)
            if citation not in c.sources: c.sources.append(citation)
            if target is None:
                target = Release(market=reference(db,Market,'Mercato non documentato'))
                c.releases.append(target); db.flush(); report['release_rows_created'] += 1
            else:
                before = {'release_date': date_text(target,'release_date'), 'catalog_details': deepcopy(target.catalog_details),
                          'source_links': [dict(r._mapping) for r in db.execute(select(release_source).where(release_source.c.target_id == target.id))]}
            previous = {'value': target.release_date.isoformat() if target.release_date else None, 'precision': target.release_precision}
            report['dates_corrected' if target.release_date else 'dates_filled'] += 1
            target.release_date,target.release_precision = historical_date(desired['release_date'])
            if citation not in target.sources: target.sources.append(citation)
            details = deepcopy(target.catalog_details or {})
            details.update(date_scope='reference' if desired['kind']=='reference' else 'model', date_sources=[citation.id],
                           date_evidence={'kind': desired['kind'], 'source_ids': [citation.id]})
            if desired['kind']=='reference': details['reference_note'] = desired['note']
            else: details.pop('reference_note',None)
            details['commercialization_notes'] = list(dict.fromkeys([*details.get('commercialization_notes',[]),desired['note']]))
            target.catalog_details = details
            row.claims.append(ImportClaim(computer_id=c.id, source_id=citation.id, entity='Release', target_id=target.id,
                field='release_date', value={'value': target.release_date.isoformat(), 'precision': target.release_precision},
                previous=previous, status='pending', estimated=False, evidence=desired['evidence']+' '+desired['note']))
            changes.append({'computer_id': c.id, 'release_id': target.id, 'before': before, 'desired': desired})
        for image in item['retire']:
            photo_changes.append({'computer_id': c.id, 'action': 'retire_unrelated_automatic_image',
                'before': {col.name: serialize(getattr(image,col.name)) for col in ComputerImage.__table__.columns}})
            if c.image_url == image.remote_url: c.image_url = None
            c.images.remove(image); report['wrong_automatic_photos_retired'] += 1
        manual_cover = any(i.is_primary and not (i.caption or '').startswith(AUTO_PHOTO) for i in c.images)
        if c.image_url and not any(i.remote_url == c.image_url and (i.caption or '').startswith(AUTO_PHOTO) for i in c.images): manual_cover = True
        for proposal in item['photos']:
            values = {k: v for k,v in proposal.items() if k not in ('image_url','permission_basis')}
            if not manual_cover:
                for i in c.images: i.is_primary = False
                c.image_url = None
            image = ComputerImage(remote_url=proposal['image_url'], **values, is_primary=not manual_cover,
                                  display_order=max((i.display_order for i in c.images),default=-1)+1)
            c.images.append(image); db.flush()
            citation = source(db,photo_citation(c.model_name,proposal))
            if citation not in c.sources: c.sources.append(citation)
            photo_changes.append({'computer_id': c.id, 'action': 'add_selected_image', 'image_id': image.id, 'proposal': proposal})
            report['photos_added'] += 1; manual_cover = True
        row.status = 'updated'; report['updated'] += 1
    job.status = 'completed'; report['import_job_id'] = job.id
    db.add(CatalogReconciliation(entity=ENTITY,source_id=0,target_id=0,
        note='Revisione Sun: date con provenienza, prezzi conservati, fotografie selezionate; nuove asserzioni pending.',
        snapshot={**report,'changes':changes,'photo_changes':photo_changes,'research':data['research']}))
    from ..catalog_store import refresh_pending
    db.flush(); refresh_pending(db,commit=False,locked=True); db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Applica il supplemento; senza opzione mostra l’anteprima.')
    args = parser.parse_args()
    from ..main import SessionLocal
    with SessionLocal() as db: result = apply(db) if args.apply else preview(db)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
