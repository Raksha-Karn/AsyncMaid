import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.main import app
from app.database import Base, get_db

TEST_DB = "sqlite:///./test_auth.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def client():
    Base.metadata.create_all(bind=engine)

    def override():
        yield TestSession()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    Base.metadata.drop_all(engine)


def test_decode_token_invalid_token(client):
    r = client.get(
        "/tasks/my-tasks",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert r.status_code == 401


def test_decode_token_no_sub(client):
    from app.auth import create_access_token

    token = create_access_token({"no_sub": "value"})
    r = client.get(
        "/tasks/my-tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


def test_decode_token_user_not_found(client):
    from app.auth import create_access_token

    token = create_access_token({"sub": "nonexistent@example.com"})
    r = client.get(
        "/tasks/my-tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401
