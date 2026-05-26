from fastapi import FastAPI
from app.routers import users, tasks

app = FastAPI(title="Task Queue API", version="2.0.0")
app.include_router(users.router)
app.include_router(tasks.router)

@app.get("/")
def health():
    return {"status": "ok", "version": "2.0.0"}