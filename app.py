"""Streamlit UI for the job-vacancy-filter application."""

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
from src.data_loader import load_jobs, normalize_jobs
from src.export_excel import dataframe_to_excel_bytes
from src.filters import JobFilters, apply_filters
from src.paste_jobs import parse_pasted_jobs
from src.profile import UserProfile, load_profile, save_profile
from src.scoring import calculate_match_score

DATABASE_PATH = DEFAULT_DATABASE_PATH
WORK_MODE_OPTIONS = ["Any", "remote", "hybrid", "onsite"]
JOB_LEVEL_OPTIONS = ["Any", "internship", "entry", "junior", "mid", "senior", "lead", "manager"]
COVER_LETTER_TONES = ["formal", "concise", "confident"]


def _parse_optional_float(value: str, field_label: str) -> float | None:
    """Parse a numeric input string into a float or raise a friendly error."""
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field_label} must be a valid number.") from exc


def _load_jobs_dataframe(uploaded_file: object | None) -> pd.DataFrame:
    """Load job data and ensure application tracking columns exist."""
    jobs = load_jobs(uploaded_file=uploaded_file)
    jobs = ensure_application_columns(jobs)
    return apply_saved_application_statuses(jobs, path=DATABASE_PATH)


def _load_pasted_jobs_dataframe(pasted_text: str) -> pd.DataFrame:
    """Parse pasted lowongan text and ensure application tracking columns exist."""
    jobs = parse_pasted_jobs(pasted_text)
    jobs = ensure_application_columns(jobs)
    return apply_saved_application_statuses(jobs, path=DATABASE_PATH)


