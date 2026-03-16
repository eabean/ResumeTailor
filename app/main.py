"""
Streamlit UI — Resume Tailor

Layout:
  Sidebar:  base resume upload + applicant profile editor
  Tab 1:    Tailor Resume (JD input → pipeline → diff + downloads)
  Tab 2:    Applications dashboard (tracker table + status updates)
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path when run via `streamlit run app/main.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

import streamlit as st

from app import tracker
from app.diff import diff_to_html, has_changes
from app.models import ApplicationStatus
from app.pipeline import run_pipeline

PROFILE_PATH = Path("data/applicant_profile.json")
STATUS_OPTIONS = [s.value for s in ApplicationStatus]


# ── Helpers ────────────────────────────────────────────────────────────────

def load_profile() -> dict:
    if PROFILE_PATH.exists():
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    return {}


def save_profile(profile: dict) -> None:
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")


# ── Page config ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Resume Tailor",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Resume Tailor")

# ── Sidebar ────────────────────────────────────────────────────────────────

BASE_RESUME_PATH = Path("data/BaseResume.tex")

with st.sidebar:
    st.header("Base Resume")
    base_tex: str | None = None
    if BASE_RESUME_PATH.exists():
        base_tex = BASE_RESUME_PATH.read_text(encoding="utf-8")
        st.success(f"Loaded: {BASE_RESUME_PATH.name}")
        st.download_button(
            "⬇️ Download Base Resume",
            data=base_tex,
            file_name=BASE_RESUME_PATH.name,
            mime="text/x-tex",
            use_container_width=True,
        )
    else:
        st.error(f"Base resume not found at {BASE_RESUME_PATH}")

    st.divider()

    st.header("Applicant Profile")
    profile = load_profile()

    with st.expander("Edit Profile", expanded=not bool(profile.get("name"))):
        profile["name"] = st.text_input("Full Name", profile.get("name", ""))
        profile["email"] = st.text_input("Email", profile.get("email", ""))
        profile["phone"] = st.text_input("Phone", profile.get("phone", ""))
        profile["location"] = st.text_input("Location", profile.get("location", ""))
        profile["linkedin"] = st.text_input("LinkedIn URL", profile.get("linkedin", ""))
        profile["github"] = st.text_input("GitHub URL", profile.get("github", ""))
        profile["summary"] = st.text_area(
            "Professional Summary",
            profile.get("summary", ""),
            height=100,
        )
        skills_str = ", ".join(profile.get("skills", []))
        skills_input = st.text_input("Skills (comma-separated)", skills_str)
        profile["skills"] = [s.strip() for s in skills_input.split(",") if s.strip()]
        profile["extra_context"] = st.text_area(
            "Extra Context for Claude",
            profile.get("extra_context", ""),
            height=80,
            help="Career goals, pivots, preferences — anything Claude should know.",
        )

        if st.button("Save Profile", type="primary"):
            save_profile(profile)
            st.success("Profile saved.")

# ── Main tabs ──────────────────────────────────────────────────────────────

tab_tailor, tab_apps = st.tabs(["✏️ Tailor Resume", "📋 Applications"])

# ── Tab 1: Tailor ──────────────────────────────────────────────────────────

with tab_tailor:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Job Details")
        company = st.text_input("Company Name", placeholder="Acme Corp")
        job_title = st.text_input("Job Title", placeholder="Software Engineer")
        job_desc = st.text_area(
            "Job Description",
            placeholder="Paste the full job description here...",
            height=350,
        )

    with col2:
        st.subheader("Actions")
        st.write("")

        ready = bool(base_tex and job_desc.strip() and company.strip() and job_title.strip())
        if not ready:
            missing = []
            if not base_tex:
                missing.append("base resume (data/BaseResume.tex not found)")
            if not job_desc.strip():
                missing.append("job description")
            if not company.strip():
                missing.append("company name")
            if not job_title.strip():
                missing.append("job title")
            st.info(f"Still needed: {', '.join(missing)}")

        tailor_btn = st.button(
            "🚀 Tailor Resume",
            type="primary",
            disabled=not ready,
            use_container_width=True,
        )

    if tailor_btn and ready:
        with st.status("Tailoring your resume...", expanded=True) as status:
            try:
                st.write("Calling Claude API...")
                result = run_pipeline(
                    base_tex=base_tex,
                    job_desc=job_desc,
                    profile=profile,
                    company=company,
                    job_title=job_title,
                )
                st.write("Compiling PDFs...")
                st.write("Generating diff...")
                status.update(label="Done! ✅", state="complete", expanded=False)
                st.session_state["last_result"] = result
            except Exception as e:
                status.update(label="Failed ❌", state="error")
                st.error(str(e))

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]

        st.divider()
        st.subheader("Results")

        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                "⬇️ Download Resume PDF",
                data=result.resume_pdf,
                file_name=f"resume_{company.lower().replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with dl_col2:
            st.download_button(
                "⬇️ Download Cover Letter PDF",
                data=result.cover_pdf,
                file_name=f"cover_letter_{company.lower().replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        st.caption(f"Application saved to tracker (ID: {result.application_id})")

        st.subheader("What Changed")
        if has_changes(result.diff_lines):
            st.markdown(diff_to_html(result.diff_lines), unsafe_allow_html=True)
        else:
            st.info("No changes detected between base and tailored resume.")

        with st.expander("View tailored .tex source"):
            st.code(result.resume_tex, language="latex")

        with st.expander("View cover letter .tex source"):
            st.code(result.cover_letter_tex, language="latex")

# ── Tab 2: Applications ────────────────────────────────────────────────────

with tab_apps:
    st.subheader("Application Tracker")

    applications = tracker.get_all_applications()

    if not applications:
        st.info("No applications yet. Tailor your first resume to get started.")
    else:
        for app in applications:
            with st.container(border=True):
                header_col, status_col, del_col = st.columns([3, 1.5, 0.5])

                with header_col:
                    st.markdown(f"**{app.job_title}** at **{app.company}**")
                    st.caption(f"Applied: {app.created_at.strftime('%b %d, %Y')}  •  ID: {app.id}")

                with status_col:
                    new_status = st.selectbox(
                        "Status",
                        options=STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(app.status) if app.status in STATUS_OPTIONS else 0,
                        key=f"status_{app.id}",
                        label_visibility="collapsed",
                    )
                    if new_status != app.status:
                        tracker.update_status(app.id, new_status)
                        st.rerun()

                with del_col:
                    if st.button("🗑️", key=f"del_{app.id}", help="Delete this application"):
                        tracker.delete_application(app.id)
                        st.rerun()

                if app.jd_snippet:
                    with st.expander("Job description snippet"):
                        st.text(app.jd_snippet)
