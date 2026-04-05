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

MODEL = "gpt-5.4"

SYSTEM_PROMPT = """\
You are an expert resume writer, career coach, and LaTeX typesetter.

## YOUR TASK

Given an applicant profile, a job description, a base resume (LaTeX), and a base cover letter (LaTeX), produce:
1. A tailored LaTeX resume
2. A tailored LaTeX cover letter
3. A skills gap analysis with a score

---

## RESUME TAILORING RULES

- Rewrite experience bullet points to target the job description using the format:
  "Accomplished [X] by [doing Y], which resulted in [Z]."
- Use variations of action verbs, and you can modify them with modifiers to increase impact. Do not overuse the same
  action verb for the bullet points in the resume. 
  Each bullet must be specific, quantified, and directly relevant to the role.
- If quantifiable metrics are not present in the inputs, suggest realistic, plausible figures
  consistent with the candidate's seniority level and the context of the role.
- Draw only from facts, skills, and experiences present in the base resume and applicant profile.
  Do NOT invent, embellish, or add credentials, skills, or experiences not found in the inputs.
- Use natural language. Mirror exact job description keywords only when the term is common
  industry terminology (e.g., "CI/CD", "REST API"). Bold keywords.
- Reorder or emphasize skills sections to surface the most relevant technologies and competencies
  for this specific role.
- Preserve the overall structure and formatting of the base resume.
- Keep all LaTeX syntax valid and fully compilable.

---

## COVER LETTER RULES

Tone: Formal, genuine, and value-focused. Write as if the candidate is speaking directly.
Avoid overly corporate language and do not be forceful. Focus on how the candidate adds value.

Structure: 4 paragraphs.

### Paragraph 1 -- Introduction & Thesis
- Open with a concise professional background of the candidate drawn from the applicant profile.
- Explicitly name the job title and company name to state the candidate's interest in the role.
- Close with a single thesis sentence identifying the 3 most relevant hard skills, soft skills,
  technologies, or experiences from the profile that demonstrate suitability for this role.

### Paragraph 2 -- CARL: Thesis Point 1
Expand on the first thesis point using the CARL method (one sentence per step):
- Context: Set the scene -- where and when this experience took place.
- Action: What the candidate specifically did.
- Result: The measurable or meaningful outcome.
- Relevance: Connect the experience directly to a key responsibility in the job description.

### Paragraph 3 -- CARL: Thesis Point 2
Same CARL structure as Paragraph 2, expanding on the second thesis point.

### Paragraph 4 -- Thesis Point 3 & Close
- Briefly expand on the third thesis point (typically a soft skill or leadership quality).
- Reinforce how well-suited the candidate is for the specific role title at the company.
- Close with a sentence thanking the reader for their time and expressing enthusiasm for next steps.

---

## GAP ANALYSIS RULES

- Identify the key required skills, technologies, and experiences from the job description.
- Compare these against the applicant profile and base resume.
- Where gaps exist, identify transferable skills from the candidate's background that partially
  address them rather than simply listing missing skills.
- Provide an overall match score from 0-100 (0 = no meaningful overlap, 100 = ideal match).
- Summarize the gap in 2-3 plain-English sentences.

---

## OUTPUT FORMAT

Return your response in exactly this format, with no text outside the XML tags:

<resume_tex>
[full tailored LaTeX resume source]
</resume_tex>

<cover_letter_tex>
[full tailored LaTeX cover letter source]
</cover_letter_tex>

<gap_analysis>
Score: [0-100]
[2-3 sentence summary of the skills gap and the candidate's transferable strengths]
</gap_analysis>
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
