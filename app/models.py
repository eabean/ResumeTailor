"""
SQLAlchemy models for the application tracker.

Application status transitions:
  DRAFT ──▶ APPLIED ──▶ INTERVIEW ──▶ OFFER
                │                        │
                └──────────▶ REJECTED ◀──┘
"""

import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_PATH = "data/resume_tailor.db"


class ApplicationStatus(enum.Enum):
    DRAFT = "Draft"
    APPLIED = "Applied"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    REJECTED = "Rejected"


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String(255), nullable=False)
    job_title = Column(String(255), nullable=False)
    jd_snippet = Column(Text)           # first 500 chars of JD for reference
    resume_tex = Column(Text)           # tailored .tex source
    cover_letter_tex = Column(Text)     # cover letter .tex source
    status = Column(String(50), default=ApplicationStatus.DRAFT.value, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


def get_session_factory():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
