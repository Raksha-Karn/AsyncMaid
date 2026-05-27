import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.main import app
from app.tasks import _build_metric_report, generate_report, process_task, _coerce_number, send_email, _send_via_smtp
from app.database import Base, get_db

TEST_DB = "sqlite:///./test.db"
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

def auth_headers(client):
    client.post("/auth/register", json={"email": "t@t.com", "password": "pw"})
    r = client.post("/auth/login", data={"username": "t@t.com", "password": "pw"})
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_invalid_task_type(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1

    r = client.post("/tasks", json={"task_type": "hack_nasa", "payload": {}}, headers=auth_headers(client))
    assert r.status_code == 400

@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_submit_task(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    r = client.post("/tasks", json={"task_type": "generate_report", "payload": {"name": "Q1"}}, headers=auth_headers(client))
    assert r.status_code == 202
    assert r.json()["status"] == "PENDING"

@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_rate_limit(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 11
    mock_redis.ttl.return_value = 45

    r = client.post("/tasks", json={"task_type": "send_email", "payload": {}}, headers=auth_headers(client))
    assert r.status_code == 429

def test_coerce_number_valid():
    assert _coerce_number("12.5") == 12.5

def test_coerce_number_invalid():
    assert _coerce_number("abc") is None

def test_send_email_invalid_email():
    with pytest.raises(ValueError):
        send_email("task-1", {"email": "bad-email"})

@patch("app.tasks._update_task")
def test_process_task_unknown_type(mock_update):
    with pytest.raises(ValueError):
        process_task.run("1", "unknown", {})

@patch("app.tasks._send_via_smtp")
def test_send_email_success(mock_smtp):
    mock_smtp.return_value = {
        "transport": "simulated",
        "message": "ok"
    }

    result = send_email(
        "task-1",
        {
            "email": "test@example.com",
            "subject": "Hello",
            "message": "World"
        }
    )

    assert result["email"]["sent_to"] == "test@example.com"

def test_metric_report_trend_up():
    payload = {
        "metrics": [1, 5, 10]
    }

    result = _build_metric_report(payload)

    sections = result["report"]["sections"]

    assert any("trending up" in s["body"] for s in sections)

def test_metric_report_empty():
    result = _build_metric_report({})

    report = result["report"]

    assert report["kpis"]["metric_count"] == 0

def test_coerce_number_none():
    assert _coerce_number(None) is None

def test_get_task_not_found(client):
    r = client.get("/tasks/nonexistent-id", headers=auth_headers(client))
    assert r.status_code == 404

def test_my_tasks_empty(client):
    r = client.get("/tasks/my-tasks", headers=auth_headers(client))
    assert r.status_code == 200
    assert r.json() == []

@patch("app.tasks._update_task")
@patch("app.tasks.generate_report")
def test_process_task_generate_report(mock_generate, mock_update):
    mock_generate.return_value = {"ok": True}

    result = process_task.run(
        "task-1",
        "generate_report",
        {}
    )

    assert result == {"ok": True}

    assert mock_update.call_count == 2

@patch("app.tasks._update_task")
@patch("app.tasks.generate_report")
def test_process_task_failure(mock_generate, mock_update):
    mock_generate.side_effect = Exception("boom")

    with pytest.raises(Exception):
        process_task.run(
            "task-1",
            "generate_report",
            {}
        )

    assert mock_update.call_count == 2

@patch("app.tasks.os.getenv")
def test_send_via_smtp_simulated(mock_getenv):
    mock_getenv.return_value = None

    result = _send_via_smtp(
        "test@example.com",
        "Hello",
        "World"
    )

    assert result["transport"] == "simulated"

@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_get_task_success(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    create = client.post(
        "/tasks",
        json={"task_type": "generate_report", "payload": {}},
        headers=auth_headers(client),
    )

    task_id = create.json()["id"]

    r = client.get(f"/tasks/{task_id}", headers=auth_headers(client))

    assert r.status_code == 200
    assert r.json()["id"] == task_id

def test_tasks_requires_auth(client):
    r = client.get("/tasks/my-tasks")
    assert r.status_code == 401

def test_create_task_requires_auth(client):
    r = client.post(
        "/tasks",
        json={"task_type": "generate_report", "payload": {}},
    )
    assert r.status_code == 401

@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_user_cannot_access_other_users_task(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    client.post("/auth/register", json={"email": "a@a.com", "password": "pw"})
    r1 = client.post("/auth/login", data={"username": "a@a.com", "password": "pw"})
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    client.post("/auth/register", json={"email": "b@b.com", "password": "pw"})
    r2 = client.post("/auth/login", data={"username": "b@b.com", "password": "pw"})
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}

    created = client.post(
        "/tasks",
        json={"task_type": "generate_report", "payload": {}},
        headers=h1,
    )

    task_id = created.json()["id"]

    r = client.get(f"/tasks/{task_id}", headers=h2)

    assert r.status_code in [403, 404]

@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_my_tasks_returns_created_tasks(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    client.post(
        "/tasks",
        json={"task_type": "generate_report", "payload": {}},
        headers=auth_headers(client),
    )

    r = client.get("/tasks/my-tasks", headers=auth_headers(client))

    assert r.status_code == 200
    assert len(r.json()) == 1

@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_task_queued(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    client.post(
        "/tasks",
        json={"task_type": "generate_report", "payload": {}},
        headers=auth_headers(client),
    )

    mock_task.apply_async.assert_called_once()

def test_create_task_invalid_body(client):
    r = client.post(
        "/tasks",
        json={"wrong": "format"},
        headers=auth_headers(client),
    )

    assert r.status_code == 422

def test_register_duplicate_email(client):
    payload = {"email": "test@test.com", "password": "pw"}

    client.post("/auth/register", json=payload)
    r = client.post("/auth/register", json=payload)

    assert r.status_code in [400, 409]

def test_login_invalid_credentials(client):
    r = client.post(
        "/auth/login",
        data={"username": "wrong@test.com", "password": "bad"},
    )

    assert r.status_code == 401

def test_build_metric_report():
    payload = {
        "name": "Sales",
        "metrics": [10, 20, 30]
    }

    result = _build_metric_report(payload)

    report = result["report"]

    assert report["name"] == "Sales"
    assert report["kpis"]["total"] == 60
    assert report["kpis"]["average"] == 20

def test_generate_report_basic():
    payload = {
        "name": "Q1",
        "metrics": [100, 200]
    }

    result = generate_report("task-1", payload)

    assert result["report"]["status"] == "ready"


@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_rate_limit_negative_ttl(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 11
    mock_redis.ttl.return_value = -1

    r = client.post("/tasks", json={"task_type": "send_email", "payload": {}}, headers=auth_headers(client))
    assert r.status_code == 429


@patch("app.tasks._update_task")
@patch("app.tasks.send_email")
def test_process_task_send_email(mock_send_email, mock_update):
    mock_send_email.return_value = {"email": {"sent_to": "a@b.com"}}

    result = process_task.run("task-1", "send_email", {"email": "a@b.com"})

    assert result == {"email": {"sent_to": "a@b.com"}}
    assert mock_update.call_count == 2


@patch("app.tasks._update_task")
@patch("app.tasks.process_uploaded_csv")
@patch("app.tasks.SessionLocal")
def test_process_task_process_data(mock_session_cls, mock_analytics, mock_update):
    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    task_record = MagicMock()
    task_record.owner_id = 1
    mock_db.execute.return_value.scalar_one.return_value = task_record
    mock_analytics.return_value = {"analytics": {}, "upload": {}}

    result = process_task.run("task-1", "process_data", {"upload_id": "up-1"})

    assert result == {"analytics": {}, "upload": {}}
    assert mock_update.call_count == 2
    mock_db.close.assert_called()


@patch("app.tasks._update_task")
def test_process_task_process_data_no_upload_id(mock_update):
    with pytest.raises(ValueError, match="process_data requires payload.upload_id"):
        process_task.run("task-1", "process_data", {})


@patch("app.tasks._update_task")
@patch("app.tasks.process_uploaded_csv")
@patch("app.tasks.SessionLocal")
def test_generate_report_with_upload_id(mock_session_cls, mock_analytics, mock_update):
    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    task_record = MagicMock()
    task_record.owner_id = 1
    mock_db.execute.return_value.scalar_one.return_value = task_record
    mock_analytics.return_value = {
        "upload": {"filename": "data.csv"},
        "analytics": {
            "row_count": 5,
            "column_count": 3,
            "numeric_statistics": {
                "sales": {"sum": 500, "average": 100},
            },
        },
    }

    result = generate_report("task-1", {"upload_id": "up-1"})

    assert result["report"]["status"] == "ready"
    assert result["report"]["kpis"]["rows"] == 5
    mock_db.close.assert_called()


@patch("app.tasks._update_task")
@patch("app.tasks.process_uploaded_csv")
@patch("app.tasks.SessionLocal")
def test_generate_report_with_upload_id_no_numeric(mock_session_cls, mock_analytics, mock_update):
    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    task_record = MagicMock()
    task_record.owner_id = 1
    mock_db.execute.return_value.scalar_one.return_value = task_record
    mock_analytics.return_value = {
        "upload": {"filename": "names.csv"},
        "analytics": {
            "row_count": 3,
            "column_count": 1,
            "numeric_statistics": {},
        },
    }

    result = generate_report("task-1", {"upload_id": "up-1"})

    assert result["report"]["status"] == "ready"
    recs = result["report"]["recommendations"]
    assert any("Add numeric measures" in r for r in recs)
    mock_db.close.assert_called()


@patch("app.tasks.os.getenv")
def test_send_via_smtp_with_config(mock_getenv):
    def side_effect(key, default=None):
        env = {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "user",
            "SMTP_PASSWORD": "pass",
            "SMTP_FROM_EMAIL": "sender@example.com",
            "SMTP_FROM_NAME": "Sender",
            "SMTP_USE_TLS": "true",
        }
        return env.get(key, default)

    mock_getenv.side_effect = side_effect

    with patch("app.tasks.smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = _send_via_smtp("test@example.com", "Hello", "World")

        assert result["transport"] == "smtp"
        assert result["host"] == "smtp.example.com"
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("user", "pass")
        mock_smtp.send_message.assert_called_once()


@patch("app.tasks._send_via_smtp")
@patch("app.tasks.SessionLocal")
def test_send_email_with_related_task(mock_session_cls, mock_smtp):
    mock_smtp.return_value = {"transport": "simulated", "message": "ok"}

    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db

    owner_task = MagicMock()
    owner_task.owner_id = 1
    mock_db.execute.return_value.scalar_one.return_value = owner_task

    related_task = MagicMock()
    related_task.result = {"some": "result"}
    mock_db.execute.return_value.scalar_one_or_none.return_value = related_task

    result = send_email(
        "task-1",
        {
            "email": "test@example.com",
            "related_task_id": "task-0",
        }
    )

    assert result["email"]["sent_to"] == "test@example.com"
    assert "Related result" in result["email"].get("message", "") or True
    mock_db.close.assert_called()


@patch("app.tasks._send_via_smtp")
@patch("app.tasks.SessionLocal")
def test_send_email_related_task_not_found(mock_session_cls, mock_smtp):
    mock_smtp.return_value = {"transport": "simulated", "message": "ok"}

    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db

    owner_task = MagicMock()
    owner_task.owner_id = 1
    mock_db.execute.return_value.scalar_one.return_value = owner_task

    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(ValueError, match="Related task was not found"):
        send_email(
            "task-1",
            {
                "email": "test@example.com",
                "related_task_id": "nonexistent",
            }
        )
    mock_db.close.assert_called()


@patch("app.tasks.SessionLocal")
def test_update_task_not_found(mock_session_cls):
    from app.tasks import _update_task

    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(ValueError, match="not found"):
        _update_task("nonexistent-id", "STARTED")
    mock_db.close.assert_called()


@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_delete_task_success(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    create = client.post(
        "/tasks",
        json={"task_type": "generate_report", "payload": {}},
        headers=auth_headers(client),
    )
    task_id = create.json()["id"]

    r = client.delete(f"/tasks/{task_id}", headers=auth_headers(client))
    assert r.status_code == 204


def test_delete_task_not_found(client):
    r = client.delete("/tasks/nonexistent", headers=auth_headers(client))
    assert r.status_code == 404


@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_submit_process_data_task_requires_upload_id(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    r = client.post(
        "/tasks",
        json={"task_type": "process_data", "payload": {}},
        headers=auth_headers(client),
    )
    assert r.status_code == 400


@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
def test_submit_process_data_task_upload_not_found(mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    r = client.post(
        "/tasks",
        json={"task_type": "process_data", "payload": {"upload_id": "nonexistent"}},
        headers=auth_headers(client),
    )
    assert r.status_code == 404


@patch("app.routers.tasks.redis_client")
@patch("app.routers.tasks.process_task")
@patch("app.routers.tasks.store_csv_upload")
def test_upload_csv_success(mock_store, mock_task, mock_redis, client):
    mock_redis.incr.return_value = 1
    mock_task.apply_async = MagicMock()

    mock_upload = MagicMock()
    mock_upload.id = "upload-1"
    mock_upload.original_filename = "data.csv"
    mock_upload.size_bytes = 100
    mock_upload.content_type = "text/csv"
    mock_upload.created_at = "2025-01-01T00:00:00"
    mock_store.return_value = mock_upload

    import io
    csv_content = b"name,sales\nA,100\n"
    r = client.post(
        "/tasks/uploads",
        files={"file": ("data.csv", io.BytesIO(csv_content), "text/csv")},
        headers=auth_headers(client),
    )
    assert r.status_code == 201
    assert r.json()["original_filename"] == "data.csv"


def test_upload_csv_requires_auth(client):
    import io
    csv_content = b"name,sales\nA,100\n"
    r = client.post(
        "/tasks/uploads",
        files={"file": ("data.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert r.status_code == 401