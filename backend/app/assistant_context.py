"""Search the whole catalog before selecting bounded, sourced model evidence."""
import re
import json
from sqlalchemy import select, or_, case, func, literal
from .models import Computer, Manufacturer
from .import_models import ImportClaim, ComputerAlias
from .source_policy import excluded_source_ids
from .importing.catalog_aliases import assertion_variant


def retrieve(db, question, eager, full):
    words = list(dict.fromkeys(w for w in re.findall(r'\w+', question.casefold())
                 if len(w) >= 2 and w not in {'che', 'con', 'del', 'della', 'dei', 'per', 'una', 'quali', 'sono', 'computer', 'calcolatori'}))[:15]
    conditions = [or_(Computer.model_name.icontains(w, autoescape=True), Manufacturer.name.icontains(w, autoescape=True),
        select(ComputerAlias.id).where(ComputerAlias.computer_id == Computer.id, ComputerAlias.original_name.icontains(w, autoescape=True)).exists()) for w in words]
    stmt = select(Computer).join(Computer.manufacturer)
    exact = func.instr(func.lower(literal(question)), func.lower(Computer.model_name)) > 0 if db.bind.dialect.name == 'sqlite' else func.strpos(func.lower(literal(question)), func.lower(Computer.model_name)) > 0
    if conditions:
        stmt = stmt.where(or_(exact, *conditions))
    stmt = stmt.order_by(case((exact, 0), else_=1), Computer.id.desc()).limit(30).options(*eager)
    rows = [full(c) for c in db.scalars(stmt).unique()]
    compact = []
    hidden_sources = excluded_source_ids(db)
    for r in rows:
        claims = db.scalars(select(ImportClaim).where(ImportClaim.computer_id == r['id'], ImportClaim.source_id.not_in(hidden_sources)).order_by(ImportClaim.id.desc()).limit(100)).all()
        base_words = set(re.findall(r'\w+', (r['model_name'] + ' ' + r['manufacturer']).casefold())) | {'ram', 'rom', 'rev', 'kb', 'mb', 'firmware'}
        def relevant(scope):
            return bool((set(re.findall(r'\w+', (scope or '').casefold())) - base_words) & set(words))
        configurations = sorted(r['display_configurations'], key=lambda cfg: not relevant(cfg.get('model_variant')))
        releases = sorted(r['releases'], key=lambda release: not relevant(release.get('model_variant')))
        claims.sort(key=lambda claim: not relevant(assertion_variant(db, claim)))
        item = {'id': r['id'], 'model': r['model_name'], 'manufacturer': r['manufacturer'], 'year': r['year'],
            'categories': r['categories'], 'description': (r.get('display_description', r['description']) or '')[:2000],
            'configurations': [{'name': v.get('display_name', v['variant_name']), 'specifications': v['specifications'][:12],
                'model_variant': v.get('model_variant'), 'description': v.get('variant_description') or v.get('display_description'),
                'regional_variants': v.get('regional_variants', []),
                'announcement_date': v.get('variant_announcement_date')} for v in configurations[:4]],
            'releases': releases[:5], 'sales': r['sales'][:5], 'reviews': r['reviews'][:5],
            'facts': [{**fact, 'statement': fact.get('display_statement', fact['statement'])} for fact in r['facts'][:5]], 'sources': r['sources'][:10],
            'import_assertions': [{'entity': c.entity, 'target_id': c.target_id, 'field': c.field, 'value': c.value,
                'status': c.status, 'estimated': c.estimated, 'model_variant': assertion_variant(db, c),
                'source': {'title': c.source.title, 'url': c.source.url}} for c in claims[:30]]}
        # Keep whole objects with citations; never cut a JSON string midway.
        if len(json.dumps(item, ensure_ascii=False)) > 25000:
            item['configurations'] = item['configurations'][:1]
            item['import_assertions'] = item['import_assertions'][:5]
            item['reviews'], item['facts'] = [], []
        if len(json.dumps(compact + [item], ensure_ascii=False)) > 60000:
            break
        compact.append(item)
    return {'catalog_total': db.scalar(select(func.count()).select_from(Computer)), 'retrieved': len(compact),
            'scope': 'Selezione di massimo 30 schede pertinenti; non rappresenta necessariamente tutto l’archivio. Le asserzioni sono storiche e possono differire dai valori correnti.', 'computers': compact}
