"""Tests for SQLite-backed profile persistence."""

from __future__ import annotations

from pathlib import Path

from src.profile import UserProfile, load_profile, save_profile


def test_save_and_load_profile_round_trip(tmp_path: Path) -> None:
    database_path = tmp_path / "profile.db"
    original = UserProfile(
        name="Rifky",
        email="rifky@example.com",
        phone="+62-812-0000-0000",
        linkedin_url="https://linkedin.com/in/rifky",
        portfolio_url="https://rifky.dev",
    )

    save_profile(original, path=str(database_path))

    loaded = load_profile(path=str(database_path))

    assert loaded == original


def test_load_profile_returns_empty_when_database_is_new(tmp_path: Path) -> None:
    database_path = tmp_path / "empty.db"

    loaded = load_profile(path=str(database_path))

    assert loaded == UserProfile()
