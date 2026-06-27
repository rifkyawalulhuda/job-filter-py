"""Filtering helpers for job vacancies."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass(slots=True)
class JobFilters:
    """Container for user-selected job vacancy filter settings."""

    keyword: str = ""
    company: str = ""
    location: str = ""
    work_mode: str = "Any"
    job_level: str = "Any"
    salary_min: float | None = None
    salary_max: float | None = None
    skills: list[str] = field(default_factory=list)
    posted_after: date | None = None
    include_unknown_salary: bool = True


def _contains_partial(series: pd.Series, value: str) -> pd.Series:
    """Return a case-insensitive partial-match mask for a string series."""
    return series.fillna("").astype(str).str.contains(value, case=False, regex=False)


def _keyword_match(series: pd.Series, keyword: str) -> pd.Series:
    """Match a multi-word keyword loosely against a text series.

    A row matches when the full phrase appears OR when ANY individual word
    token appears. This keeps results relevant without dropping clearly
    related listings (e.g. keyword "python developer" still matches a
    "Senior Python Engineer" title). Tokens shorter than 2 chars are ignored.
    """
    text = series.fillna("").astype(str)
    mask = _contains_partial(text, keyword)
    tokens = [t for t in re.split(r"\s+", keyword.strip()) if len(t) >= 2]
    for token in tokens:
        mask |= _contains_partial(text, token)
    return mask


def _normalize_exact(value: str) -> str:
    """Normalize text used for exact-match categorical filtering."""
    return value.strip().casefold()


def _text_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Safely return a text series for a column, defaulting to empty strings."""
    if column in df.columns:
        return df[column].fillna("").astype(str)
    return pd.Series("", index=df.index, dtype="object")


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Safely return a numeric series for a column, coercing invalid values."""
    if column in df.columns:
        return pd.to_numeric(df[column], errors="coerce")
    return pd.Series(float("nan"), index=df.index, dtype="float64")


def _datetime_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Safely return a datetime series for a column, coercing invalid values."""
    if column in df.columns:
        return pd.to_datetime(df[column], errors="coerce")
    return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")


def apply_filters(df: pd.DataFrame, filters: JobFilters) -> pd.DataFrame:
    """Apply job vacancy filters without mutating the original DataFrame.

    Parameters
    ----------
    df:
        Source job vacancy data.
    filters:
        Filter values chosen by the user.

    Returns
    -------
    pandas.DataFrame
        A copy of the filtered DataFrame.
    """
    filtered = df.copy()
    mask = pd.Series(True, index=filtered.index)

    job_title = _text_series(filtered, "job_title")
    description = _text_series(filtered, "description")
    company = _text_series(filtered, "company")
    location = _text_series(filtered, "location")
    skills = _text_series(filtered, "skills")

    if filters.keyword.strip():
        keyword_mask = (
            _keyword_match(job_title, filters.keyword)
            | _keyword_match(description, filters.keyword)
            | _keyword_match(company, filters.keyword)
        )
        mask &= keyword_mask

    if filters.company.strip():
        mask &= _contains_partial(company, filters.company)

    if filters.location.strip():
        # Keep rows whose location matches OR whose location is unknown (empty).
        # Many platforms (Glints, Kalibrr, Indeed) return jobs without a parsed
        # location; dropping them would hide most non-LinkedIn results.
        location_unknown = location.str.strip() == ""
        mask &= _contains_partial(location, filters.location) | location_unknown

    if filters.work_mode.strip() and _normalize_exact(filters.work_mode) != "any":
        work_mode_series = _text_series(filtered, "work_mode").map(_normalize_exact)
        # Unknown (empty) work_mode passes — non-LinkedIn platforms rarely set it.
        mask &= (work_mode_series == _normalize_exact(filters.work_mode)) | (
            work_mode_series == ""
        )

    if filters.job_level.strip() and _normalize_exact(filters.job_level) != "any":
        job_level_series = _text_series(filtered, "job_level").map(_normalize_exact)
        # Unknown (empty) job_level passes — non-LinkedIn platforms rarely set it.
        mask &= (job_level_series == _normalize_exact(filters.job_level)) | (
            job_level_series == ""
        )

    salary_min_series = _numeric_series(filtered, "salary_min")
    salary_max_series = _numeric_series(filtered, "salary_max")
    salary_unknown = salary_min_series.isna() | salary_max_series.isna()

    if filters.salary_min is not None:
        salary_floor_mask = (salary_max_series >= filters.salary_min) | (
            salary_min_series >= filters.salary_min
        )
        if filters.include_unknown_salary:
            salary_floor_mask |= salary_unknown
        mask &= salary_floor_mask

    if filters.salary_max is not None:
        salary_ceiling_mask = salary_min_series <= filters.salary_max
        if filters.include_unknown_salary:
            salary_ceiling_mask |= salary_unknown
        mask &= salary_ceiling_mask

    active_skills = [skill.strip() for skill in filters.skills if skill.strip()]
    if active_skills:
        searchable_text = (skills + " " + description).str.casefold()
        skill_mask = pd.Series(False, index=filtered.index)
        for skill in active_skills:
            skill_mask |= searchable_text.str.contains(skill.casefold(), regex=False)
        mask &= skill_mask

    if filters.posted_after is not None:
        posted_date = _datetime_series(filtered, "posted_date")
        mask &= posted_date.notna() & (posted_date >= pd.Timestamp(filters.posted_after))

    return filtered.loc[mask].copy()
