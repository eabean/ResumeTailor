"""
Tests for jobfetch.py — generic job posting scraper.

Covers:
  [K] _try_structured: extracts fields from a flat JSON-LD JobPosting
  [L] _try_structured: extracts fields from a @graph JSON block (Built In style)
  [M] _try_structured: returns None when no JobPosting present
  [N] _extract_with_llm: parses OpenAI JSON response into the expected dict
  [O] _extract_with_llm: raises ValueError on empty LLM result
  [P] fetch_job_posting: uses structured path when JobPosting data is present
  [Q] fetch_job_posting: falls back to LLM when no structured data found
  [R] _strip_html: converts HTML to plain text correctly
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.jobfetch import _extract_with_llm, _strip_html, _try_structured, fetch_job_posting


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_page(script_content: str) -> str:
    return f"<html><body><script>{script_content}</script></body></html>"


def _make_llm_response(payload: dict) -> MagicMock:
    message = MagicMock()
    message.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def _make_http_response(body: str, status: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.text = body
    resp.raise_for_status = MagicMock()
    return resp


# ── Fixtures ───────────────────────────────────────────────────────────────────

FLAT_JOB_POSTING = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    "title": "Backend Engineer",
    "hiringOrganization": {"@type": "Organization", "name": "Acme Corp"},
    "description": "<p>We need a <b>Python</b> developer.</p>",
}

GRAPH_JOB_POSTING = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "WebPage", "name": "Job Board"},
        {
            "@type": "JobPosting",
            "title": "Expert Gameplay AI Software Engineer",
            "hiringOrganization": {"@type": "Organization", "name": "2K"},
            "description": "<p>Build AI systems.</p><ul><li>Skill A</li><li>Skill B</li></ul>",
        },
    ],
}


# ── Layer 1: structured extraction ────────────────────────────────────────────

class TestTryStructured:
    def test_extracts_flat_json_ld(self):
        page = _make_page(json.dumps(FLAT_JOB_POSTING))
        result = _try_structured(page)
        assert result is not None
        assert result["company"] == "Acme Corp"
        assert result["job_title"] == "Backend Engineer"
        assert "Python" in result["job_desc"]

    def test_extracts_graph_json_block(self):
        page = _make_page(json.dumps(GRAPH_JOB_POSTING))
        result = _try_structured(page)
        assert result is not None
        assert result["company"] == "2K"
        assert result["job_title"] == "Expert Gameplay AI Software Engineer"
        assert "AI" in result["job_desc"]

    def test_returns_none_when_no_job_posting(self):
        page = _make_page(json.dumps({"@type": "WebPage", "name": "Home"}))
        assert _try_structured(page) is None

    def test_returns_none_when_no_script_tags(self):
        assert _try_structured("<html><body>No scripts here.</body></html>") is None

    def test_returns_none_on_malformed_json(self):
        page = _make_page("{ this is not valid json }")
        assert _try_structured(page) is None

    def test_returns_none_when_description_missing(self):
        data = {**FLAT_JOB_POSTING, "description": ""}
        page = _make_page(json.dumps(data))
        assert _try_structured(page) is None


# ── Layer 2: LLM extraction ───────────────────────────────────────────────────

class TestExtractWithLlm:
    def test_returns_parsed_fields(self):
        payload = {"company": "Globex", "job_title": "Dev", "job_desc": "Build things."}
        mock_response = _make_llm_response(payload)

        with patch("app.jobfetch.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_response
            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
                result = _extract_with_llm("<html>some page</html>", "https://example.com/job/1")

        assert result["company"] == "Globex"
        assert result["job_title"] == "Dev"
        assert result["job_desc"] == "Build things."

    def test_raises_value_error_when_all_fields_empty(self):
        payload = {"company": "", "job_title": "", "job_desc": ""}
        mock_response = _make_llm_response(payload)

        with patch("app.jobfetch.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_response
            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
                with pytest.raises(ValueError, match="Could not extract"):
                    _extract_with_llm("<html></html>", "https://example.com/job/1")


# ── fetch_job_posting integration ─────────────────────────────────────────────

class TestFetchJobPosting:
    def test_uses_structured_path_when_available(self):
        page_html = _make_page(json.dumps(FLAT_JOB_POSTING))
        mock_resp = _make_http_response(page_html)

        with patch("app.jobfetch.httpx.get", return_value=mock_resp):
            result = fetch_job_posting("https://example.com/job/123")

        assert result["company"] == "Acme Corp"
        assert result["job_title"] == "Backend Engineer"

    def test_falls_back_to_llm_when_no_structured_data(self):
        plain_page = "<html><body><h1>Senior Dev at Initech</h1><p>You will code.</p></body></html>"
        mock_resp = _make_http_response(plain_page)
        llm_payload = {"company": "Initech", "job_title": "Senior Dev", "job_desc": "You will code."}
        mock_llm = _make_llm_response(llm_payload)

        with patch("app.jobfetch.httpx.get", return_value=mock_resp), \
             patch("app.jobfetch.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_llm
            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
                result = fetch_job_posting("https://example.com/job/456")

        assert result["company"] == "Initech"
        assert result["job_title"] == "Senior Dev"

    def test_raises_on_http_error(self):
        with patch("app.jobfetch.httpx.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            with pytest.raises(httpx.HTTPStatusError):
                fetch_job_posting("https://example.com/job/404")


# ── _strip_html ────────────────────────────────────────────────────────────────

class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_converts_br_to_newline(self):
        result = _strip_html("line one<br>line two")
        assert "line one" in result
        assert "line two" in result
        assert "\n" in result

    def test_decodes_html_entities(self):
        assert "&amp;" not in _strip_html("AT&amp;T")
        assert "AT&T" in _strip_html("AT&amp;T")

    def test_collapses_excess_blank_lines(self):
        result = _strip_html("<p>A</p>\n\n\n\n<p>B</p>")
        assert "\n\n\n" not in result
