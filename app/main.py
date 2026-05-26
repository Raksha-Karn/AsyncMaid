from fastapi import FastAPI

app = FastAPI(title="Task Queue API", version="2.0.0")

@app.get("/")
def health():
    return {"status": "ok"}