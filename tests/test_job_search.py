"""Tests for AI-powered job search module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.filters import JobFilters
from src.job_search import (
    DuckDuckGoBackend,
    _build_search_query,
    _clean_html,
    _extract_company,
    _extract_job_title,
    _extract_location,
    _is_job_listing,
    _parse_ddg_html,
    _result_to_row,
    search_jobs,
)


# ── Query building ───────────────────────────────────────────────────────────


def test_build_search_query_with_keyword_and_location() -> None:
    """Query includes keyword and location."""
    filters = JobFilters(keyword="Python Developer", location="Jakarta")
    query = _build_search_query(filters)
    assert "Python Developer" in query
    assert "Jakarta" in query


def test_build_search_query_includes_job_level() -> None:
    """Query includes job level when not 'Any'."""
    filters = JobFilters(keyword="Engineer", job_level="senior")
    query = _build_search_query(filters)
    assert "senior" in query.lower()


def test_build_search_query_includes_work_mode() -> None:
    """Query includes work mode when not 'Any'."""
    filters = JobFilters(keyword="Designer", work_mode="remote")
    query = _build_search_query(filters)
    assert "remote" in query.lower()


def test_build_search_query_ignores_any_level_and_mode() -> None:
    """Query excludes 'Any' level/mode values."""
    filters = JobFilters(keyword="Dev", job_level="Any", work_mode="Any")
    query = _build_search_query(filters)
    assert "any" not in query.lower()


def test_build_search_query_returns_empty_for_blank_filters() -> None:
    """Empty query when no meaningful filters are provided."""
    filters = JobFilters()
    query = _build_search_query(filters)
    assert query == ""


def test_build_search_query_includes_skills() -> None:
    """Query includes first 3 skills as context."""
    filters = JobFilters(
        keyword="Engineer", skills=["Python", "Docker", "AWS", "React"]
    )
    query = _build_search_query(filters)
    assert "Python" in query
    assert "Docker" in query
    assert "AWS" in query
    assert "React" not in query  # Only first 3


# ── HTML parsing ─────────────────────────────────────────────────────────────


def test_clean_html_strips_tags() -> None:
    """HTML tags are removed and text is cleaned."""
    result = _clean_html("<b>Hello</b> <i>World</i>")
    assert result == "Hello World"


def test_clean_html_decodes_entities() -> None:
    """HTML entities are decoded."""
    result = _clean_html("AT&amp;T &quot;quote&quot;")
    assert "AT&T" in result
    assert '"quote"' in result


def test_parse_ddg_html_extracts_results() -> None:
    """DDG HTML is parsed into structured result dicts."""
    html = """
    <html><body>
    <a class="result__a" href="https://linkedin.com/jobs/view/123">
        Python Developer - Tech Corp
    </a>
    <a class="result__snippet">
        Tech Corp is hiring a Python Developer in Jakarta. Apply now.
    </a>
    <a class="result__a" href="https://indeed.com/viewjob/456">
        Senior Engineer at StartupX
    </a>
    <a class="result__snippet">
        StartupX looking for Senior Engineer, remote position.
    </a>
    </body></html>
    """
    results = _parse_ddg_html(html, max_results=10)
    assert len(results) == 2
    assert results[0]["url"] == "https://linkedin.com/jobs/view/123"
    assert "Python Developer" in results[0]["title"]
    assert "Jakarta" in results[0]["snippet"]


# ── Job listing detection ────────────────────────────────────────────────────


def test_is_job_listing_detects_known_domains() -> None:
    """URLs from known job platforms are detected."""
    result = {
        "title": "Engineer",
        "snippet": "Some description",
        "url": "https://linkedin.com/jobs/view/123",
    }
    assert _is_job_listing(result) is True


def test_is_job_listing_detects_indeed() -> None:
    """Indeed URLs are detected."""
    result = {
        "title": "Dev",
        "snippet": "",
        "url": "https://id.indeed.com/viewjob?jk=abc",
    }
    assert _is_job_listing(result) is True


def test_is_job_listing_detects_by_keywords() -> None:
    """Non-job-platform URLs with hiring keywords are detected."""
    result = {
        "title": "Backend Engineer",
        "snippet": "Company is hiring for a full-time position. Apply now.",
        "url": "https://some-company.com/careers",
    }
    assert _is_job_listing(result) is True


def test_is_job_listing_rejects_news_articles() -> None:
    """News articles about jobs are not treated as listings."""
    result = {
        "title": "Tech jobs report 2025",
        "snippet": "News report about the latest hiring trends in tech.",
        "url": "https://news-site.com/tech-jobs-report",
    }
    assert _is_job_listing(result) is False


def test_is_job_listing_rejects_irrelevant_urls() -> None:
    """Random URLs without job keywords are rejected."""
    result = {
        "title": "Blog post about coding",
        "snippet": "Learn to code in Python with these tips.",
        "url": "https://blog.example.com/python-tips",
    }
    assert _is_job_listing(result) is False


# ── Field extraction ─────────────────────────────────────────────────────────


def test_extract_job_title_from_combined_text() -> None:
    """Job title is extracted from title + snippet."""
    title = "Senior Python Developer - Tech Corp | Jakarta"
    snippet = "We are hiring a Senior Python Developer to join our team."
    result = _extract_job_title(title, snippet)
    assert "Senior" in result
    assert "Python" in result
    assert len(result) > 0


def test_extract_job_title_falls_back_to_cleaned_title() -> None:
    """When no pattern matches, the cleaned title is used."""
    title = "Full-Stack Engineer at CompanyX"
    snippet = "Some unrelated text"
    result = _extract_job_title(title, snippet)
    assert len(result) > 0
    assert "CompanyX" not in result.lower()


def test_extract_company_from_text() -> None:
    """Company name is extracted from 'at Company' patterns."""
    result = _extract_company(
        "Software Engineer",
        "We are looking for an engineer at TechVision Inc. in Jakarta.",
    )
    assert result == "TechVision Inc"


def test_extract_location_from_text() -> None:
    """Location is extracted from 'in City' patterns."""
    result = _extract_location(
        "Developer",
        "Position available in Bandung, Indonesia. Apply now.",
    )
    assert "Bandung" in result


# ── Result conversion ────────────────────────────────────────────────────────


def test_result_to_row_returns_structured_dict() -> None:
    """A search result is converted to a structured job row."""
    result = {
        "title": "Data Analyst at Metro Insight",
        "snippet": "Hiring Data Analyst in Surabaya. SQL, Excel required.",
        "url": "https://example.com/jobs/123",
    }
    row = _result_to_row(result)
    assert row["apply_url"] == "https://example.com/jobs/123"
    assert isinstance(row["job_title"], str)
    assert isinstance(row["company"], str)
    assert isinstance(row["description"], str)


# ── DuckDuckGo backend ───────────────────────────────────────────────────────


def test_duckduckgo_backend_has_default_timeout() -> None:
    """Backend initializes with default timeout."""
    backend = DuckDuckGoBackend()
    assert backend.timeout == 15


# ── search_jobs integration ──────────────────────────────────────────────────


def test_search_jobs_returns_dataframe() -> None:
    """search_jobs returns a normalized DataFrame using a mock backend."""
    filters = JobFilters(keyword="Python", location="Jakarta")
    df = search_jobs(filters, max_results=10, backend=_MockBackend())

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "job_title" in df.columns
    assert "company" in df.columns
    assert "apply_url" in df.columns


def test_search_jobs_raises_for_empty_filters() -> None:
    """search_jobs raises ValueError when no meaningful filters."""
    filters = JobFilters()
    with pytest.raises(ValueError, match="keyword or location"):
        search_jobs(filters)


class _FakeBackend:
    """Fake search backend that returns no job listings."""

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        return [
            {
                "title": "Random blog post",
                "snippet": "Nothing work related here, just a cooking recipe.",
                "url": "https://blog.example.com/post",
            }
        ]


class _MockBackend:
    """Mock search backend with job listing results."""

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        return [
            {
                "title": "Software Engineer at TechCo",
                "snippet": "TechCo is hiring a Software Engineer in Jakarta. Remote. Apply now.",
                "url": "https://linkedin.com/jobs/view/999",
            },
            {
                "title": "Data Scientist - Analytics Corp",
                "snippet": "Analytics Corp looking for Data Scientist. Python, SQL.",
                "url": "https://indeed.com/viewjob/888",
            },
        ]


def test_search_jobs_rejects_no_listing_results() -> None:
    """search_jobs raises when no job listings are found in results."""
    filters = JobFilters(keyword="Engineer", location="Nowhere")
    with pytest.raises(ValueError, match="No job listings found"):
        search_jobs(filters, backend=_FakeBackend())


def test_search_jobs_with_mock_backend() -> None:
    """search_jobs works with a custom mock backend."""
    filters = JobFilters(keyword="Engineer", location="Jakarta")
    df = search_jobs(filters, backend=_MockBackend())

    assert len(df) == 2
    assert "Software Engineer" in df.iloc[0]["job_title"]
    assert "linkedin.com" in df.iloc[0]["apply_url"]
