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
from src.cv_parser import CVAnalysis, analyze_cv_bytes, match_cv_skills_to_job
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
   Design System: Swiss Modernism + Professional Blue
   Palette: Financial Dashboard (OLED dark) + Job Board blue
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Light mode ───────────────────────────────────────────────────── */
:root,
body.light-theme {
    --primary: #0369A1;
    --primary-hover: #0284C7;
    --primary-bg: #F0F9FF;
    --accent: #16A34A;
    --accent-bg: #DCFCE7;
    --text: #0C4A6E;
    --text-heading: #0369A1;
    --text-muted: #64748B;
    --border: #BAE6FD;
    --border-subtle: #E7EFF5;
    --input-bg: #FFFFFF;
    --sidebar-bg-start: #F0F9FF;
    --sidebar-bg-end: #FFFFFF;
    --badge-inactive-bg: #F1F5F9;
    --focus-ring: rgba(3, 105, 161, 0.15);
    --divider: #BAE6FD;
    --btn-text: #FFFFFF;
}

/* ── Dark mode ────────────────────────────────────────────────────── */
body.dark-theme {
    --primary: #38BDF8;
    --primary-hover: #7DD3FC;
    --primary-bg: rgba(14, 165, 233, 0.1);
    --accent: #4ADE80;
    --accent-bg: rgba(74, 222, 128, 0.15);
    --text: #E2E8F0;
    --text-heading: #BAE6FD;
    --text-muted: #94A3B8;
    --border: #1E3A5F;
    --border-subtle: #1E293B;
    --input-bg: #1E293B;
    --sidebar-bg-start: #0B1623;
    --sidebar-bg-end: #0F1D2E;
    --badge-inactive-bg: #1E293B;
    --focus-ring: rgba(56, 189, 248, 0.25);
    --divider: #1E3A5F;
    --btn-text: #0F172A;
}

/* ═════════════════════════════════════════════════════════════════════
   FORCE DARK MODE — override Streamlit's internal variables
   ═════════════════════════════════════════════════════════════════════ */
body.dark-theme section[data-testid="stSidebar"] {
    --sidebar-background-color: #0B1623 !important;
    background: linear-gradient(180deg, #0B1623 0%, #0F1D2E 100%) !important;
    background-color: #0B1623 !important;
    border-right: 1px solid #1E293B !important;
}
body.dark-theme section[data-testid="stSidebar"] * {
    color-scheme: dark !important;
}
body.dark-theme section[data-testid="stSidebar"] .st-emotion-cache-6qob1r,
body.dark-theme section[data-testid="stSidebar"] .st-emotion-cache-1cypcdb,
body.dark-theme section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    background: transparent !important;
}

/* ── Sidebar section headers ── */
section[data-testid="stSidebar"] .stMarkdown h2 {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    color: var(--text-heading) !important;
    margin-top: 1.25rem !important;
    margin-bottom: 0.5rem !important;
    padding-bottom: 0.3rem !important;
    border-bottom: 2px solid var(--border) !important;
}
body.dark-theme section[data-testid="stSidebar"] .stMarkdown h2 {
    color: #BAE6FD !important;
    border-bottom-color: #1E3A5F !important;
}

/* ── Text ── */
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span {
    color: var(--text) !important;
}
body.dark-theme section[data-testid="stSidebar"] .stMarkdown p,
body.dark-theme section[data-testid="stSidebar"] .stMarkdown span,
body.dark-theme section[data-testid="stSidebar"] label {
    color: #E2E8F0 !important;
}
body.dark-theme section[data-testid="stSidebar"] .stCaption,
body.dark-theme section[data-testid="stSidebar"] .stCaption p {
    color: #94A3B8 !important;
}

/* ── Inputs ── */
section[data-testid="stSidebar"] input[type="text"],
section[data-testid="stSidebar"] input[type="password"] {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    padding: 0.4rem 0.6rem !important;
    font-size: 0.85rem !important;
    background: var(--input-bg) !important;
    color: var(--text) !important;
}
body.dark-theme section[data-testid="stSidebar"] input[type="text"],
body.dark-theme section[data-testid="stSidebar"] input[type="password"] {
    background: #1E293B !important;
    border-color: #1E3A5F !important;
    color: #E2E8F0 !important;
}
body.dark-theme section[data-testid="stSidebar"] input::placeholder {
    color: #64748B !important;
    opacity: 0.7 !important;
}
section[data-testid="stSidebar"] input:focus {
    box-shadow: 0 0 0 2px var(--focus-ring) !important;
    outline: none !important;
}
body.dark-theme section[data-testid="stSidebar"] input:focus {
    border-color: #38BDF8 !important;
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25) !important;
}

