"""
LaTeX compilation via tectonic.

Compiles a .tex string to PDF bytes using a temp directory.
Raises LatexCompileError on failure — the retry loop lives in pipeline.py.

Startup check:
  On import, verifies tectonic is installed and raises a clear error if not.

Compile flow:
  tex_string
      │
      ▼
  write to temp dir
      │
      ▼
  tectonic <file.tex>  (subprocess)
      │
      ├── success ──▶ return PDF bytes
      │
      └── failure ──▶ raise LatexCompileError(error_log)
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class LatexCompileError(Exception):
    """Raised when tectonic fails to compile a .tex file."""

    def __init__(self, message: str, error_log: str = ""):
        super().__init__(message)
        self.error_log = error_log


# Windows fallback locations — winget and Scoop don't always update PATH
# for the current process (e.g. when launched from an IDE or Streamlit).
_WINDOWS_FALLBACK_PATHS = [
    Path(os.environ.get("USERPROFILE", "")) / ".bin" / "tectonic.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "tectonic.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / "tectonic" / "tectonic.exe",
    Path(os.environ.get("USERPROFILE", "")) / "scoop" / "shims" / "tectonic.exe",
]


def _find_tectonic() -> str:
    """Return the tectonic executable path, searching fallback locations if needed."""
    found = shutil.which("tectonic")
    if found:
        return found
    for candidate in _WINDOWS_FALLBACK_PATHS:
        if candidate.exists():
            return str(candidate)
    raise EnvironmentError(
        "tectonic is not installed or not on PATH.\n"
        "Install it from: https://tectonic-typesetting.github.io/\n"
        "  Windows: winget install tectonic\n"
        "  macOS:   brew install tectonic\n"
        "  Linux:   cargo install tectonic\n\n"
        "If tectonic is already installed, try restarting your terminal or IDE "
        "so the updated PATH takes effect."
    )


def compile(tex_content: str, filename: str = "document") -> bytes:
    """
    Compile a LaTeX string to PDF.

    Args:
        tex_content: Full LaTeX source as a string.
        filename:    Base name for the temp .tex file (no extension).

    Returns:
        PDF content as bytes.

    Raises:
        LatexCompileError: If tectonic reports a compilation error.
    """
    tectonic = _find_tectonic()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_path = tmp_path / f"{filename}.tex"
        pdf_path = tmp_path / f"{filename}.pdf"

        tex_path.write_text(tex_content, encoding="utf-8")

        result = subprocess.run(
            [tectonic, str(tex_path)],
            capture_output=True,
            text=True,
            cwd=tmp,
        )

        if result.returncode != 0:
            error_log = result.stderr or result.stdout or "Unknown tectonic error"
            raise LatexCompileError(
                f"LaTeX compilation failed (exit {result.returncode})",
                error_log=error_log,
            )

        if not pdf_path.exists():
            raise LatexCompileError(
                "tectonic exited successfully but no PDF was produced.",
                error_log=result.stdout,
            )

        return pdf_path.read_bytes()


def page_count(pdf_bytes: bytes) -> int:
    """Return the number of pages in a PDF using pypdf."""
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)
