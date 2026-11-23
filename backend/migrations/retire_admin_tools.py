"""Retire obsolete research queues, retaining only catalog attribution and audit.

Repeatable, transactional SQLite/PostgreSQL migration. No catalog values,
sources or imported originals are deleted. Queue tables are dropped physically.
"""
import hashlib
import json
from sqlalchemy import inspect, select, text, func, MetaData, Table
from app.import_models import CatalogReconciliation, ImportJob

TABLES = ('history_research_items', 'history_research_jobs')


def migrate(engine):
    with engine.begin() as conn:
        if engine.dialect.name == 'postgresql':
            conn.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
        existing = set(inspect(conn).get_table_names())
        removed = [name for name in TABLES if name in existing]
        if not removed:
            return {'removed_tables': [], 'attributions': 0}
        metadata = MetaData()
        tables = {name: Table(name, metadata, autoload_with=conn, resolve_fks=False) for name in removed}
        counts = {name: conn.scalar(select(func.count()).select_from(table)) for name, table in tables.items()}
        retained = []
        items = tables.get('history_research_items')
        if items is not None:
            for row in conn.execute(select(items).where(items.c.status == 'updated').order_by(items.c.id)).mappings():
                result = row['result']
                if isinstance(result, str):
                    result = json.loads(result)
                if not isinstance(result, dict) or not result.get('description'):
                    continue
                if not all(isinstance(result.get(k), str) for k in ('title', 'url', 'license_url', 'method')):
                    raise ValueError('Attribuzione storica incompleta: ritiro annullato per non perdere i crediti del testo.')
                retained.append({**{k: result[k] for k in ('title', 'url', 'license_url', 'method')},
                    'computer_id': row['computer_id'], 'import_job_id': row['import_job_id'],
                    'description_sha256': hashlib.sha256(result['description'].encode()).hexdigest()})
        # Imported originals remain readable, but their retired remote task
        # cannot be accidentally restarted through the generic retry endpoint.
        for row in conn.execute(select(ImportJob.id, ImportJob.provider, ImportJob.request_options)):
            options = dict(row.request_options or {})
            managed = options.pop('managed_history', False)
            if managed or row.provider == 'italian_history':
                options['retired_feature'] = 'description_research'
                conn.execute(ImportJob.__table__.update().where(ImportJob.id == row.id).values(request_options=options))
        conn.execute(CatalogReconciliation.__table__.insert().values(
            entity='admin_retirement', source_id=0, target_id=0,
            note='Rimossi strumenti amministrativi dismessi. Attribuzioni, catalogo e originali ETL conservati.',
            snapshot={'removed_tables': removed, 'removed_counts': counts, 'description_attributions': retained}))
        for name in removed:
            tables[name].drop(conn)
        return {'removed_tables': removed, 'attributions': len(retained)}


if __name__ == '__main__':
    from app.main import engine
    print(json.dumps(migrate(engine), ensure_ascii=False))
