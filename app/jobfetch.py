"""
Generic job posting scraper.

Two-layer extraction strategy:
  1. Structured data  — parses schema.org JobPosting JSON embedded in the page
                        (works on Built In, Indeed, Greenhouse, Lever, and many others)
  2. LLM fallback     — strips the page to plain text and asks OpenAI to extract
                        the three fields; works on any job posting page
"""

import html
import json
import os
import re

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Characters of plain text sent to the LLM — enough to cover any full JD
_LLM_CHAR_LIMIT = 12_000


def fetch_job_posting(url: str) -> dict:
    """
    Fetch job details from any job posting URL.

    Returns a dict with keys: company, job_title, job_desc.
    Raises ValueError if details cannot be extracted.
    """
    resp = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=15)
    resp.raise_for_status()
    page = resp.text

    result = _try_structured(page)
    if result:
        return result

    return _extract_with_llm(page, url)


# ── Layer 1: structured JSON extraction ───────────────────────────────────────

def _try_structured(page: str) -> dict | None:
    """
    Look for a schema.org JobPosting block in any inline <script> tag.
    Handles both flat JSON-LD objects and @graph arrays.
    Returns the extracted dict or None if not found.
    """
    for script_text in re.findall(r"<script[^>]*>(.*?)</script>", page, re.DOTALL):
        if "JobPosting" not in script_text:
            continue
        try:
            data = json.loads(script_text.strip())
        except json.JSONDecodeError:
            continue

        job = _find_job_posting(data)
        if job is None:
            continue

        title = (job.get("title") or "").strip()
        org = job.get("hiringOrganization") or {}
        company = (org.get("name") if isinstance(org, dict) else str(org)).strip()
        desc = _strip_html(job.get("description") or "")

        if title and company and desc:
            return {"company": company, "job_title": title, "job_desc": desc}

    return None


def _find_job_posting(data) -> dict | None:
    """Recursively find a JobPosting object inside parsed JSON."""
    if isinstance(data, dict):
        if data.get("@type") == "JobPosting":
            return data
        # @graph array
        for item in data.get("@graph") or []:
            result = _find_job_posting(item)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_job_posting(item)
            if result:
                return result
    return None


# ── Layer 2: LLM extraction ───────────────────────────────────────────────────

def _extract_with_llm(page: str, url: str) -> dict:
    """
    Strip the page to plain text and ask OpenAI to extract the job fields.
    Raises ValueError if the response cannot be parsed.
    """
    plain = _strip_html(page)[:_LLM_CHAR_LIMIT]

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract structured job posting data from raw page text. "
                    "Reply ONLY with a JSON object using exactly these keys: "
                    "company, job_title, job_desc. "
                    "job_desc should be the complete job description as plain text. "
                    "If a field cannot be determined, use an empty string."
                ),
            },
            {
                "role": "user",
                "content": f"URL: {url}\n\n{plain}",
            },
        ],
        response_format={"type": "json_object"},
    )

    try:
        result = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, IndexError, AttributeError) as exc:
        raise ValueError(f"LLM returned unparseable response: {exc}") from exc

    company = (result.get("company") or "").strip()
    job_title = (result.get("job_title") or "").strip()
    job_desc = (result.get("job_desc") or "").strip()

    if not (company or job_title or job_desc):
        raise ValueError(
            "Could not extract job details from this page. "
            "Try copying the job description manually."
        )

    return {"company": company, "job_title": job_title, "job_desc": job_desc}


# ── HTML utilities ─────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Convert an HTML fragment to readable plain text."""
    text = html.unescape(text)
    text = re.sub(
        r"<(?:br\s*/?\s*|/p|/li|/div|/h[1-6]|/tr|/td)>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
