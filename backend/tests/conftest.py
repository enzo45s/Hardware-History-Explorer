"""Isolated databases: never run tests against development or production data."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy.engine import make_url

_test_files = TemporaryDirectory(prefix='hhe-tests-')
_test_url = os.getenv('HHE_TEST_DATABASE_URL', f'sqlite:///{_test_files.name}/tests.db')
if make_url(_test_url).get_backend_name() != 'sqlite' and not make_url(_test_url).database.endswith('_test'):
    raise RuntimeError('HHE_TEST_DATABASE_URL must use a dedicated database ending in _test')
os.environ['DATABASE_URL'] = _test_url
os.environ['UPLOAD_DIR'] = str(Path(_test_files.name) / 'uploads')

from app.main import Base, app, engine, UPLOAD_DIR  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    for file in UPLOAD_DIR.iterdir():
        file.unlink()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
