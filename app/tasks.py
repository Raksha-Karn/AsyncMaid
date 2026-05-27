from .celery_app import celery_app
from datetime import datetime, UTC
from email.message import EmailMessage
from email.utils import formataddr
import os
import smtplib
from statistics import mean
from typing import Any
from sqlalchemy import select
from dotenv import load_dotenv
from .database import SessionLocal
from . import models
from app.services.analytics import process_uploaded_csv

load_dotenv()

def _update_task(task_id: str, status: str, result = None, error = None):
    db = SessionLocal()
    try:
        task = db.execute(select(models.Task).where(models.Task.id == task_id)).scalar_one_or_none()
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


def _task_owner_id(db, task_id: str) -> int:
    task = db.execute(select(models.Task).where(models.Task.id == task_id)).scalar_one()
    return task.owner_id


def _coerce_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _build_metric_report(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") or payload.get("data_points") or []
    numeric_values = [_coerce_number(item.get("value") if isinstance(item, dict) else item) for item in metrics]
    numeric_values = [value for value in numeric_values if value is not None]

    report_name = payload.get("name") or payload.get("title") or "Operations report"
    sections = [
        {
            "title": "Executive summary",
            "body": payload.get(
                "summary",
                "This report was generated from the submitted business metrics and is ready for review.",
            ),
        }
    ]

    kpis: dict[str, Any] = {
        "metric_count": len(metrics),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    if numeric_values:
        kpis.update(
            {
                "total": round(sum(numeric_values), 2),
                "average": round(mean(numeric_values), 2),
                "minimum": round(min(numeric_values), 2),
                "maximum": round(max(numeric_values), 2),
            }
        )
        trend = "up" if numeric_values[-1] >= numeric_values[0] else "down"
        sections.append(
            {
                "title": "Trend signal",
                "body": f"The latest value is trending {trend} compared with the first submitted value.",
            }
        )

    recommendations = payload.get("recommendations") or [
        "Review the largest metric movements before the next operating cycle.",
        "Attach a source CSV when deeper column-level analytics are required.",
    ]

    return {
        "report": {
            "name": report_name,
            "status": "ready",
            "kpis": kpis,
            "sections": sections,
            "recommendations": recommendations,
        }
    }


def generate_report(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    upload_id = payload.get("upload_id")
    if upload_id:
        db = SessionLocal()
        try:
            owner_id = _task_owner_id(db, task_id)
            processed = process_uploaded_csv(db, owner_id=owner_id, upload_id=upload_id)
        finally:
            db.close()

        analytics = processed["analytics"]
        numeric_columns = analytics.get("numeric_statistics", {})
        largest_columns = sorted(
            numeric_columns.items(),
            key=lambda item: abs(item[1].get("sum") or 0),
            reverse=True,
        )[:3]
        recommendations = [
            "Prioritize columns with missing values before publishing downstream dashboards.",
            "Use the top numeric columns as candidates for trend monitoring and alerting.",
        ]
        if not numeric_columns:
            recommendations.append("Add numeric measures to this CSV for richer statistical analysis.")

        return {
            "report": {
                "name": payload.get("name") or f"Analytics report for {processed['upload']['filename']}",
                "status": "ready",
                "source": processed["upload"],
                "kpis": {
                    "rows": analytics["row_count"],
                    "columns": analytics["column_count"],
                    "numeric_columns": len(numeric_columns),
                    "generated_at": datetime.now(UTC).isoformat(),
                },
                "sections": [
                    {
                        "title": "Dataset profile",
                        "body": f"{analytics['row_count']} rows across {analytics['column_count']} columns were analyzed.",
                    },
                    {
                        "title": "Top numeric signals",
                        "body": ", ".join(column for column, _ in largest_columns) or "No numeric columns were detected.",
                    },
                ],
                "recommendations": recommendations,
                "analytics": analytics,
            }
        }

    return _build_metric_report(payload)


def _send_via_smtp(to_email: str, subject: str, body: str) -> dict[str, Any]:
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        return {"transport": "simulated", "message": "SMTP_HOST is not configured"}

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "noreply@taskmaid.local")
    sender_name = os.getenv("SMTP_FROM_NAME", "TaskMaid Analytics")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((sender_name, sender_email))
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
        if os.getenv("SMTP_USE_TLS", "true").lower() == "true":
            smtp.starttls()
        if smtp_user and smtp_password:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)

    return {"transport": "smtp", "host": smtp_host, "port": smtp_port}


def send_email(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    to_email = payload.get("email") or payload.get("to")
    if not to_email or "@" not in to_email:
        raise ValueError("send_email requires a valid payload.email")

    subject = payload.get("subject") or "Your analytics update is ready"
    message = payload.get("message") or payload.get("body") or "Your requested analytics workflow has completed."
    related_task_id = payload.get("related_task_id")

    if related_task_id:
        db = SessionLocal()
        try:
            owner_id = _task_owner_id(db, task_id)
            related_task = db.execute(
                select(models.Task).where(
                    models.Task.id == related_task_id,
                    models.Task.owner_id == owner_id,
                )
            ).scalar_one_or_none()
            if related_task is None:
                raise ValueError("Related task was not found for this user")
            if related_task.result:
                message = f"{message}\n\nRelated result:\n{related_task.result}"
        finally:
            db.close()

    delivery = _send_via_smtp(to_email, subject, message)
    return {
        "email": {
            "sent_to": to_email,
            "subject": subject,
            "status": "delivered" if delivery["transport"] == "smtp" else "queued_simulation",
            "delivered_at": datetime.now(UTC).isoformat(),
            **delivery,
        }
    }


@celery_app.task(bind=True)
def process_task(self, task_id: str, task_type: str, payload: dict):
    _update_task(task_id, "STARTED")
    try:
        if task_type == "generate_report":
            result = generate_report(task_id, payload)
        elif task_type == "process_data":
            upload_id = payload.get("upload_id")
            if not upload_id:
                raise ValueError("process_data requires payload.upload_id")
            db = SessionLocal()
            try:
                task = db.execute(select(models.Task).where(models.Task.id == task_id)).scalar_one()
                result = process_uploaded_csv(db, owner_id=task.owner_id, upload_id=upload_id)
            finally:
                db.close()
        elif task_type == "send_email":
            result = send_email(task_id, payload)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        _update_task(task_id, "SUCCESS", result=result)
        return result
    except Exception as e:
        _update_task(task_id, "FAILURE", error=str(e))
        raise
