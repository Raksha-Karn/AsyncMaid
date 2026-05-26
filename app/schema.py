from .database import Base
from .models import User, Task
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Any
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    task_type: str
    payload: dict = Field(default_factory=dict)


class TaskOut(BaseModel):
    id: int
    task_type: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime]
    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str