/* ── Select ── */
body.dark-theme section[data-testid="stSidebar"] [data-baseweb="select"] {
    background: #1E293B !important;
}
body.dark-theme section[data-testid="stSidebar"] [data-baseweb="select"] * {
    color: #E2E8F0 !important;
}

/* ── Primary button ── */
section[data-testid="stSidebar"] button[kind="primary"] {
    background: var(--primary) !important;
    border: none !important;
    border-radius: 6px !important;
    color: var(--btn-text) !important;
    font-weight: 600 !important;
    transition: background 0.2s !important;
}
section[data-testid="stSidebar"] button[kind="primary"]:hover {
    background: var(--primary-hover) !important;
}

/* ── Secondary buttons ── */
section[data-testid="stSidebar"] button[kind="secondary"],
section[data-testid="stSidebar"] button[kind="secondaryFormSubmit"] {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--primary) !important;
    background: transparent !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}
body.dark-theme section[data-testid="stSidebar"] button[kind="secondary"],
body.dark-theme section[data-testid="stSidebar"] button[kind="secondaryFormSubmit"] {
    border-color: #1E3A5F !important;
    color: #38BDF8 !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover,
section[data-testid="stSidebar"] button[kind="secondaryFormSubmit"]:hover {
    border-color: var(--primary) !important;
    background: var(--primary-bg) !important;
}

/* ── Divider ── */
section[data-testid="stSidebar"] hr {
    border-color: var(--divider) !important;
}

/* ── Checkbox ── */
body.dark-theme section[data-testid="stSidebar"] .stCheckbox label {
    color: #E2E8F0 !important;
}

/* ── Expander ── */
body.dark-theme section[data-testid="stSidebar"] .streamlit-expanderHeader {
    background: #1E293B !important;
    border-color: #1E3A5F !important;
    color: #94A3B8 !important;
}
body.dark-theme section[data-testid="stSidebar"] .streamlit-expanderHeader svg {
    fill: #94A3B8 !important;
}
body.dark-theme section[data-testid="stSidebar"] .streamlit-expanderContent {
    background: transparent !important;
}

/* ── Status badge ── */
.ai-status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    vertical-align: middle;
    margin-left: 6px;
}
.ai-status-active { background: var(--accent-bg); color: var(--accent); }
.ai-status-inactive { background: var(--badge-inactive-bg); color: var(--text-muted); }

/* ── File uploader ── */
body.dark-theme section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    background: #1E293B !important;
    border-color: #1E3A5F !important;
}
body.dark-theme section[data-testid="stSidebar"] [data-testid="stFileUploader"] * {
    color: #E2E8F0 !important;
}
body.dark-theme section[data-testid="stSidebar"] [data-testid="stFileUploader"] small {
    color: #94A3B8 !important;
}

/* ── Scrollbar ── */
body.dark-theme section[data-testid="stSidebar"] ::-webkit-scrollbar-track {
    background: #0B1623 !important;
}
body.dark-theme section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
    background: #1E3A5F !important;
    border-radius: 4px !important;
}

/* ── Main area fixes ── */
body.dark-theme .stDataFrame {
    border-color: #1E293B !important;
}
body.dark-theme .stDownloadButton button {
    background: transparent !important;
    border-color: #1E3A5F !important;
    color: #38BDF8 !important;
}
body.dark-theme .stDownloadButton button:hover {
    border-color: #38BDF8 !important;
    background: rgba(14, 165, 233, 0.1) !important;
}
</style>

