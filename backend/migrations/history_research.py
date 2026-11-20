"""Idempotent additive tables; no modification of existing catalog records."""
import os
from sqlalchemy import create_engine
from app.models import Base
from app.import_models import ImportJob  # referenced by the evidence rows
from app.history_models import HistoryJob, HistoryItem


def migrate(engine):
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=[HistoryJob.__table__, HistoryItem.__table__], checkfirst=True)


if __name__ == '__main__':
    url = os.getenv('DATABASE_URL')
    if not url:
        raise SystemExit('Imposta DATABASE_URL; esegui un backup prima della migrazione.')
    migrate(create_engine(url))
