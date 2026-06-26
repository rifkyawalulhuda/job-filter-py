"""Streamlit UI for the AI-powered job-vacancy-filter application."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.applications import (
    apply_saved_application_statuses,
    ensure_application_columns,
    persist_application_status,
    update_application_status,
)
from src.cover_letter import generate_cover_letter
from src.cv_parser import CVAnalysis, analyze_cv_bytes, analyze_profile_text, match_cv_skills_to_job
from src.database import DEFAULT_DATABASE_PATH, init_database
from src.export_excel import dataframe_to_excel_bytes
from src.filters import JobFilters, apply_filters
from src.job_search import search_jobs
from src.profile import UserProfile, load_profile, save_profile
from src.scoring import calculate_match_score
from src.llm import (
    LLMConfig,
    load_llm_config,
    save_llm_config,
    generate_ai_cover_letter,
    ai_enhance_jobs,
    ai_generate_profile_summary,
    ai_generate_cv,
)

DATABASE_PATH = DEFAULT_DATABASE_PATH
WORK_MODE_OPTIONS = ["Any", "remote", "hybrid", "onsite"]
JOB_LEVEL_OPTIONS = [
    "Any", "internship", "entry", "junior", "mid", "senior", "lead", "manager",
]
COVER_LETTER_TONES = ["formal", "concise", "confident"]

# ── Design System (Swiss Modernism + Job Board palette) ────────────────────
# Color: Professional Blue (#0369A1) + Light Blue (#F0F9FF)
# Style: Flat Design, mathematical spacing, single accent

_CUSTOM_CSS = """
<style>
/* ═══════════════════════════════════════════════════════════════════════
   Design System: Executive Dashboard + Minimal & Direct
   All colors follow Streamlit native theme variables.
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Sidebar: subtle gradient + clean spacing ── */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128, 128, 128, 0.15) !important;
}

/* ── Sidebar inputs: consistent sizing ── */
section[data-testid="stSidebar"] input[type="text"],
section[data-testid="stSidebar"] input[type="password"] {
    border-radius: 8px !important;
    padding: 0.45rem 0.7rem !important;
    font-size: 0.85rem !important;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
    background: transparent !important;
}
section[data-testid="stSidebar"] input::placeholder {
    opacity: 0.45 !important;
}

/* ── Select: rounded ── */
section[data-testid="stSidebar"] [data-baseweb="select"] {
    border-radius: 8px !important;
}

/* ── Buttons: consistent rounded corners ── */
section[data-testid="stSidebar"] button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: opacity 0.2s ease !important;
}
section[data-testid="stSidebar"] button[kind="primary"]:hover {
    opacity: 0.88 !important;
}
section[data-testid="stSidebar"] button[kind="secondary"],
section[data-testid="stSidebar"] button[kind="secondaryFormSubmit"] {
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
}

/* ── Expander: clean borders ── */
section[data-testid="stSidebar"] .streamlit-expanderHeader {
    border-radius: 8px !important;
    border: 1px solid rgba(128, 128, 128, 0.15) !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
}
section[data-testid="stSidebar"] .streamlit-expanderContent {
    border: none !important;
    padding-top: 0.5rem !important;
}

/* ── Caption ── */
section[data-testid="stSidebar"] .stCaption {
    font-size: 0.75rem !important;
    opacity: 0.65 !important;
}

/* ═══════════════════════════════════════════════════════════════════════
   MAIN AREA
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Main container: max width + padding ── */
main .block-container {
    max-width: 1200px !important;
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
}

/* ── Title: clean ── */
h1 {
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    margin-bottom: 0.25rem !important;
}

/* ── Subheaders: uppercase tracking ── */
h2, h3 {
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    margin-top: 2rem !important;
}

/* ── Metric cards: card style ── */
[data-testid="stMetric"] {
    background: rgba(128, 128, 128, 0.05);
    border: 1px solid rgba(128, 128, 128, 0.12);
    border-radius: 10px;
    padding: 1rem 1.2rem !important;
    margin: 0.25rem 0;
}
[data-testid="stMetric"] label {
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    opacity: 0.7 !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
}

