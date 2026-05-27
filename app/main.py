from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.routers import users, tasks

app = FastAPI(title="AsyncMaid - Task Queue API", version="2.0.0")
app.include_router(users.router)
app.include_router(tasks.router)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def frontend():
    return FileResponse(static_dir / "index.html")

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
