"""Tests for pasted job text parsing helpers."""

from __future__ import annotations

from src.paste_jobs import parse_pasted_jobs


def test_parse_pasted_jobs_supports_labeled_blocks() -> None:
    text = """
    Backend Engineer
    Company: Acme Inc
    Location: Jakarta
    Work Mode: Remote
    Skills: Python;FastAPI;PostgreSQL
    Apply URL: https://example.com/jobs/1

    Frontend Engineer
    Company: Beta Labs
    Location: Bandung
    Work Mode: Hybrid
    Skills: React;JavaScript
    """.strip()

    result = parse_pasted_jobs(text)

    assert len(result) == 2
    assert result.loc[0, "company"] == "Acme Inc"
    assert result.loc[1, "work_mode"] == "Hybrid"


def test_parse_pasted_jobs_uses_plain_line_fallbacks() -> None:
    text = """
    Data Analyst
    Delta Analytics | Surabaya | Onsite
    SQL reporting and dashboard support.
    https://example.com/jobs/2
    """.strip()

    result = parse_pasted_jobs(text)

    assert result.loc[0, "job_title"] == "Data Analyst"
    assert result.loc[0, "company"] == "Delta Analytics"
    assert result.loc[0, "location"] == "Surabaya"
    assert result.loc[0, "work_mode"] == "onsite"
    assert result.loc[0, "apply_url"] == "https://example.com/jobs/2"


def test_parse_pasted_jobs_infers_metadata_salary_and_skills() -> None:
    text = """
    Senior Backend Engineer
    Acme Inc | Jakarta | Remote | Full-time
    Salary: IDR 25000000 - 35000000
    Build Python and FastAPI services on AWS with Docker.
    Posted: 2026-04-30
    https://example.com/jobs/3
    """.strip()

    result = parse_pasted_jobs(text)

    assert result.loc[0, "company"] == "Acme Inc"
    assert result.loc[0, "location"] == "Jakarta"
    assert result.loc[0, "work_mode"] == "remote"
    assert result.loc[0, "job_type"] == "full-time"
    assert result.loc[0, "salary_min"] == 25000000
    assert result.loc[0, "salary_max"] == 35000000
    assert result.loc[0, "currency"] == "IDR"
    assert result.loc[0, "skills"] == "Python;FastAPI;AWS;Docker"


def test_parse_pasted_jobs_rejects_empty_text() -> None:
    try:
        parse_pasted_jobs("   ")
    except ValueError as exc:
        assert "Paste lowongan text first" in str(exc)
    else:
        raise AssertionError("Expected parse_pasted_jobs to raise ValueError for empty text.")
