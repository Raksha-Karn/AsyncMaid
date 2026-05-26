from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, autoflush=False)

engine = create_engine(DATABASE_URL)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()