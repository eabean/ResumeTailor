"""
Tests for tracker.py — SQLite application CRUD.

Covers:
  [D] save_application: inserts a record, returns an ID
  [E] get_all_applications: returns records ordered by most recent
  [J] update_status: changes the status of an existing record
      Edge case: update/delete non-existent ID raises ValueError
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app import tracker


@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch):
    """Replace the tracker's session factory with an in-memory SQLite DB."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)

    monkeypatch.setattr(tracker, "_SessionFactory", SessionFactory)
    yield
    Base.metadata.drop_all(engine)


def _save(company="Acme", title="Engineer", jd="Some JD", resume="tex", cover="cover"):
    return tracker.save_application(company, title, jd, resume, cover)


class TestSaveApplication:
    def test_returns_positive_integer_id(self):
        app_id = _save()
        assert isinstance(app_id, int)
        assert app_id > 0

    def test_saved_record_is_retrievable(self):
        app_id = _save(company="TestCo", title="Dev")
        app = tracker.get_application(app_id)
        assert app is not None
        assert app.company == "TestCo"
        assert app.job_title == "Dev"

    def test_default_status_is_draft(self):
        app_id = _save()
        app = tracker.get_application(app_id)
        assert app.status == "Draft"

    def test_jd_snippet_truncated_to_500_chars(self):
        long_jd = "x" * 1000
        app_id = _save(jd=long_jd)
        app = tracker.get_application(app_id)
        assert len(app.jd_snippet) == 500


class TestGetAllApplications:
    def test_returns_empty_list_when_no_records(self):
        assert tracker.get_all_applications() == []

    def test_returns_all_saved_records(self):
        _save(company="A")
        _save(company="B")
        apps = tracker.get_all_applications()
        assert len(apps) == 2

    def test_ordered_most_recent_first(self):
        id1 = _save(company="First")
        id2 = _save(company="Second")
        apps = tracker.get_all_applications()
        assert apps[0].id == id2
        assert apps[1].id == id1


class TestUpdateStatus:
    def test_updates_status_successfully(self):
        app_id = _save()
        tracker.update_status(app_id, "Applied")
        app = tracker.get_application(app_id)
        assert app.status == "Applied"

    def test_raises_for_nonexistent_id(self):
        with pytest.raises(ValueError, match="not found"):
            tracker.update_status(9999, "Applied")


class TestDeleteApplication:
    def test_deletes_existing_record(self):
        app_id = _save()
        tracker.delete_application(app_id)
        assert tracker.get_application(app_id) is None

    def test_raises_for_nonexistent_id(self):
        with pytest.raises(ValueError, match="not found"):
            tracker.delete_application(9999)
