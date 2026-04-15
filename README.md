# ResumeTailor

A locally run web-app that uses an LLM to tailor your resume and cover letter to a specific job posting. Paste a job description (or import it from a URL), and the app rewrites your LaTeX resume and cover letter to match — then compiles them to PDF.

## What it does

- **Tailor tab** — paste a job description or import it from a job posting URL. The app calls the OpenAI API to rewrite your resume bullets and cover letter to match the posting, compiles both to PDF, and shows a line-by-line diff of what changed.
- **Profile tab** — view and upload your `applicant_profile.json`, which is the source of truth for all your experience, skills, and contact info.
- **Applications tab** — tracks every tailored application in a local SQLite database. Update statuses (Draft → Applied → Interview → Offer / Rejected) and browse past outputs.

## Prerequisites

### Python
Python 3.10 or later.

### Tectonic (LaTeX compiler)
The app compiles `.tex` files to PDF using [Tectonic](https://tectonic-typesetting.github.io/). Install it before running:

**macOS (Homebrew):**
```bash
brew install tectonic
```

**Linux:**
```bash
curl --proto '=https' --tlsv1.2 -fsSL https://drop.tectonic-typesetting.github.io/install.sh | sh
```

**Windows:**
Download the binary from the [Tectonic releases page](https://github.com/tectonic-typesetting/tectonic/releases) and add it to your PATH.

Verify it works:
```bash
tectonic --version
```

### OpenAI API key
Get one at [platform.openai.com](https://platform.openai.com).

---

## Setup

**1. Clone and enter the repo**
```bash
git clone <repo-url>
cd ResumeTailor
```

**2. Create a virtual environment and install dependencies**
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Add your OpenAI API key**
```bash
cp .env.example .env
```
Open `.env` and replace `sk-your-key-here` with your actual key.

**4. Run the app**
```bash
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Providing your base resume and cover letter

The app ships with sample LaTeX templates in `data/`:

| File | Purpose |
|---|---|
| `data/BaseResume.tex` | Your master resume — the starting point for every tailored version |
| `data/BaseCoverLetter.tex` | Your master cover letter template |
| `data/applicant_profile.json` | All your personal data: contact info, experience, projects, skills, scenarios |

**Replace the sample files with your own.** The templates already in `data/` belong to a fictional candidate (Jordan Park) and are there so the app works out of the box.

### Important: the prompts are tuned to the sample template structure

The AI prompt is written to understand the specific LaTeX structure and commands used in the provided `BaseResume.tex` and `BaseCoverLetter.tex` templates. It knows, for example, that contact info lives in `\huge\scshape\textbf{}` and `\faPhone` commands, that work experience entries use a custom `\entry{}` command, and so on.

**If you substitute a different LaTeX template, you should also update the system prompt in `app/tailor.py`** to reflect the commands and structure in your template — otherwise the AI may write syntactically correct LaTeX that doesn't fit your template's layout.

The safest approach is to edit the provided templates directly (swap out Jordan Park's details) rather than replacing them wholesale.

### applicant_profile.json

This file is what the AI reads to populate your resume. Fill it in with your real details before tailoring. The structure:

```jsonc
{
  "name": "Your Name",
  "phone": "...",
  "email": "...",
  "linkedin": "linkedin.com/in/...",
  "github": "github.com/...",
  "portfolio": "yoursite.dev",        // omit the faBook icon if empty
  "summary": "...",                   // optional

  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "location": "City, Province",
      "duration": "Jan 2022 – Present",
      "bullets": ["Did X resulting in Y", "..."]
    }
  ],

  "projects": [
    { "name": "Project", "tech": "Python, React", "bullets": ["..."] }
  ],

  "education": [
    { "institution": "...", "credential": "B.Sc. Computer Science", "location": "...", "year": "2022" }
  ],

  "skills": {
    "languages": ["Python", "TypeScript"],
    "tools": ["Docker", "PostgreSQL"]
  },

  "certs": ["AWS Solutions Architect"],

  // CARL scenarios used to write cover letter paragraphs
  "scenarios": [
    {
      "context": "...",
      "action": "...",
      "result": "...",
      "relevance": "roles involving backend systems",
      "tech": "Python, FastAPI"
    }
  ]
}
```

You can upload a new `applicant_profile.json` at any time from the **Profile** tab without restarting the app.

---