/* ── DataFrame: clean borders ── */
.stDataFrame {
    border: 1px solid rgba(128, 128, 128, 0.15) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* ── Download buttons: subtle ── */
.stDownloadButton button {
    border-radius: 8px !important;
    font-weight: 500 !important;
}

/* ── Expander in main area ── */
main .streamlit-expanderHeader {
    border-radius: 8px !important;
    border: 1px solid rgba(128, 128, 128, 0.15) !important;
    font-weight: 500 !important;
}

/* ── AI status badge ── */
.ai-status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    vertical-align: middle;
    margin-left: 6px;
}
.ai-status-active {
    background: rgba(22, 163, 74, 0.15);
    color: #16A34A;
}
.ai-status-inactive {
    background: rgba(128, 128, 128, 0.12);
    color: inherit;
    opacity: 0.6;
}

/* ── Scrollbar ── */
::-webkit-scrollbar {
    width: 8px;
}
::-webkit-scrollbar-thumb {
    border-radius: 4px;
}
</style>
"""


def _inject_custom_css() -> None:
    """Inject the custom design system CSS into the Streamlit app."""
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


def _toast(message: str, type: str = "info", duration: int = 4) -> None:
    """Show a floating toast notification using Streamlit's native st.toast.

    Args:
        message: The notification text.
        type: One of 'success', 'error', 'warning', 'info'.
        duration: Auto-dismiss time in SECONDS (default 4).
    """
    icon_map = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
    }
    icon = icon_map.get(type, "ℹ️")
    st.toast(message, icon=icon)


def _parse_optional_float(value: str, field_label: str) -> float | None:
    """Parse a numeric input string into a float or raise a friendly error."""
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field_label} must be a valid number.") from exc


def _merge_profile_with_cv(profile: UserProfile, analysis: CVAnalysis) -> UserProfile:
    """Fill empty profile fields with values detected from the uploaded CV."""
    return UserProfile(
        name=profile.name or analysis.name,
        email=profile.email or analysis.email,
        phone=profile.phone or analysis.phone,
        linkedin_url=profile.linkedin_url or analysis.linkedin_url,
        portfolio_url=profile.portfolio_url or analysis.portfolio_url,
    )


def _build_job_filters(
    keyword: str,
    location: str,
    work_mode: str,
    job_level: str,
    minimum_salary_text: str,
    maximum_salary_text: str,
    skills_text: str,
    posted_after: date | None,
    include_unknown_salary: bool,
) -> JobFilters:
    """Build a ``JobFilters`` instance from sidebar form values."""
    skills = [skill.strip() for skill in skills_text.split(",") if skill.strip()]
    return JobFilters(
        keyword=keyword,
        location=location,
        work_mode=work_mode,
        job_level=job_level,
        salary_min=_parse_optional_float(minimum_salary_text, "Minimum salary"),
        salary_max=_parse_optional_float(maximum_salary_text, "Maximum salary"),
        skills=skills,
        posted_after=posted_after,
        include_unknown_salary=include_unknown_salary,
    )


def _format_job_option(row: pd.Series) -> str:
    """Format a job option label for the application selector."""
    title = str(row.get("job_title", "") or "Untitled role")
    company = str(row.get("company", "") or "Unknown company")
    location = str(row.get("location", "") or "Unknown location")
    return f"{title} - {company} ({location})"


def _sync_status_to_state(row_index: int, status: str) -> None:
    """Apply a status update to stored DataFrames in session state."""
    if "results_df" in st.session_state and row_index in st.session_state.results_df.index:
        st.session_state.results_df = update_application_status(
            st.session_state.results_df,
            row_index,
            status,
        )


def _persist_selected_job_status(
    row: pd.Series,
    status: str,
    cover_letter_text: str = "",
) -> None:
    """Persist one selected job status update to SQLite."""
    persist_application_status(
        row.to_dict(),
        status=status,
        path=DATABASE_PATH,
        cover_letter_text=cover_letter_text,
    )


def _render_results_metrics(results_df: pd.DataFrame, total_jobs: int) -> None:
    """Render high-level result metrics."""
    average_score = 0.0
    if not results_df.empty and "match_score" in results_df.columns:
        average_score = float(results_df["match_score"].mean())

    col1, col2, col3 = st.columns(3)
    col1.metric("Results found", len(results_df))
    col2.metric("Average match score", f"{average_score:.1f}")
    col3.metric("Total searched", total_jobs)


def main() -> None:
    """Run the Streamlit app."""
    st.set_page_config(page_title="AI Job Vacancy Filter", layout="wide")
    _inject_custom_css()
    st.title("AI Job Vacancy Filter")
    st.caption(
        "Search real job listings on LinkedIn Indonesia. "
        "Filter, score, and prepare your applications."
    )

    # ── Database init ───────────────────────────────────────────────────
    try:
        init_database(DATABASE_PATH)
    except Exception:
        st.error(
            "We could not initialize the local application database. "
            "Please check file permissions and try again."
        )
        return

    # ── Session state ───────────────────────────────────────────────────
    defaults = {
        "profile": None,
        "results_df": pd.DataFrame(),
        "cover_letter_text": "",
        "selected_job_index": None,
        "cv_analysis": CVAnalysis(),
        "cv_file_name": "",
        "cover_letter_tone": "formal",
        "cover_letter_custom_prompt": "",
        "last_search_count": 0,
        "llm_config": None,
        "use_ai_cover_letter": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            if key == "profile":
                try:
                    st.session_state.profile = load_profile(DATABASE_PATH)
                except Exception:
                    st.session_state.profile = UserProfile()
                    st.warning(
                        "We could not load the saved profile from the local database, "
                        "so the form started empty."
                    )
            elif key == "llm_config":
                try:
                    st.session_state.llm_config = load_llm_config(DATABASE_PATH)
                except Exception:
                    st.session_state.llm_config = LLMConfig()
            else:
                st.session_state[key] = default

    # ══════════════════════════════════════════════════════════════════════
    # SIDEBAR — Collapsible Sections
    # ══════════════════════════════════════════════════════════════════════
    with st.sidebar:
        # ── Search Section (expanded by default) ──────────────────────
        with st.expander("Search Filters", expanded=True):
            st.caption("Find jobs on LinkedIn Indonesia")

            keyword = st.text_input(
                "Keyword / Job title",
                placeholder="e.g. Python Developer",
                label_visibility="collapsed",
            )
            location = st.text_input(
                "Location",
                placeholder="e.g. Jakarta",
                label_visibility="collapsed",
            )

            col1, col2 = st.columns(2)
            with col1:
                work_mode = st.selectbox(
                    "Work mode", WORK_MODE_OPTIONS, label_visibility="collapsed"
                )
            with col2:
                job_level = st.selectbox(
                    "Job level", JOB_LEVEL_OPTIONS, label_visibility="collapsed"
                )

            skills_text = st.text_input(
                "Skills",
                placeholder="Python, React, Docker",
                label_visibility="collapsed",
            )

            with st.expander("Salary & Date", expanded=False):
                minimum_salary_text = st.text_input("Minimum salary")
                maximum_salary_text = st.text_input("Maximum salary")
                posted_after = st.date_input("Posted after", value=None)
                include_unknown_salary = st.checkbox(
                    "Include unknown salary", value=True
                )

        ai_search_clicked = st.button(
            "Search Jobs",
            width="stretch",
            type="primary",
            use_container_width=True,
            help="Search LinkedIn Indonesia for matching jobs.",
        )

        # ── Profile & CV Section ─────────────────────────────────────
        with st.expander("Profile & CV", expanded=False):
            with st.form("profile_form"):
                profile_name = st.text_input(
                    "Name",
                    value=st.session_state.profile.name,
                    label_visibility="collapsed",
                    placeholder="Your name",
                )
                profile_email = st.text_input(
                    "Email",
                    value=st.session_state.profile.email,
                    label_visibility="collapsed",
                    placeholder="your@email.com",
                )
                profile_phone = st.text_input(
                    "Phone",
                    value=st.session_state.profile.phone,
                    label_visibility="collapsed",
                    placeholder="+62...",
                )
                profile_linkedin = st.text_input(
                    "LinkedIn URL",
                    value=st.session_state.profile.linkedin_url,
                    label_visibility="collapsed",
                    placeholder="linkedin.com/in/...",
                )
                profile_portfolio = st.text_input(
                    "Portfolio URL",
                    value=st.session_state.profile.portfolio_url,
                    label_visibility="collapsed",
                    placeholder="yourportfolio.com",
                )
                save_profile_clicked = st.form_submit_button(
                    "Save Profile", width="stretch"
                )

            # ── CV / Profile Input: toggle between PDF upload and text ─
            st.divider()
            st.caption("Import profile from CV or text")
            cv_input_method = st.radio(
                "Input method",
                ["Upload PDF/DOCX", "Write Markdown/Text"],
                label_visibility="collapsed",
                horizontal=True,
                key="cv_input_method",
            )

            cv_uploaded_file = None
            profile_text_input = ""

            if cv_input_method == "Upload PDF/DOCX":
                cv_uploaded_file = st.file_uploader(
                    "Upload CV (PDF/DOCX)",
                    type=["pdf", "docx"],
                    key="cv_uploader",
                    label_visibility="collapsed",
                )
                use_cv_profile_clicked = st.button(
                    "Use CV Details in Profile",
                    width="stretch",
                    disabled=cv_uploaded_file is None,
                )
                parse_text_clicked = False
            else:
                profile_text_input = st.text_area(
                    "Paste your profile (Markdown or plain text)",
                    placeholder=(
                        "Name: Santi Husni\n"
                        "Email: santi@example.com\n"
                        "Phone: +628****5678\n"
                        "LinkedIn: https://linkedin.com/in/santi\n"
                        "Skills: Python, FastAPI, PostgreSQL, Docker\n"
                        "Experience: Backend engineer with 5 years..."
                    ),
                    height=200,
                    key="profile_text_input",
                )
                use_cv_profile_clicked = False
                parse_text_clicked = st.button(
                    "Parse & Use Text Profile",
                    width="stretch",
                    disabled=not profile_text_input.strip(),
                )

            # AI-powered Profile & CV generation
            if st.session_state.llm_config.is_configured:
                st.divider()
                st.caption("AI-powered generation")

                ai_summary_clicked = st.button(
                    "AI Generate Summary",
                    width="stretch",
                    help="Generate a professional summary using your LLM.",
                )
                ai_cv_clicked = st.button(
                    "AI Generate CV",
                    width="stretch",
                    help="Generate a complete CV using your LLM and profile data.",
                )
            else:
                ai_summary_clicked = False
                ai_cv_clicked = False

    # ── Profile save handler ────────────────────────────────────────────
    if save_profile_clicked:
        try:
            st.session_state.profile = UserProfile(
                name=profile_name,
                email=profile_email,
                phone=profile_phone,
                linkedin_url=profile_linkedin,
                portfolio_url=profile_portfolio,
            )
            save_profile(st.session_state.profile, DATABASE_PATH)
            _toast("Profile saved to local database.", "success")
        except Exception:
            _toast("Could not save profile. Please try again.", "error")

    # ── CV upload handler ───────────────────────────────────────────────
    if (
        cv_uploaded_file is not None
        and st.session_state.cv_file_name != cv_uploaded_file.name
    ):
        try:
            st.session_state.cv_analysis = analyze_cv_bytes(
                cv_uploaded_file.name,
                cv_uploaded_file.getvalue(),
            )
            st.session_state.cv_file_name = cv_uploaded_file.name
            _toast("CV analyzed successfully.", "success")
        except ValueError as exc:
            _toast(str(exc), "error")
        except Exception:
            _toast("Could not read that CV file. Please try another PDF or DOCX.", "error")
    elif cv_uploaded_file is None and st.session_state.cv_file_name:
        st.session_state.cv_analysis = CVAnalysis()
        st.session_state.cv_file_name = ""

    if use_cv_profile_clicked:
        if st.session_state.cv_analysis.text:
            st.session_state.profile = _merge_profile_with_cv(
                st.session_state.profile,
                st.session_state.cv_analysis,
            )
            _toast("Profile fields filled from CV.", "success")
        else:
            _toast("Upload a readable CV first.", "warning")

    # ── Parse text profile handler ───────────────────────────────────
    if parse_text_clicked and profile_text_input.strip():
        try:
            st.session_state.cv_analysis = analyze_profile_text(
                profile_text_input.strip()
            )
            st.session_state.cv_file_name = "text_input"
            if st.session_state.cv_analysis.text:
                st.session_state.profile = _merge_profile_with_cv(
                    st.session_state.profile,
                    st.session_state.cv_analysis,
                )
            _toast("Text profile parsed and applied.", "success")
        except Exception as exc:
            _toast(f"Could not parse text profile: {exc}", "error")

    # ── AI Generate Summary handler ──────────────────────────────────
    if ai_summary_clicked:
        try:
            with st.spinner("AI generating professional summary..."):
                summary = ai_generate_profile_summary(
                    name=st.session_state.profile.name or "Professional",
                    skills=", ".join(st.session_state.cv_analysis.skills) if st.session_state.cv_analysis.skills else "",
                    experience=st.session_state.cv_analysis.experience_summary,
                    target_role=keyword if keyword else "",
                    config=st.session_state.llm_config,
                )
            st.session_state["ai_generated_summary"] = summary
            _toast("AI summary generated!", "success")
        except Exception as exc:
            _toast(f"AI summary failed: {exc}", "error")

    # ── AI Generate CV handler ───────────────────────────────────────
    if ai_cv_clicked:
        try:
            with st.spinner("AI generating CV..."):
                cv_text = ai_generate_cv(
                    name=st.session_state.profile.name or "Professional",
                    email=st.session_state.profile.email,
                    phone=st.session_state.profile.phone,
                    linkedin=st.session_state.profile.linkedin_url,
                    skills=", ".join(st.session_state.cv_analysis.skills) if st.session_state.cv_analysis.skills else "",
                    experience=st.session_state.cv_analysis.experience_summary,
                    target_role=keyword if keyword else "",
                    config=st.session_state.llm_config,
                )
            st.session_state["ai_generated_cv"] = cv_text
            _toast("AI CV generated!", "success")
        except Exception as exc:
            _toast(f"AI CV generation failed: {exc}", "error")

    # ── CV insights (sidebar) ───────────────────────────────────────────
    if st.session_state.cv_analysis.text:
        with st.sidebar:
            with st.expander("CV Insights", expanded=False):
                if st.session_state.cv_analysis.name:
                    st.caption(f"**Name:** {st.session_state.cv_analysis.name}")
                if st.session_state.cv_analysis.email:
                    st.caption(f"**Email:** {st.session_state.cv_analysis.email}")
                if st.session_state.cv_analysis.phone:
                    st.caption(f"**Phone:** {st.session_state.cv_analysis.phone}")
                if st.session_state.cv_analysis.skills:
                    st.caption("**Skills:** " + ", ".join(st.session_state.cv_analysis.skills))

    # ── BYOK Panel ──────────────────────────────────────────────────────
    with st.sidebar:
        ai_status = "Active" if st.session_state.llm_config.is_configured else "Inactive"
        ai_badge = "ai-status-active" if st.session_state.llm_config.is_configured else "ai-status-inactive"

        with st.expander("AI Settings", expanded=False):
            st.markdown(
                f'<span class="ai-status-badge {ai_badge}">{ai_status}</span>',
                unsafe_allow_html=True,
            )
            st.caption("Bring Your Own Key")

            with st.form("byok_form"):
                byok_api_base = st.text_input(
                    "API Base URL",
                    value=st.session_state.llm_config.api_base,
                    label_visibility="collapsed",
                    placeholder="https://dough.id/api/v1",
                )
                byok_api_key = st.text_input(
                    "API Key",
                    value=st.session_state.llm_config.api_key,
                    type="password",
                    label_visibility="collapsed",
                    placeholder="sk-...",
                )
                byok_model = st.text_input(
                    "Model",
                    value=st.session_state.llm_config.model,
                    label_visibility="collapsed",
                    placeholder="mimo/mimo-v2.5",
                )
                save_byok_clicked = st.form_submit_button(
                    "Save AI Config", width="stretch"
                )

            st.session_state.use_ai_cover_letter = st.checkbox(
                "AI-Powered Cover Letter",
                value=st.session_state.use_ai_cover_letter,
                help="Generate personalized cover letters using your LLM.",
            )

    if save_byok_clicked:
        try:
            st.session_state.llm_config = LLMConfig(
                api_base=byok_api_base.strip(),
                api_key=byok_api_key.strip(),
                model=byok_model.strip(),
            )
            save_llm_config(st.session_state.llm_config, DATABASE_PATH)
            _toast("AI config saved!", "success")
        except Exception:
            _toast("Could not save AI config.", "error")

    # ══════════════════════════════════════════════════════════════════════
    # AI SEARCH + FILTER + SCORE
    # ══════════════════════════════════════════════════════════════════════
    if ai_search_clicked:
        try:
            active_filters = _build_job_filters(
                keyword=keyword,
                location=location,
                work_mode=work_mode,
                job_level=job_level,
                minimum_salary_text=minimum_salary_text,
                maximum_salary_text=maximum_salary_text,
                skills_text=skills_text,
                posted_after=posted_after,
                include_unknown_salary=include_unknown_salary,
            )
            with st.spinner("Phase 1 — Searching LinkedIn, Indeed, Glints, Kalibrr & Bing in parallel..."):
                raw_jobs = search_jobs(active_filters)

            # AI Enhance: if LLM is configured, enrich scraped data
            if st.session_state.llm_config.is_configured:
                with st.spinner("Phase 3 — AI enriching job data (skills, salary, level)..."):
                    try:
                        raw_jobs = ai_enhance_jobs(
                            raw_jobs,
                            config=st.session_state.llm_config,
                        )
                    except Exception:
                        pass  # Continue with unenhanced data if LLM fails

            # Apply application status overlay
            raw_jobs = ensure_application_columns(raw_jobs)
            raw_jobs = apply_saved_application_statuses(raw_jobs, path=DATABASE_PATH)

            # Filter and score
            filtered = apply_filters(raw_jobs, active_filters)
            scored = calculate_match_score(filtered, active_filters)

            st.session_state.results_df = scored
            st.session_state.cover_letter_text = ""
            st.session_state.selected_job_index = None
            st.session_state.last_search_count = len(raw_jobs)

            if scored.empty:
                _toast("No jobs matched your filters. Try broadening your search.", "warning", 6000)
            else:
                _toast(f"Found {len(raw_jobs)} jobs - {len(scored)} matched your filters.", "success")
        except ValueError as exc:
            _toast(str(exc), "error", 6000)
        except Exception:
            _toast("Search failed. Check your internet connection.", "error", 6000)

    results_df = st.session_state.results_df.copy()

    # ══════════════════════════════════════════════════════════════════════
    # RESULTS
    # ══════════════════════════════════════════════════════════════════════
    if results_df.empty:
        st.info(
            "Fill in at least a keyword or location in the sidebar, "
            "then click **Search Jobs** to find vacancies."
        )
        if "ai_generated_summary" in st.session_state:
            st.divider()
            st.subheader("AI-Generated Professional Summary")
            st.text_area(
                "Summary",
                value=st.session_state["ai_generated_summary"],
                height=150,
                key="display_summary",
            )
        if "ai_generated_cv" in st.session_state:
            st.divider()
            st.subheader("AI-Generated CV")
            st.text_area(
                "CV",
                value=st.session_state["ai_generated_cv"],
                height=400,
                key="display_cv",
            )
            st.download_button(
                "Download CV",
                data=st.session_state["ai_generated_cv"].encode("utf-8"),
                file_name="ai_generated_cv.txt",
                mime="text/plain",
            )
        return

    # Show AI-generated content above results
    if "ai_generated_summary" in st.session_state:
        with st.expander("AI-Generated Professional Summary", expanded=False):
            st.text(st.session_state["ai_generated_summary"])
    if "ai_generated_cv" in st.session_state:
        with st.expander("AI-Generated CV", expanded=False):
            st.text(st.session_state["ai_generated_cv"])
            st.download_button(
                "Download CV",
                data=st.session_state["ai_generated_cv"].encode("utf-8"),
                file_name="ai_generated_cv.txt",
                mime="text/plain",
                key="download_cv_results",
            )

    _render_results_metrics(results_df, st.session_state.last_search_count)

    st.subheader("Filtered Results")
    st.dataframe(results_df, use_container_width=True, hide_index=False)

    try:
        excel_bytes = dataframe_to_excel_bytes(results_df)
        st.download_button(
            "Download Excel",
            data=excel_bytes,
            file_name="filtered_jobs.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        _toast("Could not prepare Excel export.", "error")

    # ══════════════════════════════════════════════════════════════════════
    # APPLICATION ASSISTANT
    # ══════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("Application Assistant")
    st.caption(
        "Prepare your application manually. "
        "This does not auto-submit or scrape job sites."
    )

    job_option_indexes = list(results_df.index)
    selected_job_index = st.selectbox(
        "Select a job",
        options=job_option_indexes,
        format_func=lambda index: _format_job_option(results_df.loc[index]),
    )
    selected_job = results_df.loc[selected_job_index]
    st.session_state.selected_job_index = selected_job_index

    selected_tone = st.selectbox(
        "Cover letter tone",
        options=COVER_LETTER_TONES,
        index=COVER_LETTER_TONES.index(st.session_state.cover_letter_tone),
    )
    st.session_state.cover_letter_tone = selected_tone

    custom_cover_letter_prompt = st.text_input(
        "Edit prompt",
        value=st.session_state.cover_letter_custom_prompt,
        help="Contoh: lebih formal, lebih singkat, lebih percaya diri.",
    )
    st.session_state.cover_letter_custom_prompt = custom_cover_letter_prompt

    skill_match = None
    if st.session_state.cv_analysis.skills:
        skill_match = match_cv_skills_to_job(
            st.session_state.cv_analysis.skills,
            str(selected_job.get("skills", "") or ""),
            str(selected_job.get("description", "") or ""),
        )
        if skill_match.matched:
            st.info(
                f"Matched CV skills for this job: {', '.join(skill_match.matched)}"
            )
        else:
            st.info(
                "CV uploaded, but no direct skill overlap was detected "
                "for this selected job yet."
            )
        if skill_match.inferred_job_skills:
            st.caption(
                f"Detected job skills: {', '.join(skill_match.inferred_job_skills)}"
            )
        if skill_match.missing:
            st.warning(
                f"Job skills not detected in CV yet: {', '.join(skill_match.missing)}"
            )

    prepare_clicked = st.button("Prepare Application", type="primary")
    if prepare_clicked:
        try:
            if (
                st.session_state.use_ai_cover_letter
                and st.session_state.llm_config.is_configured
            ):
                # AI-powered cover letter via BYOK
                job_title = str(selected_job.get("job_title", "") or "")
                company = str(selected_job.get("company", "") or "")
                location = str(selected_job.get("location", "") or "")
                skills_text = str(selected_job.get("skills", "") or "")
                applicant_name = st.session_state.profile.name or "Applicant"

                st.session_state.cover_letter_text = generate_ai_cover_letter(
                    job_title=job_title,
                    company=company,
                    location=location,
                    skills_text=skills_text,
                    applicant_name=applicant_name,
                    cv_summary=st.session_state.cv_analysis.experience_summary,
                    tone=selected_tone,
                    custom_prompt=custom_cover_letter_prompt,
                    config=st.session_state.llm_config,
                )
            else:
                # Template-based cover letter
                st.session_state.cover_letter_text = generate_cover_letter(
                    selected_job,
                    st.session_state.profile,
                    matched_skills=(
                        skill_match.matched if skill_match is not None else None
                    ),
                    missing_skills=(
                        skill_match.missing if skill_match is not None else None
                    ),
                    experience_summary=st.session_state.cv_analysis.experience_summary,
                    tone=selected_tone,
                    custom_prompt=custom_cover_letter_prompt,
                )
            _sync_status_to_state(selected_job_index, "Draft Ready")
            _persist_selected_job_status(
                selected_job,
                "Draft Ready",
                cover_letter_text=st.session_state.cover_letter_text,
            )
            results_df = st.session_state.results_df.copy()
            selected_job = results_df.loc[selected_job_index]
        except Exception:
            _toast("Could not prepare application draft.", "error")

    cover_letter_text = st.text_area(
        "Generated cover letter",
        value=st.session_state.cover_letter_text,
        height=260,
    )
    st.session_state.cover_letter_text = cover_letter_text

    # Action buttons in a row
    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])
    with action_col1:
        st.download_button(
            "Download Cover Letter",
            data=cover_letter_text.encode("utf-8"),
            file_name="cover_letter.txt",
            mime="text/plain",
            disabled=not cover_letter_text.strip(),
        )

    apply_url = str(selected_job.get("apply_url", "") or "").strip()
    with action_col2:
        if apply_url:
            st.link_button("Open Apply Link", url=apply_url)
        else:
            st.info("No apply link available.")

    with action_col3:
        if st.button("Mark as Submitted"):
            try:
                _sync_status_to_state(selected_job_index, "Submitted")
                _persist_selected_job_status(selected_job, "Submitted")
                _toast("Application status updated to Submitted.", "success")
            except (ValueError, IndexError):
                _toast("Could not update application status.", "error")
            except Exception:
                _toast("Could not update application status.", "error")


if __name__ == "__main__":
    main()
