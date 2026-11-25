import os
from pathlib import Path

# A dedicated SQLite file makes the suite runnable without PostgreSQL or Docker.
TEST_DB = Path('/tmp/horizon_voice_pytest.sqlite3')
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB}'
os.environ['AUTO_CREATE_SCHEMA'] = 'true'
os.environ['JWT_SECRET'] = 'pytest-only-secret-never-use-in-production'
os.environ['ENVIRONMENT'] = 'test'
os.environ['COOKIE_SECURE'] = 'false'

import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine
from app.main import app, _rate_limit_hits, _rate_limit_lock


@pytest.fixture(autouse=True)
def reset_database():
    with _rate_limit_lock:
        _rate_limit_hits.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
