"""Tests for CV parsing helpers."""

from __future__ import annotations

import pytest

from src.cv_parser import analyze_cv_bytes, analyze_cv_text


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


def test_analyze_cv_bytes_rejects_unsupported_format() -> None:
    with pytest.raises(ValueError):
        analyze_cv_bytes("resume.txt", b"hello")
