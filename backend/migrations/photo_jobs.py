"""Add durable automatic-photo queues without altering existing catalog tables."""
import os
from sqlalchemy import create_engine
from app.models import Base
from app.photo_jobs import PhotoJob, PhotoItem


def migrate(engine):
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=[PhotoJob.__table__, PhotoItem.__table__], checkfirst=True)


if __name__ == '__main__':
    migrate(create_engine(os.environ['DATABASE_URL']))
    print('Code fotografiche disponibili; catalogo conservato.')
