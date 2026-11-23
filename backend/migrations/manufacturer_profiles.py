"""Repeatable nullable columns for existing company records."""
import os
from sqlalchemy import create_engine
from app.manufacturer_profiles import ensure_schema
if __name__=='__main__':
    url=os.getenv('DATABASE_URL')
    if not url:raise SystemExit('DATABASE_URL richiesto.')
    from app.models import Base
    engine=create_engine(url)
    Base.metadata.create_all(engine)
    ensure_schema(engine)
