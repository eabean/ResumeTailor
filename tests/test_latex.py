"""
Tests for latex.py — tectonic compilation.

Covers:
  [B] Happy path: compile() returns PDF bytes
  [G] Retry: tectonic fails once, then succeeds (tested via pipeline)
  [H] Hard fail: tectonic fails, LatexCompileError raised with error_log
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# Patch tectonic check at import time so tests don't require tectonic installed
with patch("shutil.which", return_value="/usr/local/bin/tectonic"):
    from app.latex import LatexCompileError, compile


@pytest.fixture
def sample_tex():
    return (FIXTURES / "sample_resume.tex").read_text(encoding="utf-8")


@pytest.fixture
def minimal_valid_tex():
    return r"\documentclass{article}\begin{document}Hello world\end{document}"


class TestCompile:
    def test_returns_pdf_bytes_on_success(self, minimal_valid_tex):
        fake_pdf = b"%PDF-1.4 fake content"

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("app.latex.subprocess.run", return_value=mock_result), \
             patch("app.latex.Path.exists", return_value=True), \
             patch("app.latex.Path.read_bytes", return_value=fake_pdf):
            result = compile(minimal_valid_tex)

        assert result == fake_pdf

    def test_raises_on_nonzero_exit(self, minimal_valid_tex):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "! Undefined control sequence."
        mock_result.stdout = ""

        with patch("app.latex.subprocess.run", return_value=mock_result):
            with pytest.raises(LatexCompileError) as exc_info:
                compile(minimal_valid_tex)

        assert "Undefined control sequence" in exc_info.value.error_log

    def test_raises_when_pdf_not_produced(self, minimal_valid_tex):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("app.latex.subprocess.run", return_value=mock_result), \
             patch("app.latex.Path.exists", return_value=False):
            with pytest.raises(LatexCompileError, match="no PDF was produced"):
                compile(minimal_valid_tex)

    def test_error_log_preserved_on_failure(self, minimal_valid_tex):
        error_text = "LaTeX Error: File 'missing.sty' not found."
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = error_text
        mock_result.stdout = ""

        with patch("app.latex.subprocess.run", return_value=mock_result):
            with pytest.raises(LatexCompileError) as exc_info:
                compile(minimal_valid_tex)

        assert exc_info.value.error_log == error_text
