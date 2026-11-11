"""Repair the review scale constraint without removing rows or references.

Back up first; stop the API, then run `python -m migrations.review_score` with
DATABASE_URL set. Invalid existing scores block migration instead of being changed.
"""
import os

from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.schema import CreateTable

from app.models import Computer, Review

CONSTRAINT = 'score IS NULL OR (max_score IS NOT NULL AND max_score > 0 AND score >= 0 AND score <= max_score)'


def migrate(engine):
    if engine.dialect.name not in ('sqlite', 'postgresql'):
        raise ValueError('Only SQLite and PostgreSQL are supported')
    inspector = inspect(engine)
    if {c['name'] for c in inspector.get_columns('reviews')} != set(Review.__table__.columns.keys()):
        raise ValueError('Unexpected review columns; inspect this schema before migrating')
    checks = inspector.get_check_constraints('reviews')
    if any(c['name'] == 'valid_score' and 'max_score is not null' in c['sqltext'].lower() for c in checks):
        return
    with engine.connect() as conn:
        if engine.dialect.name == 'sqlite':
            conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
            conn.commit()
        try:
            # BEGIN IMMEDIATE makes SQLite DDL transactional and excludes writers.
            if engine.dialect.name == 'sqlite':
                conn.exec_driver_sql('BEGIN IMMEDIATE')
            else:
                conn.begin()
                conn.exec_driver_sql('LOCK TABLE reviews IN ACCESS EXCLUSIVE MODE')
            invalid = conn.scalar(text('SELECT COUNT(*) FROM reviews WHERE score IS NOT NULL AND (max_score IS NULL OR max_score <= 0 OR score < 0 OR score > max_score)'))
            if invalid:
                raise ValueError(f'{invalid} review scores need a valid scale; no data changed')
            if engine.dialect.name == 'postgresql':
                conn.exec_driver_sql(f'ALTER TABLE reviews DROP CONSTRAINT valid_score, ADD CONSTRAINT valid_score CHECK ({CONSTRAINT})')
            else:
                schema = MetaData()
                Computer.__table__.to_metadata(schema)
                replacement = Review.__table__.to_metadata(schema, name='reviews_new')
                extras = conn.scalars(text("SELECT sql FROM sqlite_master WHERE tbl_name='reviews' AND type IN ('index','trigger') AND sql IS NOT NULL")).all()
                conn.execute(CreateTable(replacement))
                columns = ', '.join(Review.__table__.columns.keys())
                conn.exec_driver_sql(f'INSERT INTO reviews_new ({columns}) SELECT {columns} FROM reviews')
                conn.exec_driver_sql('DROP TABLE reviews')
                conn.exec_driver_sql('ALTER TABLE reviews_new RENAME TO reviews')
                for statement in extras:
                    conn.exec_driver_sql(statement)
                if conn.exec_driver_sql('PRAGMA foreign_key_check').first():
                    raise ValueError('Foreign key violations found; migration rolled back')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if engine.dialect.name == 'sqlite':
                conn.exec_driver_sql('PRAGMA foreign_keys=ON')
                conn.commit()


if __name__ == '__main__':
    url = os.getenv('DATABASE_URL')
    if not url:
        raise SystemExit('Set DATABASE_URL to the database to migrate; back up and stop the API first')
    migrate(create_engine(url))
    print('Review score constraint is up to date; existing rows preserved.')
