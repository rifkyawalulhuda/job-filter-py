"""Candidate profile helpers backed by local SQLite storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.database import DEFAULT_DATABASE_PATH, load_profile_data, save_profile_data


@dataclass(slots=True)
class UserProfile:
    """User profile data used by the application assistant flow."""

    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""


def profile_to_dict(profile: UserProfile) -> dict[str, str]:
    """Convert a user profile dataclass into a plain dictionary."""
    return asdict(profile)


def profile_from_dict(data: dict[str, Any]) -> UserProfile:
    """Create a user profile from a dictionary-like payload."""
    return UserProfile(
        name=str(data.get("name", "") or ""),
        email=str(data.get("email", "") or ""),
        phone=str(data.get("phone", "") or ""),
        linkedin_url=str(data.get("linkedin_url", "") or ""),
        portfolio_url=str(data.get("portfolio_url", "") or ""),
    )


def save_profile(profile: UserProfile, path: str = DEFAULT_DATABASE_PATH) -> None:
    """Save a user profile to a local SQLite database."""
    save_profile_data(profile_to_dict(profile), path=path)


def load_profile(path: str = DEFAULT_DATABASE_PATH) -> UserProfile:
    """Load a user profile from local SQLite or return an empty profile on failure."""
    try:
        raw_data = load_profile_data(path=path)
    except OSError:
        return UserProfile()
    return profile_from_dict(raw_data)
