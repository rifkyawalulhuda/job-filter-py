"""Tests for job vacancy filtering helpers."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.filters import JobFilters, apply_filters


def _jobs_dataframe() -> pd.DataFrame:
    """Create an in-memory dataset for filter tests."""
    return pd.DataFrame(
        [
            {
                "job_title": "Python Developer",
                "company": "Acme",
                "location": "Jakarta",
                "work_mode": "remote",
                "job_level": "junior",
                "salary_min": 8_000_000,
                "salary_max": 12_000_000,
                "skills": "Python;SQL",
                "posted_date": pd.Timestamp("2026-04-20"),
                "description": "Build internal data tools.",
            },
            {
                "job_title": "Backend Engineer",
                "company": "Beta",
                "location": "Bandung",
                "work_mode": "hybrid",
                "job_level": "mid",
                "salary_min": 15_000_000,
                "salary_max": 22_000_000,
                "skills": "FastAPI;Docker",
                "posted_date": pd.Timestamp("2026-04-25"),
                "description": "Work on Python APIs and distributed systems.",
            },
            {
                "job_title": "Frontend Engineer",
                "company": "Gamma",
                "location": "Surabaya",
                "work_mode": "onsite",
                "job_level": "senior",
                "salary_min": None,
                "salary_max": None,
                "skills": "React;JavaScript",
                "posted_date": pd.Timestamp("2026-04-10"),
                "description": "Build React dashboards and collaborate with design.",
            },
            {
                "job_title": "Data Analyst",
                "company": "Delta",
                "location": "Jakarta",
                "work_mode": "remote",
                "job_level": "entry",
                "salary_min": 6_000_000,
                "salary_max": 9_000_000,
                "skills": "Excel",
                "posted_date": pd.Timestamp("2026-04-05"),
                "description": "SQL reporting and business analysis.",
            },
        ]
    )


def test_keyword_filtering_matches_job_title() -> None:
    # Keyword matching is token-based: "python developer" matches the exact
    # "Python Developer" title (Acme) AND any listing mentioning a token, e.g.
    # "Beta" whose description mentions "Python". This broad matching keeps
    # relevant multi-platform results that lack a rich description from being
    # dropped.
    result = apply_filters(_jobs_dataframe(), JobFilters(keyword="python developer"))

    assert result["company"].tolist() == ["Acme", "Beta"]


def test_keyword_filtering_single_token_is_strict() -> None:
    # A single-word keyword still only matches rows containing that word.
    result = apply_filters(_jobs_dataframe(), JobFilters(keyword="frontend"))

    assert result["company"].tolist() == ["Gamma"]


def test_location_filter_keeps_rows_with_unknown_location() -> None:
    # Rows with an empty location (common for Glints/Kalibrr/Indeed results)
    # must pass the location filter instead of being dropped.
    jobs = _jobs_dataframe()
    jobs.loc[1, "location"] = ""  # Beta now has unknown location
    result = apply_filters(jobs, JobFilters(location="Jakarta"))

    assert set(result["company"].tolist()) == {"Acme", "Beta", "Delta"}


def test_work_mode_filter_keeps_rows_with_unknown_work_mode() -> None:
    jobs = _jobs_dataframe()
    jobs.loc[0, "work_mode"] = ""  # Acme now has unknown work mode
    result = apply_filters(jobs, JobFilters(work_mode="hybrid"))

    # Beta (hybrid) plus Acme (unknown) pass; explicit remote/onsite are dropped.
    assert set(result["company"].tolist()) == {"Acme", "Beta"}


def test_keyword_filtering_matches_description() -> None:
    result = apply_filters(_jobs_dataframe(), JobFilters(keyword="distributed systems"))

    assert result["company"].tolist() == ["Beta"]


def test_location_filtering_works_case_insensitive() -> None:
    result = apply_filters(_jobs_dataframe(), JobFilters(location="jAkArTa"))

    assert result["company"].tolist() == ["Acme", "Delta"]


def test_work_mode_filtering_works() -> None:
    result = apply_filters(_jobs_dataframe(), JobFilters(work_mode="hybrid"))

    assert result["company"].tolist() == ["Beta"]


def test_job_level_filtering_works() -> None:
    result = apply_filters(_jobs_dataframe(), JobFilters(job_level="senior"))

    assert result["company"].tolist() == ["Gamma"]


def test_salary_min_filtering_works() -> None:
    result = apply_filters(
        _jobs_dataframe(),
        JobFilters(salary_min=10_000_000, include_unknown_salary=False),
    )

    assert result["company"].tolist() == ["Acme", "Beta"]


def test_salary_max_filtering_works() -> None:
    result = apply_filters(
        _jobs_dataframe(),
        JobFilters(salary_max=10_000_000, include_unknown_salary=False),
    )

    assert result["company"].tolist() == ["Acme", "Delta"]


def test_unknown_salary_is_included_when_allowed() -> None:
    result = apply_filters(
        _jobs_dataframe(),
        JobFilters(salary_min=20_000_000, include_unknown_salary=True),
    )

    assert result["company"].tolist() == ["Beta", "Gamma"]


def test_unknown_salary_is_excluded_when_not_allowed() -> None:
    result = apply_filters(
        _jobs_dataframe(),
        JobFilters(salary_min=20_000_000, include_unknown_salary=False),
    )

    assert result["company"].tolist() == ["Beta"]


def test_skills_filtering_matches_skills_column() -> None:
    result = apply_filters(_jobs_dataframe(), JobFilters(skills=["javascript"]))

    assert result["company"].tolist() == ["Gamma"]


def test_skills_filtering_matches_description_column() -> None:
    result = apply_filters(_jobs_dataframe(), JobFilters(skills=["sql"]))

    assert result["company"].tolist() == ["Acme", "Delta"]


def test_posted_after_excludes_older_jobs() -> None:
    result = apply_filters(_jobs_dataframe(), JobFilters(posted_after=date(2026, 4, 15)))

    assert result["company"].tolist() == ["Acme", "Beta"]
