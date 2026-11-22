"""Additive, repeatable SQLite/PostgreSQL migration and precise invalidation.

Only derived catalog tables and our own triggers are created. Historical rows,
keys, source links and existing verification decisions are never rewritten.
"""
import hashlib
from pathlib import Path
from sqlalchemy import text
from .models import (CatalogSnapshot, CatalogDirty, CatalogMetric,
                     catalog_metric_assertions, catalog_metric_sources)

TABLES = [CatalogSnapshot.__table__, CatalogDirty.__table__, CatalogMetric.__table__,
          catalog_metric_assertions, catalog_metric_sources]
# A rule change must rebuild persisted facts even when original rows did not
# change. Hash the resolver and its vocabulary, not a deployment timestamp.
_ROOT = Path(__file__).parent
_RULES = ('catalog_memory.py', 'catalog_store.py', 'technical_display.py', 'release_display.py',
          'configuration_display.py', 'catalog_display.py', 'variant_context.py', 'source_policy.py',
          'importing/vocabulary.py', 'importing/regional_names.py', 'importing/identity.py',
          'importing/normalize.py', 'ram_values.py', 'history_sources.py', 'geography.py', 'catalog_names.py')
VERSION = 'hhe-catalog-v1.' + hashlib.sha256(b''.join((_ROOT / p).read_bytes() for p in _RULES)).hexdigest()[:16]


def ensure_schema(engine):
    if engine.dialect.name not in ('sqlite', 'postgresql'):
        raise ValueError('Il catalogo consolidato richiede SQLite o PostgreSQL.')
    from .models import Base
    with engine.begin() as conn:
        if engine.dialect.name == 'postgresql':
            conn.execute(text('SELECT pg_advisory_xact_lock(68484931)'))
        Base.metadata.create_all(conn, tables=TABLES)
        # Each expression is a SELECT of existing computers. On cascading
        # deletion of a computer, children cannot resurrect its queue entry.
        targets = {
            'computers': lambda r: f'SELECT id FROM computers WHERE id={r}.id',
            'configurations': lambda r: f'SELECT id FROM computers WHERE id={r}.computer_id',
            'specifications': lambda r: f'SELECT c.id FROM computers c JOIN configurations f ON f.computer_id=c.id WHERE f.id={r}.configuration_id',
            'releases': lambda r: f'SELECT id FROM computers WHERE id={r}.computer_id',
            'computer_aliases': lambda r: f'SELECT id FROM computers WHERE id={r}.computer_id',
            'manufacturers': lambda r: f'SELECT id FROM computers WHERE manufacturer_id={r}.id',
            'markets': lambda r: f'SELECT computer_id FROM releases WHERE market_id={r}.id',
            'specification_sources': lambda r: f'SELECT f.computer_id FROM configurations f JOIN specifications s ON s.configuration_id=f.id WHERE s.id={r}.target_id',
            'release_sources': lambda r: f'SELECT computer_id FROM releases WHERE id={r}.target_id',
            'sources': lambda r: f'''SELECT f.computer_id FROM configurations f JOIN specifications s ON s.configuration_id=f.id
                 JOIN specification_sources l ON l.target_id=s.id WHERE l.source_id={r}.id
                 UNION SELECT v.computer_id FROM releases v JOIN release_sources l ON l.target_id=v.id WHERE l.source_id={r}.id''',
        }
        for table, target in targets.items():
            operations = ('INSERT', 'UPDATE') if table == 'computers' else ('UPDATE', 'DELETE') if table in ('sources', 'manufacturers', 'markets') else ('INSERT', 'UPDATE', 'DELETE')
            for operation in operations:
                name = f'hhe_catalog_{table}_{operation.lower()}'
                refs = ('OLD', 'NEW') if operation == 'UPDATE' else ('OLD',) if operation == 'DELETE' else ('NEW',)
                sql = '\n'.join(f'''INSERT INTO catalog_dirty(computer_id,generation)
                    SELECT DISTINCT c.id,1 FROM computers c WHERE c.id IN ({target(ref)})
                    ON CONFLICT(computer_id) DO UPDATE SET generation=catalog_dirty.generation+1;''' for ref in refs)
                # BEFORE source deletion can still traverse its links. Child
                # deletions are handled similarly before a cascade erases them.
                timing = 'BEFORE' if operation == 'DELETE' else 'AFTER'
                if engine.dialect.name == 'sqlite':
                    conn.exec_driver_sql(f'CREATE TRIGGER IF NOT EXISTS {name} {timing} {operation} ON {table} BEGIN {sql} END')
                else:
                    conn.exec_driver_sql(f'''CREATE OR REPLACE FUNCTION {name}_fn() RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN {sql} RETURN {'OLD' if operation == 'DELETE' else 'NEW'}; END $$''')
                    conn.exec_driver_sql(f'DROP TRIGGER IF EXISTS {name} ON {table}')
                    conn.exec_driver_sql(f'CREATE TRIGGER {name} {timing} {operation} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}_fn()')
        conn.execute(text('''INSERT INTO catalog_dirty(computer_id,generation)
            SELECT c.id,1 FROM computers c LEFT JOIN catalog_snapshots s ON s.computer_id=c.id
            WHERE s.computer_id IS NULL OR s.version<>:version
            ON CONFLICT(computer_id) DO NOTHING'''), {'version': VERSION})
