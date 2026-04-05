"""
Streamlit UI — Resume Tailor

Layout:
  Sidebar:  base resume / cover letter status
  Tab 1:    Tailor Resume (JD input → pipeline → diff + downloads)
  Tab 2:    Applicant Profile editor
  Tab 3:    Applications dashboard (tracker table + status updates)
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
BASE_COVER_PATH = Path("data/BaseCoverLetter.tex")

with st.sidebar:
    st.header("Base Files")
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

    base_cover_tex: str | None = None
    if BASE_COVER_PATH.exists():
        base_cover_tex = BASE_COVER_PATH.read_text(encoding="utf-8")
        st.success(f"Loaded: {BASE_COVER_PATH.name}")
        st.download_button(
            "⬇️ Download Base Cover Letter",
            data=base_cover_tex,
            file_name=BASE_COVER_PATH.name,
            mime="text/x-tex",
            use_container_width=True,
        )
    else:
        st.error(f"Base cover letter not found at {BASE_COVER_PATH}")

    st.divider()
    st.header("Profile Files")
    sample_profile = {
        "name": "", "phone": "", "email": "", "linkedin": "", "github": "", "portfolio": "",
        "experience": [{"title": "", "company": "", "location": "", "duration": "", "bullets": []}],
        "projects": [{"name": "", "tech": "", "bullets": []}],
        "education": [{"institution": "", "credential": "", "location": "", "year": ""}],
        "skills": {"languages": [], "tools": []},
        "certs": [],
        "scenarios": [{"context": "", "action": "", "result": "", "relevance": "", "tech": ""}],
    }
    st.download_button(
        "⬇️ Download Sample Profile",
        data=json.dumps(sample_profile, indent=2),
        file_name="applicant_profile.json",
        mime="application/json",
        use_container_width=True,
    )
    current_profile = load_profile()
    st.download_button(
        "⬇️ Download Current Profile",
        data=json.dumps(current_profile, indent=2),
        file_name="applicant_profile.json",
        mime="application/json",
        use_container_width=True,
    )

# ── Load profile (available to all tabs) ──────────────────────────────────

profile = load_profile()

# ── Main tabs ──────────────────────────────────────────────────────────────

tab_tailor, tab_profile, tab_apps = st.tabs(["✏️ Tailor Resume", "👤 Profile", "📋 Applications"])

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

        ready = bool(base_tex and base_cover_tex and job_desc.strip() and company.strip() and job_title.strip())
        if not ready:
            missing = []
            if not base_tex:
                missing.append("base resume (data/BaseResume.tex not found)")
            if not base_cover_tex:
                missing.append("base cover letter (data/BaseCoverLetter.tex not found)")
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
                st.write("Calling OpenAI API...")
                result = run_pipeline(
                    base_tex=base_tex,
                    base_cover_tex=base_cover_tex,
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

# ── Tab 2: Profile ─────────────────────────────────────────────────────────

with tab_profile:
    st.subheader("Applicant Profile")

    uploaded = st.file_uploader("Upload applicant_profile.json", type="json", label_visibility="collapsed")
    if uploaded is not None:
        try:
            uploaded_profile = json.loads(uploaded.read().decode("utf-8"))
            save_profile(uploaded_profile)
            profile = uploaded_profile
            st.success("Profile loaded from file.")
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")

    # ── Contact ──────────────────────────────────────────────────────────────
    st.markdown("#### Contact")
    c1, c2, c3 = st.columns(3)
    with c1:
        profile["name"] = st.text_input("Full Name", profile.get("name", ""))
    with c2:
        profile["phone"] = st.text_input("Phone", profile.get("phone", ""))
    with c3:
        profile["email"] = st.text_input("Email", profile.get("email", ""))
    c1, c2, c3 = st.columns(3)
    with c1:
        profile["linkedin"] = st.text_input("LinkedIn URL", profile.get("linkedin", ""))
    with c2:
        profile["github"] = st.text_input("GitHub URL", profile.get("github", ""))
    with c3:
        profile["portfolio"] = st.text_input("Portfolio URL", profile.get("portfolio", ""))

    # ── Experience ────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Experience")
    experience = profile.get("experience", [])
    if "exp_count" not in st.session_state:
        st.session_state.exp_count = max(len(experience), 1)
    new_experience = []
    for i in range(st.session_state.exp_count):
        exp = experience[i] if i < len(experience) else {}
        label = f"Role {i + 1}"
        with st.expander(label, expanded=(i == 0)):
            c1, c2 = st.columns(2)
            with c1:
                t = st.text_input("Job Title", exp.get("title", ""), key=f"exp_title_{i}")
            with c2:
                c = st.text_input("Company", exp.get("company", ""), key=f"exp_company_{i}")
            c1, c2 = st.columns(2)
            with c1:
                l = st.text_input("Location", exp.get("location", ""), key=f"exp_location_{i}")
            with c2:
                d = st.text_input("Duration", exp.get("duration", ""), key=f"exp_duration_{i}")
            b_str = "\n".join(exp.get("bullets", []))
            b_in = st.text_area("Bullets (one per line)", b_str, key=f"exp_bullets_{i}", height=120)
            bullets = [b.strip() for b in b_in.splitlines() if b.strip()]
            new_experience.append({"title": t, "company": c, "location": l, "duration": d, "bullets": bullets})
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("+ Add Role", key="add_exp"):
            st.session_state.exp_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Last Role", key="rem_exp") and st.session_state.exp_count > 1:
            st.session_state.exp_count -= 1
            st.rerun()
    profile["experience"] = new_experience

    # ── Projects ──────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Projects")
    projects = profile.get("projects", [])
    if "proj_count" not in st.session_state:
        st.session_state.proj_count = max(len(projects), 1)
    new_projects = []
    for i in range(st.session_state.proj_count):
        proj = projects[i] if i < len(projects) else {}
        label = f"Project {i + 1}"
        with st.expander(label, expanded=(i == 0)):
            c1, c2 = st.columns(2)
            with c1:
                n = st.text_input("Project Name", proj.get("name", ""), key=f"proj_name_{i}")
            with c2:
                t = st.text_input("Tech Stack", proj.get("tech", ""), key=f"proj_tech_{i}")
            b_str = "\n".join(proj.get("bullets", []))
            b_in = st.text_area("Bullets (one per line)", b_str, key=f"proj_bullets_{i}", height=120)
            bullets = [b.strip() for b in b_in.splitlines() if b.strip()]
            new_projects.append({"name": n, "tech": t, "bullets": bullets})
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("+ Add Project", key="add_proj"):
            st.session_state.proj_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Last Project", key="rem_proj") and st.session_state.proj_count > 1:
            st.session_state.proj_count -= 1
            st.rerun()
    profile["projects"] = new_projects

    # ── Education ─────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Education")
    education = profile.get("education", [])
    if "edu_count" not in st.session_state:
        st.session_state.edu_count = max(len(education), 1)
    new_education = []
    for i in range(st.session_state.edu_count):
        edu = education[i] if i < len(education) else {}
        label = f"Education {i + 1}"
        with st.expander(label, expanded=(i == 0)):
            c1, c2 = st.columns(2)
            with c1:
                inst = st.text_input("Institution", edu.get("institution", ""), key=f"edu_inst_{i}")
            with c2:
                cred = st.text_input("Credential", edu.get("credential", ""), key=f"edu_cred_{i}")
            c1, c2 = st.columns(2)
            with c1:
                loc = st.text_input("Location", edu.get("location", ""), key=f"edu_loc_{i}")
            with c2:
                yr = st.text_input("Year", edu.get("year", ""), key=f"edu_year_{i}")
            new_education.append({"institution": inst, "credential": cred, "location": loc, "year": yr})
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("+ Add Education", key="add_edu"):
            st.session_state.edu_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Last Education", key="rem_edu") and st.session_state.edu_count > 1:
            st.session_state.edu_count -= 1
            st.rerun()
    profile["education"] = new_education

    # ── Skills ────────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Skills")
    skills = profile.get("skills", {"languages": [], "tools": []})
    if not isinstance(skills, dict):
        skills = {"languages": [], "tools": []}
    c1, c2 = st.columns(2)
    with c1:
        lang_in = st.text_input(
            "Languages (comma-separated)",
            ", ".join(skills.get("languages", [])),
        )
    with c2:
        tools_in = st.text_input(
            "Tools & Technologies (comma-separated)",
            ", ".join(skills.get("tools", [])),
        )
    profile["skills"] = {
        "languages": [s.strip() for s in lang_in.split(",") if s.strip()],
        "tools": [s.strip() for s in tools_in.split(",") if s.strip()],
    }

    # ── Certificates ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### Certificates & Awards")
    certs = profile.get("certs", [])
    certs_in = st.text_input("Certificates (comma-separated)", ", ".join(certs))
    profile["certs"] = [c.strip() for c in certs_in.split(",") if c.strip()]

    # ── CARL Scenarios ────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### CARL Scenarios")
    st.caption("Used as inputs to customize your cover letter.")
    scenarios = profile.get("scenarios", [])
    if "sc_count" not in st.session_state:
        st.session_state.sc_count = max(len(scenarios), 1)
    new_scenarios = []
    for i in range(st.session_state.sc_count):
        sc = scenarios[i] if i < len(scenarios) else {}
        with st.expander(f"Scenario", expanded=(i == 0)):
            c1, c2 = st.columns([3, 1])
            with c1:
                ctx = st.text_area("Context", sc.get("context", ""), key=f"sc_ctx_{i}", height=80)
            with c2:
                tch = st.text_input("Tech", sc.get("tech", ""), key=f"sc_tech_{i}")
            act = st.text_area("Action", sc.get("action", ""), key=f"sc_act_{i}", height=80)
            res = st.text_area("Result", sc.get("result", ""), key=f"sc_res_{i}", height=80)
            rel = st.text_area("Relevance", sc.get("relevance", ""), key=f"sc_rel_{i}", height=80)
            new_scenarios.append({"context": ctx, "action": act, "result": res, "relevance": rel, "tech": tch})
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("+ Add Scenario", key="add_sc"):
            st.session_state.sc_count += 1
            st.rerun()
    with c2:
        if st.button("- Remove Last Scenario", key="rem_sc") and st.session_state.sc_count > 1:
            st.session_state.sc_count -= 1
            st.rerun()
    profile["scenarios"] = new_scenarios

    st.divider()
    if st.button("Save Profile", type="primary", use_container_width=True):
        save_profile(profile)
        st.success("Profile saved.")

# ── Tab 3: Applications ────────────────────────────────────────────────────

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

                exp_col1, exp_col2 = st.columns(2)
                with exp_col1:
                    if app.resume_tex:
                        with st.expander("Resume .tex"):
                            st.code(app.resume_tex, language="latex")
                with exp_col2:
                    if app.cover_letter_tex:
                        with st.expander("Cover Letter .tex"):
                            st.code(app.cover_letter_tex, language="latex")
