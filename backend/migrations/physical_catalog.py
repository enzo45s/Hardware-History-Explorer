"""Add metadata columns safely; data cleanup remains an explicit operation."""
import os
from sqlalchemy import create_engine
from app.catalog_schema import ensure_schema as migrate


if __name__=='__main__':
    url=os.getenv('DATABASE_URL')
    if not url:raise SystemExit('DATABASE_URL richiesto.')
    migrate(create_engine(url))
