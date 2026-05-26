from .celery_app import celery_app
from datetime import datetime, UTC
from .database import SessionLocal
from . import models
import time, random

def _update_task(task_id: str, status: str, result = None, error = None):
    db = SessionLocal()
    try:
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.status = status
        task.result = result
        task.error = error
        if status in ("SUCCESS", "FAILURE"):
            task.completed_at = datetime.now(UTC)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@celery_app.task(bind=True)
def process_task(self, task_id: str, task_type: str, payload: dict):
    _update_task(task_id, "STARTED")
    try:
        if task_type == "generate_report":
            time.sleep(5)
            result = {
                "report": f"Report for {payload.get('name', 'unknown')}",
                "rows": random.randint(100, 10000),
                "generated_at": datetime.now(UTC).isoformat()
            }
        elif task_type == "process_data":
            time.sleep(3)
            data = payload.get("numbers", [])
            result = {"sum": sum(data), "avg": sum(data)/len(data) if data else 0}
        elif task_type == "send_email":
            time.sleep(2)
            result = {"sent_to": payload.get("email"), "status": "delivered"}
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        _update_task(task_id, "SUCCESS", result=result)
        return result
    except Exception as e:
        _update_task(task_id, "FAILURE", error=str(e))
        raise
