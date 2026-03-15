"""
Application tracker — SQLite CRUD operations.

Handles saving and retrieving job applications. The DB is created
automatically on first use via models.get_session_factory().
"""

from datetime import datetime
from typing import Optional

from app.models import Application, ApplicationStatus, get_session_factory

_SessionFactory = None


def _get_session():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = get_session_factory()
    return _SessionFactory()


def save_application(
    company: str,
    job_title: str,
    job_description: str,
    resume_tex: str,
    cover_letter_tex: str,
) -> int:
    """Save a new application record. Returns the new application ID."""
    session = _get_session()
    try:
        app = Application(
            company=company,
            job_title=job_title,
            jd_snippet=job_description[:500],
            resume_tex=resume_tex,
            cover_letter_tex=cover_letter_tex,
            status=ApplicationStatus.DRAFT.value,
        )
        session.add(app)
        session.commit()
        return app.id
    finally:
        session.close()


def get_all_applications() -> list[Application]:
    """Return all applications ordered by most recent first."""
    session = _get_session()
    try:
        return (
            session.query(Application)
            .order_by(Application.created_at.desc())
            .all()
        )
    finally:
        session.close()


def get_application(app_id: int) -> Optional[Application]:
    """Return a single application by ID, or None if not found."""
    session = _get_session()
    try:
        return session.get(Application, app_id)
    finally:
        session.close()


def update_status(app_id: int, status: str) -> None:
    """Update the status of an application."""
    session = _get_session()
    try:
        app = session.get(Application, app_id)
        if app is None:
            raise ValueError(f"Application {app_id} not found")
        app.status = status
        app.updated_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()


def delete_application(app_id: int) -> None:
    """Delete an application record."""
    session = _get_session()
    try:
        app = session.get(Application, app_id)
        if app is None:
            raise ValueError(f"Application {app_id} not found")
        session.delete(app)
        session.commit()
    finally:
        session.close()
