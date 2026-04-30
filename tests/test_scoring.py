"""Tests for job vacancy scoring helpers."""

from __future__ import annotations

import pandas as pd

from src.filters import JobFilters
from src.scoring import calculate_match_score


def test_match_score_column_is_added() -> None:
    dataframe = pd.DataFrame([{"job_title": "Data Analyst", "company": "Acme"}])

    result = calculate_match_score(dataframe, JobFilters())

    assert "match_score" in result.columns
    assert result.iloc[0]["match_score"] == 0


def test_keyword_match_gives_25_points() -> None:
    dataframe = pd.DataFrame(
        [{"job_title": "Python Developer", "company": "Acme", "description": ""}]
    )

    result = calculate_match_score(dataframe, JobFilters(keyword="python"))

    assert result.iloc[0]["match_score"] == 25


def test_location_match_gives_15_points() -> None:
    dataframe = pd.DataFrame(
        [{"job_title": "Backend Engineer", "company": "Acme", "location": "Jakarta"}]
    )

    result = calculate_match_score(dataframe, JobFilters(location="jakarta"))

    assert result.iloc[0]["match_score"] == 15


def test_work_mode_match_gives_15_points() -> None:
    dataframe = pd.DataFrame(
        [{"job_title": "Backend Engineer", "company": "Acme", "work_mode": "Remote"}]
    )

    result = calculate_match_score(dataframe, JobFilters(work_mode="remote"))

    assert result.iloc[0]["match_score"] == 15


def test_job_level_match_gives_10_points() -> None:
    dataframe = pd.DataFrame(
        [{"job_title": "Backend Engineer", "company": "Acme", "job_level": "Senior"}]
    )

    result = calculate_match_score(dataframe, JobFilters(job_level="senior"))

    assert result.iloc[0]["match_score"] == 10


def test_salary_suitable_gives_15_points() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "job_title": "Backend Engineer",
                "company": "Acme",
                "salary_min": 20_000_000,
                "salary_max": 30_000_000,
            }
        ]
    )

    result = calculate_match_score(dataframe, JobFilters(salary_min=25_000_000))

    assert result.iloc[0]["match_score"] == 15


def test_skill_points_are_5_each_and_capped_at_20() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "job_title": "Platform Engineer",
                "company": "Acme",
                "skills": "Python;SQL;AWS;Docker;FastAPI",
                "description": "Build services with PostgreSQL too.",
            }
        ]
    )

    result = calculate_match_score(
        dataframe,
        JobFilters(skills=["python", "sql", "aws", "docker", "fastapi"]),
    )

    assert result.iloc[0]["match_score"] == 20


def test_results_are_sorted_by_match_score_descending() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "job_title": "Low Match",
                "company": "Acme",
                "description": "",
                "posted_date": "2026-04-10",
            },
            {
                "job_title": "High Match",
                "company": "Beta",
                "description": "Python work in Jakarta",
                "location": "Jakarta",
                "posted_date": "2026-04-05",
            },
        ]
    )

    result = calculate_match_score(
        dataframe,
        JobFilters(keyword="python", location="jakarta"),
    )

    assert result["job_title"].tolist() == ["High Match", "Low Match"]


def test_unknown_salary_does_not_receive_salary_points() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "job_title": "Backend Engineer",
                "company": "Acme",
                "salary_min": None,
                "salary_max": None,
            }
        ]
    )

    result = calculate_match_score(dataframe, JobFilters(salary_min=10_000_000))

    assert result.iloc[0]["match_score"] == 0
