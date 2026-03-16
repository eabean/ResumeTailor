"""
Tests for tailor.py — OpenAI API integration.

Covers:
  [A] Happy path: tailor() returns TailorResult with both .tex sources
  [I] Malformed response: missing XML tags raises ValueError
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.tailor import TailorResult, _extract_tag, build_context, tailor

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_resume():
    return (FIXTURES / "sample_resume.tex").read_text(encoding="utf-8")


@pytest.fixture
def sample_jd():
    return (FIXTURES / "sample_jd.txt").read_text(encoding="utf-8")


@pytest.fixture
def sample_profile():
    return {
        "name": "Jane Doe",
        "email": "jane@email.com",
        "skills": ["Python", "SQL", "Flask"],
        "summary": "Backend developer with 2 years experience.",
    }


@pytest.fixture
def mock_response_text():
    data = json.loads((FIXTURES / "mock_response.json").read_text())
    return (
        f"<resume_tex>\n{data['resume_tex']}\n</resume_tex>\n"
        f"<cover_letter_tex>\n{data['cover_letter_tex']}\n</cover_letter_tex>"
    )


def _make_openai_response(content: str) -> MagicMock:
    """Build a minimal OpenAI chat completion response mock."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


class TestExtractTag:
    def test_extracts_content_between_tags(self):
        text = "<resume_tex>\nhello world\n</resume_tex>"
        assert _extract_tag(text, "resume_tex") == "hello world"

    def test_raises_on_missing_tag(self):
        with pytest.raises(ValueError, match="missing <resume_tex>"):
            _extract_tag("no tags here", "resume_tex")

    def test_handles_multiline_content(self):
        text = "<resume_tex>\nline1\nline2\nline3\n</resume_tex>"
        result = _extract_tag(text, "resume_tex")
        assert "line1" in result
        assert "line3" in result


class TestBuildContext:
    def test_includes_all_three_sections(self, sample_resume, sample_jd, sample_profile):
        ctx = build_context(sample_resume, sample_jd, sample_profile)
        assert "APPLICANT PROFILE" in ctx
        assert "JOB DESCRIPTION" in ctx
        assert "BASE RESUME" in ctx

    def test_profile_is_json_serialised(self, sample_resume, sample_jd, sample_profile):
        ctx = build_context(sample_resume, sample_jd, sample_profile)
        assert "Jane Doe" in ctx


class TestTailor:
    def test_happy_path_returns_tailor_result(
        self, sample_resume, sample_jd, sample_profile, mock_response_text
    ):
        mock_response = _make_openai_response(mock_response_text)

        with patch("app.tailor.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_response
            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
                result = tailor(sample_resume, sample_jd, sample_profile)

        assert isinstance(result, TailorResult)
        assert "\\documentclass" in result.resume_tex
        assert "\\documentclass" in result.cover_letter_tex

    def test_malformed_response_raises_value_error(
        self, sample_resume, sample_jd, sample_profile
    ):
        mock_response = _make_openai_response("Here is your resume but without any XML tags.")

        with patch("app.tailor.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_response
            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
                with pytest.raises(ValueError, match="missing <resume_tex>"):
                    tailor(sample_resume, sample_jd, sample_profile)

    def test_missing_api_key_raises_environment_error(
        self, sample_resume, sample_jd, sample_profile
    ):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
                tailor(sample_resume, sample_jd, sample_profile)
