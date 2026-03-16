"""
OpenAI API integration — resume tailoring and cover letter generation.

Single combined call returns both outputs to minimize latency and API cost.

Data flow:
  base_tex + job_desc + profile
        │
        ▼
  build_context()  ← formats all inputs into a single user message
        │
        ▼
  OpenAI API call  ← one call, structured XML response
        │
        ▼
  _extract_tag()   ← parses <resume_tex> and <cover_letter_tex> from response
        │
        ▼
  TailorResult(resume_tex, cover_letter_tex)
"""

import json
import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "gpt-4o"

SYSTEM_PROMPT = """\
You are an expert resume writer and LaTeX typesetter.

Your task:
- Rewrite the resume experience bullets and summary to better match the job description
- Emphasize skills and experiences from the base resume that are most relevant to this role
- CRITICAL: Use ONLY facts, skills, and experiences present in the base resume and applicant profile
- CRITICAL: Do NOT invent, embellish, or add credentials, skills, or experiences not present in the inputs
- Keep all LaTeX syntax valid and fully compilable
- Keep the overall structure and formatting of the base resume intact
- Adapt the base cover letter to target the specific company and role, updating only the relevant details

Return your response in exactly this format, with no text outside the XML tags:

<resume_tex>
[full tailored LaTeX resume source]
</resume_tex>

<cover_letter_tex>
[full LaTeX cover letter source]
</cover_letter_tex>
"""

FIX_LATEX_PROMPT = """\
The following LaTeX document failed to compile. Fix the LaTeX syntax errors so it compiles correctly.

Compilation error:
{error_log}

Broken LaTeX:
{broken_tex}

Return only the corrected LaTeX inside the same XML tag as the input — either <resume_tex> or <cover_letter_tex>.
Do not change any content, only fix the syntax errors.
"""


@dataclass
class TailorResult:
    resume_tex: str
    cover_letter_tex: str


def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not set. Copy .env.example to .env and add your key."
        )
    return OpenAI(api_key=api_key)


def _extract_tag(text: str, tag: str) -> str:
    """Extract content from an XML-style tag in the model's response."""
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise ValueError(
            f"Response is missing <{tag}> tag. "
            f"Response received:\n{text[:500]}..."
        )
    return match.group(1).strip()


def build_context(base_tex: str, base_cover_tex: str, job_desc: str, profile: dict) -> str:
    """Format all inputs into a single context string for the prompt."""
    return (
        f"=== APPLICANT PROFILE ===\n{json.dumps(profile, indent=2)}\n\n"
        f"=== JOB DESCRIPTION ===\n{job_desc.strip()}\n\n"
        f"=== BASE RESUME (LaTeX) ===\n{base_tex.strip()}\n\n"
        f"=== BASE COVER LETTER (LaTeX) ===\n{base_cover_tex.strip()}"
    )


def tailor(base_tex: str, base_cover_tex: str, job_desc: str, profile: dict) -> TailorResult:
    """
    Call the OpenAI API to produce a tailored resume and cover letter.
    Returns a TailorResult with both .tex sources.
    Raises ValueError if the response is malformed.
    """
    client = _get_client()
    context = build_context(base_tex, base_cover_tex, job_desc, profile)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=8096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
    )

    response_text = response.choices[0].message.content
    resume_tex = _extract_tag(response_text, "resume_tex")
    cover_letter_tex = _extract_tag(response_text, "cover_letter_tex")

    return TailorResult(resume_tex=resume_tex, cover_letter_tex=cover_letter_tex)


def fix_latex(broken_tex: str, error_log: str, tag: str = "resume_tex") -> str:
    """
    Ask the model to fix a LaTeX compilation error.
    Used by pipeline.py in the retry loop.
    Returns the corrected LaTeX source.
    """
    client = _get_client()
    prompt = FIX_LATEX_PROMPT.format(error_log=error_log, broken_tex=broken_tex)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=8096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.choices[0].message.content
    return _extract_tag(response_text, tag)
