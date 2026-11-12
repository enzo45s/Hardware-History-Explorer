"""Add only ETL audit tables. Safe to run repeatedly on PostgreSQL and SQLite."""
import os
from sqlalchemy import create_engine
from app.models import Base
from app.import_models import ImportJob, ImportRow, ImportClaim, ExternalIdentity, CatalogReconciliation

TABLES = [c.__table__ for c in (ImportJob, ImportRow, ImportClaim, ExternalIdentity, CatalogReconciliation)]


def migrate(engine):
    if engine.dialect.name not in ('postgresql', 'sqlite'):
        raise ValueError('Database supportati: PostgreSQL, SQLite')
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=TABLES, checkfirst=True)


if __name__ == '__main__':
    url = os.getenv('DATABASE_URL')
    if not url:
        raise SystemExit('Imposta DATABASE_URL; esegui un backup e ferma l’API prima della migrazione')
    migrate(create_engine(url))
    print('Tabelle importazioni disponibili; dati esistenti conservati.')
