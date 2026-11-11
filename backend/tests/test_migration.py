import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from migrations.review_score import migrate


@pytest.mark.parametrize('invalid', [False, True])
def test_sqlite_migration_preserves_rows_and_evidence(tmp_path, invalid):
    engine = create_engine(f'sqlite:///{tmp_path}/old.db')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE computers (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('INSERT INTO computers VALUES (1)')
        conn.exec_driver_sql('CREATE TABLE reviews (id INTEGER PRIMARY KEY, computer_id INTEGER NOT NULL REFERENCES computers(id), publication VARCHAR(160) NOT NULL, review_date DATE, score FLOAT, max_score FLOAT, summary TEXT, CONSTRAINT valid_score CHECK (score IS NULL OR (max_score > 0 AND score >= 0 AND score <= max_score)))')
        conn.exec_driver_sql('CREATE TABLE evidence (review_id INTEGER REFERENCES reviews(id), note TEXT)')
        conn.exec_driver_sql('CREATE INDEX review_publication ON reviews(publication)')
        conn.execute(text("INSERT INTO reviews VALUES (1,1,'Example',NULL,4,:scale,'preserve')"), {'scale': None if invalid else 5})
        conn.exec_driver_sql("INSERT INTO evidence VALUES (1,'keep reference')")
    if invalid:
        with pytest.raises(ValueError, match='no data changed'):
            migrate(engine)
    else:
        migrate(engine)
        migrate(engine)  # repeatable
        with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql("INSERT INTO reviews VALUES (2,1,'Invalid',NULL,4,NULL,NULL)")
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT summary FROM reviews').scalar() == 'preserve'
        assert conn.exec_driver_sql('SELECT note FROM evidence JOIN reviews ON reviews.id=evidence.review_id').scalar() == 'keep reference'
        assert conn.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert conn.exec_driver_sql("SELECT count(*) FROM sqlite_master WHERE name='review_publication'").scalar() == 1


def test_postgresql_migration(client):
    from app.main import engine as app_engine
    if app_engine.dialect.name != 'postgresql':
        pytest.skip('Dedicated PostgreSQL test database required')
    with app_engine.begin() as conn:
        conn.exec_driver_sql('ALTER TABLE reviews DROP CONSTRAINT valid_score, ADD CONSTRAINT valid_score CHECK (score IS NULL OR (max_score > 0 AND score >= 0 AND score <= max_score))')
        conn.exec_driver_sql("INSERT INTO reviews (computer_id,publication,score,max_score) VALUES (1,'Preserve',4,5)")
    migrate(app_engine)
    migrate(app_engine)
    with app_engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT score FROM reviews WHERE publication='Preserve'").scalar() == 4
        with pytest.raises(IntegrityError):
            conn.exec_driver_sql("INSERT INTO reviews (computer_id,publication,score,max_score) VALUES (1,'Invalid',4,NULL)")
