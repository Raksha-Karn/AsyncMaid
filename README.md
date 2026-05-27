<div align="center">

# 🫧 AsyncMaid

A lightweight but fully-featured async task runner. It accepts jobs through a clean REST API, queues them via Celery + Redis, processes them asynchronously, and stores results in a PostgreSQL database + **93% test overage :)**

> **Three task types out of the box:**
> `generate_report` · `process_data` · `send_email`

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-2f5027?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-446b3a?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Celery](https://img.shields.io/badge/Celery-5.x-5e8852?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-7.x-8aaa80?style=flat-square&logo=redis&logoColor=white)](https://redis.io)

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=2f5027,446b3a,5e8852&height=3&section=header" width="100%"/>

</div>

<br/>


<br/>

## ✦ Feature Highlights

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   🔐  JWT authentication   — register, login, token auth   │
│   📋  Task queue           — Celery workers + Redis broker  │
│   📊  Report generation    — from metrics or CSV uploads    │
│   📁  CSV analytics        — pandas-powered column stats    │
│   📧  Email dispatch       — SMTP with simulated fallback   │
│   🚦  Rate limiting        — 10 req/min per user via Redis  │
│   🖥️   Beautiful frontend   — single HTML file, no build     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

<br/>

## ✦ Architecture

```
                        ┌──────────────────┐
                        │   Browser / UI   │  ← Single HTML file
                        │  (Vanilla + TW)  │     
                        └────────┬─────────┘
                                 │ HTTP/REST
                        ┌────────▼─────────┐
                        │   FastAPI App    │  ← Auth, routing,
                        │  /auth  /tasks   │    rate limiting
                        └──┬──────────┬───┘
                           │          │
               ┌───────────▼──┐  ┌────▼──────────┐
               │  PostgreSQL  │  │  Redis Broker  │
               │  (tasks, DB) │  │  (queue + rate │
               └──────────────┘  │   limiting)    │
                                 └────────┬───────┘
                                          │
                                 ┌────────▼───────┐
                                 │  Celery Worker │  ← generate_report
                                 │                │     process_data
                                 └────────────────┘     send_email
```

<br/>

## Preview

### 1. Dashboard Page
Monitor your tasks here!

---

![Home](./screenshots/home_1.png)

### 2. Upload CSV Page
Upload any number of CSVs you need!

---
![Home](./screenshots/upload_1.png)

### 3. Tasks Page
Choose what you want to do!

---

![Home](./screenshots/report_1.png)

### 4. Reports Page
Check stats of generated reports!

---
![Home](./screenshots/report_1.png)

### 5. Process Data Page
Check numbers of your favorite CSV data!

---
![Home](./screenshots/process_2.png)

### 6. Email Page
See if the email was sent successfully!

---
![Home](./screenshots/email_2.png)



## ✦ Getting Started

### Prerequisites

- Python 3.11+
- Redis (running locally or via Docker)
- PostgreSQL database
- SMTP credentials *(optional — email tasks simulate delivery if not configured)*

---

### 1 · Clone

```bash
git clone https://github.com/Raksha-Karn/AsyncMaid.git
cd background_tasks
```

### 2 · Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
**OR**
```bash
uv sync                            # if using uv environment
```

### 3 · Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/asyncmaid

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-super-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=10080   # 7 days recommended

# File storage
STORAGE_ROOT=/storage
MAX_UPLOAD_SIZE_BYTES=10485760      # 10 MB

# SMTP (optional — leave blank to simulate)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@asyncmaid.local
SMTP_FROM_NAME=AsyncMaid
SMTP_USE_TLS=true
```

### 4 · Run database migrations

```bash
alembic upgrade head
```

### 5 · Start the services

In three separate terminals:

```bash
# Terminal 1 — FastAPI server
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker
celery -A app.celery_app worker --loglevel=info

# Terminal 3 — (optional) Celery Flower dashboard
celery -A app.celery_app flower --port=5555
```

### 6 · Open the frontend

Serve `frontend/index.html` from the same origin as the API, or open it directly if FastAPI serves static files:

```
http://localhost:8000
```

> **Tip:** If the frontend runs on a different origin, set `const API = 'http://localhost:8000'` at the top of the HTML file.

<br/>

## ✦ API Reference

All task endpoints require `Authorization: Bearer <token>`.

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Create an account |
| `POST` | `/auth/login` | Get a JWT token |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tasks` | Submit a new task |
| `GET` | `/tasks/my-tasks` | List your tasks |
| `GET` | `/tasks/{task_id}` | Get task detail + result |
| `DELETE` | `/tasks/{task_id}` | Delete a task |
| `POST` | `/tasks/uploads` | Upload a CSV file |

---
