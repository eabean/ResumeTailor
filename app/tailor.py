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

Given a structured applicant profile (JSON), a job description, a base resume (LaTeX), and a base cover letter (LaTeX), produce:
1. A tailored LaTeX resume -- fully populated from the profile and optimized for the job description
2. A tailored LaTeX cover letter -- structured using CARL narratives from the profile
3. A skills gap analysis with a score

---

## RESUME GENERATION -- FIELD-BY-FIELD MAPPING

Map every field from the applicant JSON profile into the LaTeX template exactly as specified below.
Do not skip or omit any populated field.

### Contact Header
The contact header (name, phone, email, LinkedIn, GitHub, portfolio) is pre-populated
before this prompt is called. Do not modify any contact details.

### Work Experience Section
For each object in `experience[]`, in the order provided:
- `company`  -> first argument of `\\entry{}`
- `duration` -> second argument of `\\entry{}`
- `title`    -> first argument of `\\subentry{}`
- `location` -> second argument of `\\subentry{}`
- Each string in `bullets[]` -> one `\\item` inside `\\begin{itemize}...\\end{itemize}`

**Bullet rewriting rules (apply to every bullet):**
- Rewrite using the XYZ format: "Accomplished [X] by [doing Y], resulting in [Z]."
- Wrap job-description keywords that match the bullet's skill or domain in `\\textbf{}`.
- If a bullet lacks a quantifiable metric, inject a realistic figure consistent with the
  candidate's seniority and the company's apparent scale.
- Reorder bullets within each role so the most job-relevant bullet appears first.
- Vary action verbs across all bullets; never open two bullets with the same verb.
- Do not end bullet points with a period.
- If a role has fewer than 3 bullets, synthesize additional plausible bullets grounded
  in the role title, company context, and duration.

### Projects Section
For each object in `projects[]`, in the order provided:
- `name` -> first argument of `\\project{}`
- `tech` -> second argument of `\\project{}`
- Each string in `bullets[]` -> one `\\item`, rewritten with the same bullet rules above.
- Include exactly 2 bullets per project. If the profile has more than 2, keep only the 2 most job-relevant. If fewer than 2, synthesize additional plausible bullets.
- Reorder projects so the most job-relevant project appears first.

### Education Section
For each object in `education[]`:
- `institution` -> first argument of `\\entry{}`
- `year`        -> second argument of `\\entry{}`
- `credential`  -> first argument of `\\subentry{}`
- `location`    -> second argument of `\\subentry{}`

### Technical Skills Section
- `skills.languages` -> populate the `\\textbf{Languages}:` line (comma-separated)
- `skills.tools`     -> populate the `\\textbf{Technology \\& Tools}:` line (comma-separated)
- Reorder items within each list so technologies that appear in the job description come first.
- Do not add skills not present in the profile.

### Certificates & Awards Section
- `certs[]` -> a single `\\item` with entries comma-separated.
- If `certs` is empty, omit the entire section.

---

## RESUME TAILORING RULES

- Always preserve the order of `experience[]` exactly as provided — do not reorder roles. The most recent role must appear first.
- Draw only from `experience[]`, `projects[]`, `education[]`, `skills`, and `certs` in the
  applicant profile. Do NOT use `scenarios[]` for resume content.
- Do NOT invent, embellish, or add credentials, roles, or skills not found in the inputs.
- Use natural language. Mirror exact job description keywords only when the term is common
  industry terminology (e.g., "CI/CD", "REST API"). Bold matched keywords.
- Preserve the overall LaTeX structure, section order, and custom commands
  (`\\entry`, `\\subentry`, `\\project`) from the base resume.
- Keep all LaTeX syntax valid and fully compilable.

---

## COVER LETTER RULES

Tone: Formal, genuine, and value-focused. Write as if the candidate is speaking directly.
Avoid overly corporate language and do not be forceful. Focus on how the candidate adds value.

Structure: 4 paragraphs.