def _prepare_pasted_preview_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize an editable pasted-jobs preview DataFrame."""
    normalized = normalize_jobs(dataframe)
    normalized = ensure_application_columns(normalized)
    return apply_saved_application_statuses(normalized, path=DATABASE_PATH)


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
    company: str,
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
        company=company,
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
    if "jobs_df" in st.session_state:
        st.session_state.jobs_df = update_application_status(
            st.session_state.jobs_df,
            row_index,
            status,
        )
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
    col1.metric("Total jobs loaded", total_jobs)
    col2.metric("Results found", len(results_df))
    col3.metric("Average match score", f"{average_score:.1f}")


def main() -> None:
    """Run the Streamlit app."""
    st.set_page_config(page_title="Job Vacancy Filter", layout="wide")
    st.title("Job Vacancy Filter")
    st.caption("Manual-assisted job filtering and application preparation. No auto-submit, scraping, or CAPTCHA bypass.")
    try:
        init_database(DATABASE_PATH)
    except Exception:
        st.error("We could not initialize the local application database. Please check file permissions and try again.")
        return

    if "profile" not in st.session_state:
        try:
            st.session_state.profile = load_profile(DATABASE_PATH)
        except Exception:
            st.session_state.profile = UserProfile()
            st.warning("We could not load the saved profile from the local database, so the form started empty.")
    if "jobs_df" not in st.session_state:
        st.session_state.jobs_df = pd.DataFrame()
    if "results_df" not in st.session_state:
        st.session_state.results_df = pd.DataFrame()
    if "cover_letter_text" not in st.session_state:
        st.session_state.cover_letter_text = ""
    if "selected_job_index" not in st.session_state:
        st.session_state.selected_job_index = None
    if "data_source_name" not in st.session_state:
        st.session_state.data_source_name = None
    if "pasted_jobs_df" not in st.session_state:
        st.session_state.pasted_jobs_df = pd.DataFrame()
    if "pasted_jobs_text" not in st.session_state:
        st.session_state.pasted_jobs_text = ""
    if "pasted_jobs_preview_df" not in st.session_state:
        st.session_state.pasted_jobs_preview_df = pd.DataFrame()
    if "cv_analysis" not in st.session_state:
        st.session_state.cv_analysis = CVAnalysis()
    if "cv_file_name" not in st.session_state:
        st.session_state.cv_file_name = ""
    if "cover_letter_tone" not in st.session_state:
        st.session_state.cover_letter_tone = "formal"
    if "cover_letter_custom_prompt" not in st.session_state:
        st.session_state.cover_letter_custom_prompt = ""

    with st.sidebar:
        st.header("Data Source")
        uploaded_file = st.file_uploader(
            "Upload CSV or Excel",
            type=["csv", "xlsx", "xls"],
            key="jobs_file_uploader",
        )
        pasted_jobs_text = st.text_area(
            "Paste lowongan text",
            value=st.session_state.pasted_jobs_text,
            height=180,
            help=(
                "Pisahkan setiap lowongan dengan satu baris kosong. Anda bisa paste blok teks biasa "
                "atau format berlabel seperti Company:, Location:, Skills:, Apply URL:."
            ),
        )
        import_pasted_jobs_clicked = st.button("Use Pasted Jobs", width="stretch")
        clear_pasted_jobs_clicked = st.button("Clear Pasted Jobs", width="stretch")

        st.header("Filters")
        keyword = st.text_input("Keyword / Job title")
        company = st.text_input("Company")
        location = st.text_input("Location")
        work_mode = st.selectbox("Work mode", WORK_MODE_OPTIONS)
        job_level = st.selectbox("Job level", JOB_LEVEL_OPTIONS)
        minimum_salary_text = st.text_input("Minimum salary")
        maximum_salary_text = st.text_input("Maximum salary")
        skills_text = st.text_input("Skills comma-separated")
        posted_after = st.date_input("Posted after", value=None)
        include_unknown_salary = st.checkbox("Include jobs with unknown salary", value=True)
        search_clicked = st.button("Search", width="stretch")

        st.divider()
        st.header("Profile")
        with st.form("profile_form"):
            profile_name = st.text_input("Name", value=st.session_state.profile.name)
            profile_email = st.text_input("Email", value=st.session_state.profile.email)
            profile_phone = st.text_input("Phone", value=st.session_state.profile.phone)
            profile_linkedin = st.text_input(
                "LinkedIn URL",
                value=st.session_state.profile.linkedin_url,
            )
            profile_portfolio = st.text_input(
                "Portfolio URL",
                value=st.session_state.profile.portfolio_url,
            )
            save_profile_clicked = st.form_submit_button("Save Profile", width="stretch")

        cv_uploaded_file = st.file_uploader(
            "Upload CV",
            type=["pdf", "docx"],
            key="cv_uploader",
        )
        use_cv_profile_clicked = st.button("Use CV Details in Profile", width="stretch")

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
            st.sidebar.error("Could not save the profile to the local database. Please try again.")

    if cv_uploaded_file is not None and st.session_state.cv_file_name != cv_uploaded_file.name:
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
            st.sidebar.error("We could not read that CV file. Please try another PDF or DOCX.")
    elif cv_uploaded_file is None and st.session_state.cv_file_name:
        st.session_state.cv_analysis = CVAnalysis()
        st.session_state.cv_file_name = ""

    if use_cv_profile_clicked:
        if st.session_state.cv_analysis.text:
            st.session_state.profile = _merge_profile_with_cv(
                st.session_state.profile,
                st.session_state.cv_analysis,
            )
            st.sidebar.success("Profile fields were filled from the uploaded CV when available.")
        else:
            st.sidebar.error("Upload a readable CV first before using CV details.")

    st.session_state.pasted_jobs_text = pasted_jobs_text
    if clear_pasted_jobs_clicked:
        st.session_state.pasted_jobs_df = pd.DataFrame()
        st.session_state.pasted_jobs_preview_df = pd.DataFrame()
        st.session_state.pasted_jobs_text = ""
        if uploaded_file is None:
            st.session_state.data_source_name = None
        st.sidebar.success("Pasted jobs cleared.")

    if import_pasted_jobs_clicked:
        try:
            st.session_state.pasted_jobs_preview_df = _load_pasted_jobs_dataframe(pasted_jobs_text)
            st.sidebar.success(
                f"Parsed {len(st.session_state.pasted_jobs_preview_df)} pasted lowongan. Review and edit the preview below, then apply it."
            )
        except ValueError as exc:
            st.sidebar.error(str(exc))
        except Exception:
            st.sidebar.error("We could not parse the pasted lowongan text. Please try a cleaner format.")

    if uploaded_file is not None:
        data_source_name = uploaded_file.name
    elif not st.session_state.pasted_jobs_df.empty:
        data_source_name = "pasted_jobs"
    else:
        data_source_name = "data/sample_jobs.csv"

    if not st.session_state.pasted_jobs_preview_df.empty:
        st.subheader("Pasted Jobs Preview")
        st.caption("Review and edit parsed lowongan before using them as the active data source.")
        edited_preview_df = st.data_editor(
            st.session_state.pasted_jobs_preview_df,
            width="stretch",
            num_rows="dynamic",
            hide_index=True,
            key="pasted_jobs_preview_editor",
        )
        preview_actions_col1, preview_actions_col2 = st.columns(2)
        apply_pasted_preview_clicked = preview_actions_col1.button(
            "Apply Edited Pasted Jobs",
            width="stretch",
        )
        discard_pasted_preview_clicked = preview_actions_col2.button(
            "Discard Preview",
            width="stretch",
        )

        if discard_pasted_preview_clicked:
            st.session_state.pasted_jobs_preview_df = pd.DataFrame()
            st.success("Pasted jobs preview discarded.")
        elif apply_pasted_preview_clicked:
            try:
                st.session_state.pasted_jobs_df = _prepare_pasted_preview_dataframe(edited_preview_df)
                st.session_state.pasted_jobs_preview_df = st.session_state.pasted_jobs_df.copy()
                st.session_state.jobs_df = st.session_state.pasted_jobs_df.copy()
                st.session_state.results_df = pd.DataFrame()
                st.session_state.cover_letter_text = ""
                st.session_state.selected_job_index = None
                st.session_state.data_source_name = "pasted_jobs"
                data_source_name = "pasted_jobs"
                st.success(
                    f"Using {len(st.session_state.pasted_jobs_df)} edited pasted lowongan as the active data source."
                )
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("We could not apply the edited pasted jobs. Please review the preview values and try again.")

    if data_source_name == "pasted_jobs":
        st.session_state.jobs_df = st.session_state.pasted_jobs_df.copy()
    elif st.session_state.data_source_name != data_source_name or st.session_state.jobs_df.empty:
        try:
            st.session_state.jobs_df = _load_jobs_dataframe(uploaded_file)
            st.session_state.results_df = pd.DataFrame()
            st.session_state.cover_letter_text = ""
            st.session_state.selected_job_index = None
            st.session_state.data_source_name = data_source_name
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception:
            st.error("We could not load the job data. Please check your file and try again.")
            return

    st.caption(f"Active data source: `{data_source_name}`")

    if st.session_state.cv_analysis.text:
        with st.sidebar:
            st.subheader("CV Insights")
            if st.session_state.cv_analysis.name:
                st.write(f"Name: {st.session_state.cv_analysis.name}")
            if st.session_state.cv_analysis.email:
                st.write(f"Email: {st.session_state.cv_analysis.email}")
            if st.session_state.cv_analysis.phone:
                st.write(f"Phone: {st.session_state.cv_analysis.phone}")
            if st.session_state.cv_analysis.linkedin_url:
                st.write(f"LinkedIn: {st.session_state.cv_analysis.linkedin_url}")
            if st.session_state.cv_analysis.portfolio_url:
                st.write(f"Portfolio: {st.session_state.cv_analysis.portfolio_url}")
            if st.session_state.cv_analysis.skills:
                st.write("Detected skills:")
                st.caption(", ".join(st.session_state.cv_analysis.skills))

    if search_clicked or st.session_state.results_df.empty:
        try:
            active_filters = _build_job_filters(
                keyword=keyword,
                company=company,
                location=location,
                work_mode=work_mode,
                job_level=job_level,
                minimum_salary_text=minimum_salary_text,
                maximum_salary_text=maximum_salary_text,
                skills_text=skills_text,
                posted_after=posted_after,
                include_unknown_salary=include_unknown_salary,
            )
            filtered = apply_filters(st.session_state.jobs_df, active_filters)
            st.session_state.results_df = calculate_match_score(filtered, active_filters)
        except ValueError as exc:
            st.error(f"Please review your filter inputs: {exc}")
            st.session_state.results_df = pd.DataFrame()
        except Exception:
            st.error("We could not process the search. Please review your filters and try again.")
            st.session_state.results_df = pd.DataFrame()

    results_df = st.session_state.results_df.copy()
    _render_results_metrics(results_df, len(st.session_state.jobs_df))

    st.subheader("Filtered Results")
    st.dataframe(results_df, width="stretch", hide_index=False)

    try:
        excel_bytes = dataframe_to_excel_bytes(results_df)
        st.download_button(
            "Download Excel",
            data=excel_bytes,
            file_name="filtered_jobs.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=results_df.empty,
        )
    except Exception:
        st.error("We could not prepare the Excel export right now.")

    st.divider()
    st.subheader("Application Assistant")
    st.caption("This flow only helps you prepare applications manually. It does not auto-submit and does not scrape job sites.")

    if results_df.empty:
        st.info("Run a search to prepare an application from the filtered results.")
        return

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
            st.info(f"Matched CV skills for this job: {', '.join(skill_match.matched)}")
        else:
            st.info("CV uploaded, but no direct skill overlap was detected for this selected job yet.")
        if skill_match.inferred_job_skills:
            st.caption(f"Detected job skills: {', '.join(skill_match.inferred_job_skills)}")
        if skill_match.missing:
            st.warning(f"Job skills not detected in CV yet: {', '.join(skill_match.missing)}")

    prepare_clicked = st.button("Prepare Application")
    if prepare_clicked:
        try:
            st.session_state.cover_letter_text = generate_cover_letter(
                selected_job,
                st.session_state.profile,
                matched_skills=skill_match.matched if skill_match is not None else None,
                missing_skills=skill_match.missing if skill_match is not None else None,
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
