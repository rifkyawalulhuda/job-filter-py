"""Candidate profile helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


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


def save_profile(profile: UserProfile, path: str = "user_profile.json") -> None:
    """Save a user profile to a local JSON file using UTF-8 encoding."""
    profile_path = Path(path)
    profile_path.write_text(
        json.dumps(profile_to_dict(profile), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_profile(path: str = "user_profile.json") -> UserProfile:
    """Load a user profile from local JSON or return an empty profile on failure."""
    profile_path = Path(path)
    if not profile_path.exists():
        return UserProfile()

    try:
        raw_data = json.loads(profile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return UserProfile()

    if not isinstance(raw_data, dict):
        return UserProfile()

    return profile_from_dict(raw_data)