### Paragraph 1 -- Introduction & Thesis
- Open by introducing the candidate in their own voice, drawn directly from the `summary` field
  in the applicant profile. Use it as the basis for a natural first sentence that grounds who they
  are — their role, years of experience, and domain (e.g. "I am a backend engineer with four years
  of experience in financial services..."). If `summary` is empty, derive an equivalent introduction
  from the experience and profile data.
- Explicitly name the job title and company name to state the candidate's interest in the role.
- Close with a single thesis sentence identifying the 3 most relevant hard skills, soft skills,
  technologies, or experiences from the profile that demonstrate suitability for this role.

### Paragraphs 2 & 3 -- CARL Narratives
The `scenarios[]` array contains the candidate's pre-authored CARL stories. Each entry has:
- `context`:   the setting and circumstances
- `action`:    what the candidate specifically did
- `result`:    the measurable or meaningful outcome
- `relevance`: how it connects to a job requirement
- `tech`:      technologies involved

**Selection:** From all provided scenarios, select the two whose `relevance` and `tech`
best match the key responsibilities and required skills in the job description.
Use them for Paragraphs 2 and 3 respectively.

**Writing each paragraph:** Render the chosen scenario as four flowing sentences -- one per
CARL step -- woven into natural prose. Do not use bullet points or headers inside the paragraph.
The `relevance` sentence must explicitly connect to a named responsibility or requirement
from the job description.

### Paragraph 4 -- Thesis Point 3 & Close
- Briefly expand on the third thesis point (typically a soft skill or leadership quality).
- Reinforce how well-suited the candidate is for the specific role title at the company.
- Close with a sentence thanking the reader for their time and expressing enthusiasm for next steps, 
and to contact them at the email provided.

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

TRIM_PROMPT = """\
The following LaTeX resume compiled to more than one page. Trim it to fit exactly one page.

Rules:
- Start by removing the least job-relevant bullet points from the Work Experience section first.
  Work through each role and drop its weakest bullet before moving to the next role.
  Only after reducing all roles to a minimum of 2 bullets should you consider removing bullets elsewhere.
- Do not touch the Projects, Education, or Technical Skills sections unless absolutely necessary.
- Never remove a role entirely.
- Do not change any LaTeX structure, commands, or formatting — only reduce content.
- Keep all LaTeX syntax valid and fully compilable.

LaTeX source:
{resume_tex}

Return only the trimmed LaTeX inside <resume_tex> tags.
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
    resume_tex: str | None
    cover_letter_tex: str | None


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


def tailor(
    base_tex: str,
    base_cover_tex: str,
    job_desc: str,
    profile: dict,
    company: str = "",
    tailor_resume: bool = True,
    tailor_cover: bool = True,
) -> TailorResult:
    """
    Call the OpenAI API to produce a tailored resume and/or cover letter.
    Returns a TailorResult; fields are None if that document was not requested.
    """
    client = _get_client()
    context = build_context(base_tex, base_cover_tex, job_desc, profile)

    # Tell the model which documents to produce
    scope_note = ""
    if tailor_resume and not tailor_cover:
        scope_note = "\n\nIMPORTANT: Only produce the <resume_tex> output. Do not produce <cover_letter_tex> or <gap_analysis>."
    elif tailor_cover and not tailor_resume:
        scope_note = "\n\nIMPORTANT: Only produce the <cover_letter_tex> output. Do not produce <resume_tex> or <gap_analysis>."

    response = client.chat.completions.create(
        model=MODEL,
        max_completion_tokens=8096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context + scope_note},
        ],
    )

    response_text = response.choices[0].message.content
    resume_tex = _extract_tag(response_text, "resume_tex") if tailor_resume else None
    cover_letter_tex = _extract_tag(response_text, "cover_letter_tex") if tailor_cover else None

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
        max_completion_tokens=8096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.choices[0].message.content
    return _extract_tag(response_text, tag)


def trim_to_one_page(resume_tex: str) -> str:
    """Ask the model to trim a resume LaTeX source until it fits one page."""
    client = _get_client()
    prompt = TRIM_PROMPT.format(resume_tex=resume_tex)

    response = client.chat.completions.create(
        model=MODEL,
        max_completion_tokens=8096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.choices[0].message.content
    return _extract_tag(response_text, "resume_tex")
