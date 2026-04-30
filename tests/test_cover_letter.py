"""Tests for cover letter generation helpers."""

from __future__ import annotations

import pandas as pd

from src.cover_letter import generate_cover_letter
from src.profile import UserProfile


def _profile() -> UserProfile:
    """Create a sample user profile for cover letter tests."""
    return UserProfile(
        name="Rifky",
        email="rifky@example.com",
        phone="+62-812-0000-0000",
        linkedin_url="https://linkedin.com/in/rifky",
        portfolio_url="https://rifky.dev",
    )


def _job() -> dict[str, str]:
    """Create a sample job payload for cover letter tests."""
    return {
        "job_title": "Backend Engineer",
        "company": "Acme Inc",
        "skills": "Python;FastAPI;PostgreSQL",
    }


def test_generate_cover_letter_returns_string() -> None:
    letter = generate_cover_letter(_job(), _profile())

    assert isinstance(letter, str)


def test_generate_cover_letter_includes_applicant_name() -> None:
    letter = generate_cover_letter(_job(), _profile())

    assert "Rifky" in letter


def test_generate_cover_letter_includes_job_title() -> None:
    letter = generate_cover_letter(_job(), _profile())

    assert "Backend Engineer" in letter


def test_generate_cover_letter_includes_company_name() -> None:
    letter = generate_cover_letter(_job(), _profile())

    assert "Acme Inc" in letter


def test_generate_cover_letter_includes_email() -> None:
    letter = generate_cover_letter(_job(), _profile())

    assert "rifky@example.com" in letter


def test_generate_cover_letter_includes_phone() -> None:
    letter = generate_cover_letter(_job(), _profile())

    assert "+62-812-0000-0000" in letter


def test_generate_cover_letter_includes_skills_if_available() -> None:
    letter = generate_cover_letter(_job(), _profile())

    assert "Python" in letter
    assert "FastAPI" in letter


def test_generate_cover_letter_uses_skill_match_context() -> None:
    letter = generate_cover_letter(
        _job(),
        _profile(),
        matched_skills=["Python", "FastAPI"],
        missing_skills=["PostgreSQL"],
        experience_summary="experienced backend engineer building API platforms",
        tone="formal",
    )

    assert "Python and FastAPI" in letter
    assert "PostgreSQL" in letter
    assert "prepared to deepen" in letter
    assert "experienced backend engineer building API platforms" in letter


def test_generate_cover_letter_supports_confident_tone() -> None:
    letter = generate_cover_letter(
        _job(),
        _profile(),
        matched_skills=["Python"],
        tone="confident",
    )

    assert "I am excited to apply for" in letter
    assert "I am confident I can add value" in letter


def test_generate_cover_letter_supports_custom_prompt_for_concise_output() -> None:
    letter = generate_cover_letter(
        _job(),
        _profile(),
        matched_skills=["Python", "FastAPI"],
        missing_skills=["PostgreSQL"],
        experience_summary="experienced backend engineer building API platforms",
        tone="formal",
        custom_prompt="lebih singkat",
    )

    assert "prepared to deepen" not in letter
    assert "I am excited by the opportunity" not in letter


def test_generate_cover_letter_supports_custom_prompt_for_formal_tone() -> None:
    letter = generate_cover_letter(
        _job(),
        _profile(),
        tone="confident",
        custom_prompt="lebih formal",
    )

    assert "I am writing to express my interest in" in letter
    assert "I would welcome the opportunity to support" in letter


def test_generate_cover_letter_handles_missing_fields_gracefully() -> None:
    letter = generate_cover_letter(pd.Series({"company": "Example Corp"}), UserProfile())

    assert "Example Corp" in letter
    assert "the advertised position" in letter
    assert "Applicant" in letter
