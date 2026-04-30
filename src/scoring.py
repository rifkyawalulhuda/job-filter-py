"""Scoring helpers for ranking job vacancies."""

from __future__ import annotations

import pandas as pd

from src.filters import JobFilters


def _text_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a string series for scoring, defaulting to empty strings."""
    if column in df.columns:
        return df[column].fillna("").astype(str)
    return pd.Series("", index=df.index, dtype="object")


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a numeric series for scoring, defaulting to NaN values."""
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce")
    return pd.Series(float("nan"), index=df.index, dtype="float64")


def _normalize(value: str) -> str:
    """Normalize text for case-insensitive exact comparisons."""
    return value.strip().casefold()


def _contains_partial(series: pd.Series, value: str) -> pd.Series:
    """Return a case-insensitive partial-match mask."""
    return series.fillna("").astype(str).str.contains(value, case=False, regex=False)


def calculate_match_score(df: pd.DataFrame, filters: JobFilters) -> pd.DataFrame:
    """Calculate weighted match scores for job vacancies.

    Parameters
    ----------
    df:
        The source job vacancy DataFrame.
    filters:
        The active user filters used to score relevance.

    Returns
    -------
    pandas.DataFrame
        A new DataFrame with a ``match_score`` column and sorted results.
    """
    scored = df.copy()
    scored["match_score"] = 0

    job_title = _text_series(scored, "job_title")
    description = _text_series(scored, "description")
    location = _text_series(scored, "location")
    work_mode = _text_series(scored, "work_mode")
    job_level = _text_series(scored, "job_level")
    skills = _text_series(scored, "skills")
    salary_min = _numeric_series(scored, "salary_min")
    salary_max = _numeric_series(scored, "salary_max")

    if filters.keyword.strip():
        keyword_mask = _contains_partial(job_title, filters.keyword) | _contains_partial(
            description, filters.keyword
        )
        scored["match_score"] += keyword_mask.astype(int) * 25

    if filters.location.strip():
        location_mask = _contains_partial(location, filters.location)
        scored["match_score"] += location_mask.astype(int) * 15

    if filters.work_mode.strip() and _normalize(filters.work_mode) != "any":
        work_mode_mask = work_mode.map(_normalize) == _normalize(filters.work_mode)
        scored["match_score"] += work_mode_mask.astype(int) * 15

    if filters.job_level.strip() and _normalize(filters.job_level) != "any":
        job_level_mask = job_level.map(_normalize) == _normalize(filters.job_level)
        scored["match_score"] += job_level_mask.astype(int) * 10

    salary_known = salary_min.notna() & salary_max.notna()
    salary_suitable = pd.Series(False, index=scored.index)
    if filters.salary_min is not None:
        salary_suitable |= (salary_max >= filters.salary_min) | (salary_min >= filters.salary_min)
    if filters.salary_max is not None:
        salary_suitable |= salary_min <= filters.salary_max
    if filters.salary_min is not None or filters.salary_max is not None:
        scored["match_score"] += (salary_suitable & salary_known).astype(int) * 15

    active_skills = [skill.strip() for skill in filters.skills if skill.strip()]
    if active_skills:
        searchable_text = (skills + " " + description).str.casefold()
        skill_points = pd.Series(0, index=scored.index, dtype="int64")
        for skill in active_skills:
            skill_mask = searchable_text.str.contains(skill.casefold(), regex=False)
            skill_points += skill_mask.astype(int) * 5
        scored["match_score"] += skill_points.clip(upper=20)

    posted_date = (
        pd.to_datetime(scored["posted_date"], errors="coerce")
        if "posted_date" in scored.columns
        else pd.Series(pd.NaT, index=scored.index, dtype="datetime64[ns]")
    )
    scored["_posted_date_sort"] = posted_date
    scored["_job_title_sort"] = job_title

    sorted_df = scored.sort_values(
        by=["match_score", "_posted_date_sort", "_job_title_sort"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",
    )
    return sorted_df.drop(columns=["_posted_date_sort", "_job_title_sort"]).copy()
