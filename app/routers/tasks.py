from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
import os, uuid
from redis import Redis
from app.models import Task, UploadedFile
from dotenv import load_dotenv
from app.schema import TaskOut, TaskCreate, UploadedFileOut
from app.auth import decode_token
from app.database import get_db
from app.tasks import process_task
from app.services.uploads import store_csv_upload

load_dotenv()

router = APIRouter(prefix="/tasks", tags=["tasks"])
redis_client = Redis.from_url(os.getenv("REDIS_URL"))

VALID_TASK_TYPES = {"generate_report", "process_data", "send_email"}

def check_rate_limit(user_email: str):
    key = f"rate:{user_email}"
    count = redis_client.incr(name=key)
    if count == 1:
        redis_client.expire(key, time=60)
    if count > 10:
        ttl = redis_client.ttl(key)
        if ttl < 0:
            ttl = 60
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Try again in {ttl} seconds!"
        )

@router.post("", response_model=TaskOut, status_code=202)
def submit_task(data: TaskCreate, db: Session = Depends(get_db), user = Depends(decode_token)):
    if data.task_type not in VALID_TASK_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid task type. Choose from {VALID_TASK_TYPES}")
    if data.task_type == "process_data":
        upload_id = data.payload.get("upload_id")
        if not upload_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="process_data requires payload.upload_id")
        uploaded_file = db.execute(
            select(UploadedFile).where(
                UploadedFile.id == upload_id,
                UploadedFile.owner_id == user.id,
            )
        ).scalar_one_or_none()
        if uploaded_file is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded CSV file not found")
    check_rate_limit(user.email)

    task_id = str(uuid.uuid4())
    task_record = Task(
        id=task_id,
        task_type=data.task_type,
        status="PENDING",
        owner_id=user.id
    )
    db.add(task_record); db.commit(); db.refresh(task_record)

    process_task.apply_async(
        args=[task_id, data.task_type, data.payload],
        task_id=task_id
    )
    return task_record

@router.post("/uploads", response_model=UploadedFileOut, status_code=201)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db), user = Depends(decode_token)):
    return await store_csv_upload(db, file=file, owner_id=user.id)

@router.get("/my-tasks", response_model=list[TaskOut])
def my_tasks(skip: int = 0, limit: int = 20, db: Session = Depends(get_db), user = Depends(decode_token)):
    stmt = (select(Task).where(Task.owner_id == user.id).order_by(Task.created_at.desc()).offset(skip).limit(limit))
    return db.execute(stmt).scalars().all()

@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db), user = Depends(decode_token)):
    task = db.execute(select(Task).where(Task.id == task_id, Task.owner_id == user.id)).scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task not found!")
    return task
        
@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, db: Session = Depends(get_db), user = Depends(decode_token)):
    task = db.execute(select(Task).where(Task.id == task_id, Task.owner_id == user.id)).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task not found!")
    db.delete(task)
    db.commit()
    return None
