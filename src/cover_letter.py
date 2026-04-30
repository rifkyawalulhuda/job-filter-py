"""Cover letter generation placeholders."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.profile import UserProfile


def _job_to_dict(job: dict[str, Any] | pd.Series) -> dict[str, Any]:
    """Convert supported job inputs into a plain dictionary."""
    if isinstance(job, pd.Series):
        return job.to_dict()
    return dict(job)


def _text_value(job_data: dict[str, Any], key: str, fallback: str = "") -> str:
    """Return a normalized string value with a graceful fallback."""
    value = job_data.get(key, fallback)
    if value is None or pd.isna(value):
        return fallback
    return str(value).strip()


def generate_cover_letter(job: dict[str, Any] | pd.Series, profile: UserProfile) -> str:
    """Generate a simple professional plain-text cover letter.

    Parameters
    ----------
    job:
        Job data represented as a dictionary or a pandas Series.
    profile:
        Applicant profile information.
    """
    job_data = _job_to_dict(job)
    applicant_name = profile.name.strip() or "Applicant"
    job_title = _text_value(job_data, "job_title", "the advertised position")
    company = _text_value(job_data, "company", "your company")
    skills_text = _text_value(job_data, "skills")
    skills_list = [skill.strip() for skill in skills_text.split(";") if skill.strip()]
    relevant_skills = ", ".join(skills_list[:4]) if skills_list else "relevant technical and problem-solving skills"

    contact_lines = []
    if profile.email.strip():
        contact_lines.append(f"Email: {profile.email.strip()}")
    if profile.phone.strip():
        contact_lines.append(f"Phone: {profile.phone.strip()}")
    if profile.linkedin_url.strip():
        contact_lines.append(f"LinkedIn: {profile.linkedin_url.strip()}")
    if profile.portfolio_url.strip():
        contact_lines.append(f"Portfolio: {profile.portfolio_url.strip()}")

    contact_block = "\n".join(contact_lines)
    if contact_block:
        contact_block = f"\n{contact_block}"

    return (
        f"Dear {company} Hiring Team,\n\n"
        f"My name is {applicant_name}, and I am writing to express my interest in the {job_title} role.\n"
        f"I believe my background and experience with {relevant_skills} would allow me to contribute meaningfully to {company}.\n"
        f"I am excited by the opportunity to bring strong collaboration, ownership, and practical execution to this position.\n\n"
        f"Thank you for considering my application. I would welcome the opportunity to discuss how I can support {company}'s goals.{contact_block}\n\n"
        "Sincerely,\n"
        f"{applicant_name}"
    )
