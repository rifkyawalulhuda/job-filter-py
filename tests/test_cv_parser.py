"""Tests for CV parsing helpers."""

from __future__ import annotations

import pytest

from src.cv_parser import analyze_cv_bytes, analyze_cv_text, extract_known_skills, match_cv_skills_to_job


def test_analyze_cv_text_extracts_contact_and_skills() -> None:
    text = """
    Rifky Awalul Huda
    rifky@example.com
    +62 812-0000-0000
    https://linkedin.com/in/rifky
    https://rifky.dev
    Experienced backend engineer using Python, FastAPI, PostgreSQL, AWS, and Docker.
    """.strip()

    result = analyze_cv_text(text)

    assert result.name == "Rifky Awalul Huda"
    assert result.email == "rifky@example.com"
    assert "+62 812-0000-0000" in result.phone
    assert result.linkedin_url == "https://linkedin.com/in/rifky"
    assert result.portfolio_url == "https://rifky.dev"
    assert result.skills == ["Python", "FastAPI", "PostgreSQL", "AWS", "Docker"]
    assert "Experienced backend engineer" in result.experience_summary


def test_extract_known_skills_supports_aliases() -> None:
    text = "Built APIs with Postgres, Amazon Web Services, JS, TS, and Node.js."

    result = extract_known_skills(text)

    assert result == ["PostgreSQL", "AWS", "JavaScript", "TypeScript", "Node.js"]


def test_match_cv_skills_to_job_returns_matched_and_missing() -> None:
    result = match_cv_skills_to_job(
        ["Python", "AWS", "Docker"],
        "FastAPI;PostgreSQL",
        "Build Python APIs on Amazon Web Services with Docker.",
    )

    assert result.matched == ["Python", "AWS", "Docker"]
    assert result.missing == ["FastAPI", "PostgreSQL"]
    assert result.inferred_job_skills == ["FastAPI", "PostgreSQL", "Python", "AWS", "Docker"]


def test_analyze_cv_bytes_rejects_unsupported_format() -> None:
    with pytest.raises(ValueError):
        analyze_cv_bytes("resume.txt", b"hello")
