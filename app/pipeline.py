"""
Pipeline orchestration — ties together tailor, latex, diff, and tracker.

Full pipeline flow:
  base_tex + job_desc + profile + company + job_title
        │
        ▼
  tailor.tailor()         ← Claude API: produces tailored_tex + cover_tex
        │
        ├──▶ compile_with_retry(tailored_tex, tag="resume_tex")
        │           │
        │           ├── success ──▶ resume_pdf (bytes)
        │           └── failure ──▶ fix via Claude, retry up to 3x
        │
        ├──▶ compile_with_retry(cover_tex, tag="cover_letter_tex")
        │           └── resume_pdf + cover_pdf (bytes)
        │
        ├──▶ diff.generate_diff(base_tex, tailored_tex)
        │
        └──▶ tracker.save_application()
                    └── PipelineResult returned to UI
"""

from dataclasses import dataclass

from app import diff as diff_module
from app import latex, tailor, tracker
from app.diff import DiffLine
from app.latex import LatexCompileError

MAX_COMPILE_RETRIES = 3


@dataclass
class PipelineResult:
    resume_pdf: bytes
    cover_pdf: bytes
    resume_tex: str
    cover_letter_tex: str
    diff_lines: list[DiffLine]
    application_id: int


def _compile_with_retry(tex: str, tag: str) -> bytes:
    """
    Attempt to compile tex to PDF. On failure, ask Claude to fix the LaTeX
    and retry. Raises LatexCompileError if all retries are exhausted.

    Retry state machine:
      attempt 1 ──▶ compile ──▶ success ──▶ return PDF
                                  │
                                  └── fail ──▶ fix_latex ──▶ attempt 2
                                                               │
                                                               └── fail ──▶ fix_latex ──▶ attempt 3
                                                                                             │
                                                                                             └── fail ──▶ raise
    """
    current_tex = tex
    last_error: LatexCompileError | None = None

    for attempt in range(MAX_COMPILE_RETRIES):
        try:
            return latex.compile(current_tex)
        except LatexCompileError as e:
            last_error = e
            if attempt < MAX_COMPILE_RETRIES - 1:
                current_tex = tailor.fix_latex(current_tex, e.error_log, tag=tag)

    raise last_error


def run_pipeline(
    base_tex: str,
    base_cover_tex: str,
    job_desc: str,
    profile: dict,
    company: str,
    job_title: str,
) -> PipelineResult:
    """
    Run the full tailoring pipeline.

    Args:
        base_tex:       The user's master LaTeX resume source.
        base_cover_tex: The user's master LaTeX cover letter source.
        job_desc:       The job description text.
        profile:        The applicant profile dict from applicant_profile.json.
        company:        Company name (for the tracker record).
        job_title:      Job title (for the tracker record).

    Returns:
        PipelineResult with PDFs, .tex sources, diff, and application ID.

    Raises:
        ValueError:         If Claude returns a malformed response.
        LatexCompileError:  If PDF compilation fails after all retries.
        EnvironmentError:   If ANTHROPIC_API_KEY is missing.
    """
    tailor_result = tailor.tailor(base_tex, base_cover_tex, job_desc, profile)

    resume_pdf = _compile_with_retry(tailor_result.resume_tex, tag="resume_tex")
    cover_pdf = _compile_with_retry(tailor_result.cover_letter_tex, tag="cover_letter_tex")

    diff_lines = diff_module.generate_diff(base_tex, tailor_result.resume_tex)

    app_id = tracker.save_application(
        company=company,
        job_title=job_title,
        job_description=job_desc,
        resume_tex=tailor_result.resume_tex,
        cover_letter_tex=tailor_result.cover_letter_tex,
    )

    return PipelineResult(
        resume_pdf=resume_pdf,
        cover_pdf=cover_pdf,
        resume_tex=tailor_result.resume_tex,
        cover_letter_tex=tailor_result.cover_letter_tex,
        diff_lines=diff_lines,
        application_id=app_id,
    )
