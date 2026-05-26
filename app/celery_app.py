from celery import Celery
from dotenv import load_dotenv
import os

load_dotenv()

celery_app = Celery(
    "task_queue",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL"),
    include=["app.tasks"]
)

celery_app.conf.update(
    task_track_started = True,
    timezone = "UTC",
    enable_utc = True
)