"""Date roles from existing provenance and a small reviewed factual proof set.

Dataset registration years of regional/firmware variants are not independent
commercial offers. Runtime never fetches sites or infers markets from currency.
"""
from pathlib import Path
import json
import re
from .source_policy import is_mame_source
from .importing.normalize import name_key
from .importing.identity import price_model_keys

PROOFS = Path(__file__).parent/'importing/data/commercial-dates-v1.json'


def evidence(computer, release, history):
    """Recover which sources supported a date before old physical merges."""
    source_map={s.id:s for s in release.sources}
    details=release.catalog_details or {}
    if details.get('date_manual'):
        return {'kind':'documented','source_ids':sorted(source_map)}
    ids=details.get('date_sources')
    if ids is None:
        ids=[]
        for event in reversed(history):
            matching=[]
            for old in event['original']['releases']:
                mapped=event['redirects']['Release'].get(str(old['id']),event['redirects']['Release'].get(old['id']))
                if mapped!=release.id or not old.get('release_date'):continue
                if release.release_date and release.release_date.isoformat().startswith(old['release_date'][:{'year':4,'month':7}.get(old.get('release_precision'),10)]):
                    matching.append((old['id'],{'year':4,'month':7}.get(old.get('release_precision'),10)))
            if matching:
                precision=max(length for _,length in matching)
                selected={identifier for identifier,length in matching if length==precision}
                ids=[r['source_id'] for r in event['original']['release_sources'] if r['target_id'] in selected]
                break
    if not ids:ids=list(source_map)
    supporting=[source_map[i] for i in ids if i in source_map]
    if not supporting:
        return {'kind':'reference','base':False,'source_ids':[]}
    if any(not is_mame_source(s) for s in supporting):
        return {'kind':'documented_launch' if details.get('date_evidence',{}).get('kind')=='documented_launch' else 'documented','source_ids':sorted(s.id for s in supporting)}
    expected=details.get('model_variant') or computer.model_name
    previous=details.get('date_evidence',{})
    # A merged regional profile may no longer carry its former model_variant
    # name. Preserve the established role while its supporting IDs agree.
    base=bool(previous.get('base') and sorted(previous.get('source_ids',[]))==sorted(s.id for s in supporting))
    for src in supporting:
        match=re.fullmatch(r'MAME\s*—\s*(.+?)\s*—\s*anno registrato',src.title or '')
        if match and name_key(match[1])==name_key(expected):base=True
    return {'kind':'reference','base':base,'source_ids':sorted(s.id for s in supporting)}


def annotate(computer, payload):
    from sqlalchemy.orm import object_session
    from .catalog_cleanup import history
    db=object_session(computer)
    events=list(history(db,computer.id)) if db is not None else []
    actual={r.id:r for r in computer.releases}
    proofs=json.loads(PROOFS.read_text())['records']
    identity=price_model_keys(computer.manufacturer.name,computer.model_name)
    for row in payload['releases']:
        release=actual[row['id']]
        if release.release_date:
            row['date_evidence']=evidence(computer,release,events)
        if (release.catalog_details or {}).get('date_manual'):
            continue
        for proof in proofs:
            if not identity & price_model_keys(proof['manufacturer'],proof['model_name']):continue
            src=next((s for s in release.sources if s.url==proof['url']),None)
            if src is None or (release.price,release.currency)!=(proof['price'],proof['currency']):continue
            if release.release_date and row.get('date_evidence',{}).get('kind')!='reference':continue
            row['documented_launch']={'date':proof['launch_date'],'source_id':src.id,
                'note':proof['note'],'proof_id':proof['id']}
