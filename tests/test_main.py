import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.main import app
from app.database import Base, get_db

TEST_DB = "sqlite:///./test_main.db"
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


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_frontend_endpoint(client):
    r = client.get("/")
    assert r.status_code == 200


def test_upload_dir_config():
    from app.config import Settings

    settings = Settings()
    assert settings.upload_dir == settings.storage_root / "uploads"
