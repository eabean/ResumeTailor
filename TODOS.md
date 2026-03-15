# TODOS

## P2 — Job Board API Integration
**What:** Fetch relevant job postings automatically by keyword/location via free APIs (Adzuna, Remotive) instead of pasting JDs manually.
**Why:** Completes the original "morning workflow" vision — wake up, postings are waiting, resumes pre-generated.
**Pros:** No scraping / ToS risk since these have free APIs. Adzuna free tier: 250 req/day. Remotive: free, no auth required for remote jobs.
**Cons:** Adds ~2 files (`job_fetcher.py` + API key config), needs UI for search keyword/location params.
**Context:** Start with Remotive (zero friction, no API key needed). Add Adzuna second for broader coverage. Each posting fetched should auto-trigger the pipeline and land in the Applications tracker with status=Draft.
**Effort:** M | **Depends on:** Core pipeline working (Phase 1-6 complete)

---

## P2 — LinkedIn URL Auto-Extraction
**What:** User pastes a LinkedIn job URL; app fetches and extracts the job description text automatically.
**Why:** Most job hunters find roles on LinkedIn. Eliminating the copy-paste step removes friction from the #1 real-world use case.
**Pros:** ~30 lines with httpx + BeautifulSoup. Falls back gracefully to manual paste if fetch fails.
**Cons:** LinkedIn aggressively blocks scrapers. May require cookie auth or break without warning.
**Context:** Implement as best-effort: try to fetch, parse the `description__text` div, fall back to manual paste with a clear message if blocked. Do not hard-fail.
**Effort:** S | **Depends on:** Core pipeline working
