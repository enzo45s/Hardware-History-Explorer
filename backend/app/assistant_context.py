"""Search the whole catalog before selecting bounded, sourced model evidence."""
import re
import json
from sqlalchemy import select, or_, case, func, literal
from .models import Computer, Manufacturer
from .import_models import ImportClaim


def retrieve(db, question, eager, full):
    words = list(dict.fromkeys(w for w in re.findall(r'\w+', question.casefold())
                 if len(w) >= 2 and w not in {'che', 'con', 'del', 'della', 'dei', 'per', 'una', 'quali', 'sono', 'computer', 'calcolatori'}))[:15]
    conditions = [or_(Computer.model_name.icontains(w, autoescape=True), Manufacturer.name.icontains(w, autoescape=True)) for w in words]
    stmt = select(Computer).join(Computer.manufacturer)
    exact = func.instr(func.lower(literal(question)), func.lower(Computer.model_name)) > 0 if db.bind.dialect.name == 'sqlite' else func.strpos(func.lower(literal(question)), func.lower(Computer.model_name)) > 0
    if conditions:
        stmt = stmt.where(or_(exact, *conditions))
    stmt = stmt.order_by(case((exact, 0), else_=1), Computer.id.desc()).limit(30).options(*eager)
    rows = [full(c) for c in db.scalars(stmt).unique()]
    compact = []
    for r in rows:
        claims = db.scalars(select(ImportClaim).where(ImportClaim.computer_id == r['id']).order_by(ImportClaim.id.desc()).limit(100)).all()
        item = {'id': r['id'], 'model': r['model_name'], 'manufacturer': r['manufacturer'], 'year': r['year'],
            'categories': r['categories'], 'description': (r.get('display_description', r['description']) or '')[:2000],
            'configurations': [{'name': v.get('display_name', v['variant_name']), 'specifications': v['specifications'][:12]} for v in r['configurations'][:4]],
            'releases': r['releases'][:5], 'sales': r['sales'][:5], 'reviews': r['reviews'][:5], 'facts': r['facts'][:5], 'sources': r['sources'][:10],
            'import_assertions': [{'entity': c.entity, 'target_id': c.target_id, 'field': c.field, 'value': c.value,
                'status': c.status, 'estimated': c.estimated, 'source': {'title': c.source.title, 'url': c.source.url}} for c in claims[:30]]}
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
