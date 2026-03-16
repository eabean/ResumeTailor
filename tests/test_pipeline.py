"""
Tests for pipeline.py — full orchestration.

Covers:
  [F] Happy path: run_pipeline returns a PipelineResult
  [G] Retry: compile fails once, Claude fixes it, second attempt succeeds
  [H] Hard fail: compile fails 3 times, LatexCompileError propagates
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.latex import LatexCompileError
from app.pipeline import MAX_COMPILE_RETRIES, PipelineResult, _compile_with_retry, run_pipeline

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_resume():
    return (FIXTURES / "sample_resume.tex").read_text(encoding="utf-8")


@pytest.fixture
def sample_jd():
    return (FIXTURES / "sample_jd.txt").read_text(encoding="utf-8")


@pytest.fixture
def sample_profile():
    return {"name": "Jane Doe", "skills": ["Python", "SQL"]}


@pytest.fixture
def mock_tailor_result():
    data = json.loads((FIXTURES / "mock_response.json").read_text())
    from app.tailor import TailorResult
    return TailorResult(
        resume_tex=data["resume_tex"],
        cover_letter_tex=data["cover_letter_tex"],
    )


class TestCompileWithRetry:
    def test_returns_pdf_on_first_success(self):
        fake_pdf = b"%PDF fake"
        with patch("app.pipeline.latex.compile", return_value=fake_pdf):
            result = _compile_with_retry("some tex", tag="resume_tex")
        assert result == fake_pdf

    def test_retries_after_failure_and_succeeds(self):
        fake_pdf = b"%PDF fake"
        fixed_tex = "\\documentclass{article}\\begin{document}fixed\\end{document}"

        compile_calls = [LatexCompileError("fail", "error log"), fake_pdf]
        compile_side_effects = iter(compile_calls)

        def compile_side_effect(tex):
            val = next(compile_side_effects)
            if isinstance(val, Exception):
                raise val
            return val

        with patch("app.pipeline.latex.compile", side_effect=compile_side_effect), \
             patch("app.pipeline.tailor.fix_latex", return_value=fixed_tex):
            result = _compile_with_retry("broken tex", tag="resume_tex")

        assert result == fake_pdf

    def test_raises_after_max_retries_exhausted(self):
        with patch("app.pipeline.latex.compile", side_effect=LatexCompileError("fail", "err")), \
             patch("app.pipeline.tailor.fix_latex", return_value="still broken"):
            with pytest.raises(LatexCompileError):
                _compile_with_retry("broken tex", tag="resume_tex")

    def test_fix_latex_called_correct_number_of_times(self):
        fix_mock = MagicMock(return_value="still broken")
        with patch("app.pipeline.latex.compile", side_effect=LatexCompileError("fail", "err")), \
             patch("app.pipeline.tailor.fix_latex", fix_mock):
            with pytest.raises(LatexCompileError):
                _compile_with_retry("broken", tag="resume_tex")

        # fix_latex called MAX_COMPILE_RETRIES - 1 times (not on last attempt)
        assert fix_mock.call_count == MAX_COMPILE_RETRIES - 1


class TestRunPipeline:
    def test_happy_path_returns_pipeline_result(
        self, sample_resume, sample_jd, sample_profile, mock_tailor_result
    ):
        fake_pdf = b"%PDF fake"

        with patch("app.pipeline.tailor.tailor", return_value=mock_tailor_result), \
             patch("app.pipeline.latex.compile", return_value=fake_pdf), \
             patch("app.pipeline.tracker.save_application", return_value=1):
            result = run_pipeline(sample_resume, sample_jd, sample_profile, "Acme", "Engineer")

        assert isinstance(result, PipelineResult)
        assert result.resume_pdf == fake_pdf
        assert result.cover_pdf == fake_pdf
        assert result.application_id == 1
        assert isinstance(result.diff_lines, list)

    def test_diff_generated_between_base_and_tailored(
        self, sample_resume, sample_jd, sample_profile, mock_tailor_result
    ):
        with patch("app.pipeline.tailor.tailor", return_value=mock_tailor_result), \
             patch("app.pipeline.latex.compile", return_value=b"%PDF"), \
             patch("app.pipeline.tracker.save_application", return_value=1):
            result = run_pipeline(sample_resume, sample_jd, sample_profile, "Acme", "Engineer")

        # tailored tex differs from sample_resume, so diff should have changes
        from app.diff import has_changes
        assert has_changes(result.diff_lines)

    def test_propagates_tailor_value_error(
        self, sample_resume, sample_jd, sample_profile
    ):
        with patch("app.pipeline.tailor.tailor", side_effect=ValueError("bad response")):
            with pytest.raises(ValueError, match="bad response"):
                run_pipeline(sample_resume, sample_jd, sample_profile, "Acme", "Engineer")