<script>
(function(){
    function applyTheme() {
        var mqDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        var sidebar = document.querySelector('section[data-testid="stSidebar"]');
        var sidebarBg = sidebar ? getComputedStyle(sidebar).backgroundColor : '';
        /* Parse RGB values — if dark, channel values are low */
        var nums = sidebarBg.match(/\\d+/g);
        var avg = nums ? nums.reduce(function(a,b){return +a+ +b;},0)/nums.length : 255;
        var isStreamlitDark = avg < 80;
        var isDark = mqDark || isStreamlitDark;
        document.body.classList.toggle('dark-theme', isDark);
        document.body.classList.toggle('light-theme', !isDark);
    }
    applyTheme();
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);
    new MutationObserver(applyTheme).observe(document.body, {attributes: true, attributeFilter: ['class']});
    setTimeout(applyTheme, 300);
    setTimeout(applyTheme, 800);
    setTimeout(applyTheme, 2000);
})();
</script>
"""


def _inject_custom_css() -> None:
    """Inject the custom design system CSS into the Streamlit app."""
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


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
        "AI-powered job search across LinkedIn Indonesia. "
        "Manual-assisted filtering and application preparation."
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
    # SIDEBAR
    # ══════════════════════════════════════════════════════════════════════
    with st.sidebar:
        # ── Search Section ───────────────────────────────────────────────
        st.markdown("## Search Filters")
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

        st.divider()

        # ── Profile Section ──────────────────────────────────────────────
        st.markdown("## Profile")
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
            st.sidebar.success("Profile saved locally to SQLite.")
        except Exception:
            st.sidebar.error(
                "Could not save the profile to the local database. Please try again."
            )

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
            st.sidebar.success("CV analyzed successfully.")
        except ValueError as exc:
            st.session_state.cv_analysis = CVAnalysis()
            st.session_state.cv_file_name = ""
            st.sidebar.error(str(exc))
        except Exception:
            st.session_state.cv_analysis = CVAnalysis()
            st.session_state.cv_file_name = ""
            st.sidebar.error(
                "We could not read that CV file. Please try another PDF or DOCX."
            )
    elif cv_uploaded_file is None and st.session_state.cv_file_name:
        st.session_state.cv_analysis = CVAnalysis()
        st.session_state.cv_file_name = ""

    if use_cv_profile_clicked:
        if st.session_state.cv_analysis.text:
            st.session_state.profile = _merge_profile_with_cv(
                st.session_state.profile,
                st.session_state.cv_analysis,
            )
            st.sidebar.success(
                "Profile fields were filled from the uploaded CV when available."
            )
        else:
            st.sidebar.error("Upload a readable CV first before using CV details.")

    # ── CV insights (sidebar) ───────────────────────────────────────────
    if st.session_state.cv_analysis.text:
        with st.sidebar:
            st.divider()
            st.markdown("## CV Insights")
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
        st.divider()
        ai_status = "Active" if st.session_state.llm_config.is_configured else "Inactive"
        ai_badge = "ai-status-active" if st.session_state.llm_config.is_configured else "ai-status-inactive"
        st.markdown(
            f"## AI Settings "
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
            st.sidebar.success("AI config saved!")
        except Exception:
            st.sidebar.error("Could not save AI config.")

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
            with st.spinner("🔍 AI searching for jobs across platforms..."):
                raw_jobs = search_jobs(active_filters)

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
                st.warning(
                    "No jobs matched your filters. "
                    "Try broadening your keyword or location."
                )
            else:
                st.success(
                    f"Found {len(raw_jobs)} jobs — {len(scored)} matched your filters."
                )
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error(
                "AI search failed. Check your internet connection and try again."
            )

    results_df = st.session_state.results_df.copy()

    # ══════════════════════════════════════════════════════════════════════
    # RESULTS
    # ══════════════════════════════════════════════════════════════════════
    if results_df.empty:
        st.info(
            "👆 Fill in at least a keyword or location in the sidebar, "
            "then click **AI Search Jobs** to find vacancies."
        )
        return

    _render_results_metrics(results_df, st.session_state.last_search_count)

    st.subheader("📋 Filtered Results")
    st.dataframe(results_df, width="stretch", hide_index=False)

    try:
        excel_bytes = dataframe_to_excel_bytes(results_df)
        st.download_button(
            "Download Excel",
            data=excel_bytes,
            file_name="filtered_jobs.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        st.error("We could not prepare the Excel export right now.")

    # ══════════════════════════════════════════════════════════════════════
    # APPLICATION ASSISTANT
    # ══════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("📝 Application Assistant")
    st.caption(
        "This flow only helps you prepare applications manually. "
        "It does not auto-submit and does not scrape job sites."
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
            st.error("We could not prepare the application draft right now.")

    cover_letter_text = st.text_area(
        "Generated cover letter",
        value=st.session_state.cover_letter_text,
        height=260,
    )
    st.session_state.cover_letter_text = cover_letter_text

    st.download_button(
        "Download Cover Letter",
        data=cover_letter_text.encode("utf-8"),
        file_name="cover_letter.txt",
        mime="text/plain",
        disabled=not cover_letter_text.strip(),
    )

    apply_url = str(selected_job.get("apply_url", "") or "").strip()
    if apply_url:
        st.link_button("Open Apply Link", url=apply_url)
    else:
        st.info("No apply link is available for this job.")

    if st.button("Mark as Submitted"):
        try:
            _sync_status_to_state(selected_job_index, "Submitted")
            _persist_selected_job_status(selected_job, "Submitted")
            st.success("Application status updated to Submitted.")
        except (ValueError, IndexError):
            st.error("We could not update the application status for that job.")
        except Exception:
            st.error("We could not update the application status right now.")


if __name__ == "__main__":
    main()
