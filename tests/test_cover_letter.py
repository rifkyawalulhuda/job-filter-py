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


def test_generate_cover_letter_handles_missing_fields_gracefully() -> None:
    letter = generate_cover_letter(pd.Series({"company": "Example Corp"}), UserProfile())

    assert "Example Corp" in letter
    assert "the advertised position" in letter
    assert "Applicant" in letter
