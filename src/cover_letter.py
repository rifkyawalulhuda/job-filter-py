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


def _join_list(items: list[str]) -> str:
    """Render a short natural-language list."""
    cleaned = [item.strip() for item in items if item.strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _detect_language(text: str) -> str:
    """Detect if text is Indonesian or English."""
    id_words = {
        "dan", "yang", "untuk", "dengan", "ini", "dari", "pada", "adalah",
        "akan", "oleh", "juga", "lebih", "atau", "telah", "sudah", "bisa",
        "dalam", "saya", "tidak", "ada", "itu", "ke", "di", "sangat",
        "tertarik", "melamar", "posisi", "pekerjaan", "perusahaan",
        "pengalaman", "kemampuan", "terima", "kasih", "hormat", "formal",
        "singkat", "percaya", "diri", "tegas",
    }
    words = set(text.lower().split())
    return "indonesian" if len(words & id_words) >= 2 else "english"


def _tone_phrases(tone: str, lang: str = "english") -> dict[str, str]:
    """Return phrase variants for the requested cover letter tone and language."""
    normalized = tone.strip().casefold()
    if lang == "indonesian":
        if normalized == "concise":
            return {
                "intro": "Saya tertarik dengan",
                "fit": "Posisi ini sangat sesuai karena pengalaman saya di",
                "experience": "Latar belakang saya mencakup",
                "closing": "Saya berharap dapat berkontribusi di",
            }
        if normalized == "confident":
            return {
                "intro": "Saya sangat antusias untuk melamar posisi",
                "fit": "Saya sangat cocok untuk posisi ini karena pengalaman saya di",
                "experience": "Saya memiliki pengalaman langsung dalam",
                "closing": "Saya yakin dapat memberikan nilai tambah di",
            }
        return {
            "intro": "Saya menulis surat ini untuk menyatakan ketertarikan saya terhadap",
            "fit": "Posisi ini terasa sangat sesuai karena pengalaman saya di",
            "experience": "Latar belakang saya mencakup",
            "closing": "Saya menyambut baik kesempatan untuk mendukung",
        }
    # English
    if normalized == "concise":
        return {
            "intro": "I am interested in",
            "fit": "This role is a strong fit because of my experience with",
            "experience": "My background includes",
            "closing": "I would value the opportunity to contribute to",
        }
    if normalized == "confident":
        return {
            "intro": "I am excited to apply for",
            "fit": "I am well-positioned for this role because of my experience with",
            "experience": "I bring hands-on experience in",
            "closing": "I am confident I can add value to",
        }
    return {
        "intro": "I am writing to express my interest in",
        "fit": "This role feels like a strong match because of my experience with",
        "experience": "My background includes",
        "closing": "I would welcome the opportunity to support",
    }


def _resolve_tone_from_prompt(tone: str, custom_prompt: str) -> str:
    """Allow small prompt guidance to override or refine the selected tone."""
    prompt = custom_prompt.casefold()
    if any(keyword in prompt for keyword in ("lebih formal", "more formal", "formal")):
        return "formal"
    if any(keyword in prompt for keyword in ("lebih singkat", "more concise", "concise", "shorter", "short")):
        return "concise"
    if any(
        keyword in prompt
        for keyword in ("lebih percaya diri", "more confident", "confident", "lebih tegas")
    ):
        return "confident"
    return tone


def _build_fit_reason(
    company: str,
    matched_skills: list[str],
    job_title: str,
    location: str,
    work_mode: str,
    lang: str = "english",
) -> str:
    """Create a short reason why the role is a good fit."""
    if lang == "indonesian":
        if matched_skills:
            return f"kesesuaian antara kebutuhan posisi dan pengalaman saya di {_join_list(matched_skills[:3])}"
        if location or work_mode:
            context = " ".join(part for part in [location, work_mode] if part).strip()
            return f"ketertarikan saya pada peluang {job_title} di {context}"
        return f"ketertarikan saya untuk berkontribusi di {company} melalui posisi {job_title}"
    # English
    if matched_skills:
        return f"the overlap between the role's needs and my experience with {_join_list(matched_skills[:3])}"
    if location or work_mode:
        context = " ".join(part for part in [location, work_mode] if part).strip()
        return f"its alignment with my interest in {job_title} opportunities in {context}"
    return f"my interest in contributing to {company} through this {job_title} opportunity"


def generate_cover_letter(
    job: dict[str, Any] | pd.Series,
    profile: UserProfile,
    matched_skills: list[str] | None = None,
    missing_skills: list[str] | None = None,
    experience_summary: str = "",
    tone: str = "formal",
    custom_prompt: str = "",
) -> str:
    """Generate a simple professional plain-text cover letter.

    Parameters
    ----------
    job:
        Job data represented as a dictionary or a pandas Series.
    profile:
        Applicant profile information.
    matched_skills:
        Skills found in both the CV and the selected job.
    missing_skills:
        Skills inferred from the job that are not clearly present in the CV.
    experience_summary:
        Short candidate summary extracted from the CV.
    tone:
        Writing tone for the draft. Supported values are ``formal``, ``concise``,
        and ``confident``.
    custom_prompt:
        Small free-text guidance such as ``lebih formal`` or ``lebih singkat``.
    """
    job_data = _job_to_dict(job)
    applicant_name = profile.name.strip() or "Applicant"
    lang = _detect_language(custom_prompt) if custom_prompt.strip() else "english"

    title_fallback = "posisi yang dilamar" if lang == "indonesian" else "the advertised position"
    company_fallback = "perusahaan Anda" if lang == "indonesian" else "your company"

    job_title = _text_value(job_data, "job_title", title_fallback)
    company = _text_value(job_data, "company", company_fallback)
    location = _text_value(job_data, "location")
    work_mode = _text_value(job_data, "work_mode")
    skills_text = _text_value(job_data, "skills")
    skills_list = [skill.strip() for skill in skills_text.split(";") if skill.strip()]
    matched_skills = matched_skills or []
    missing_skills = missing_skills or []
    highlighted_skills = matched_skills[:4] if matched_skills else skills_list[:4]
    relevant_skills = (
        _join_list(highlighted_skills)
        if highlighted_skills
        else "relevant technical and problem-solving skills"
    )

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

    effective_tone = _resolve_tone_from_prompt(tone, custom_prompt)
    lang = _detect_language(custom_prompt) if custom_prompt.strip() else "english"
    phrases = _tone_phrases(effective_tone, lang)
    fit_reason = _build_fit_reason(company, matched_skills, job_title, location, work_mode, lang)

    if lang == "indonesian":
        strengths_sentence = (
            f"{phrases['fit']} {_join_list(highlighted_skills)}, dan itu menjadi alasan utama saya melamar posisi ini."
            if highlighted_skills
            else f"{phrases['fit']} {_join_list(highlighted_skills)}."
        )
        growth_sentence = ""
        if missing_skills:
            growth_sentence = (
                f" Saya juga siap untuk memperdalam pengalaman saya di {_join_list(missing_skills[:3])} "
                "jika posisi ini membutuhkannya."
            )
        experience_sentence = ""
        if experience_summary:
            experience_sentence = f" {phrases['experience']} {experience_summary.strip(' .')}."

        concise_mode = effective_tone == "concise" or "lebih singkat" in custom_prompt.casefold() or "shorter" in custom_prompt.casefold()
        body_lines = [
            f"Kepada Tim HRD {company},",
            "",
            f"Nama saya {applicant_name}, dan {phrases['intro']} posisi {job_title} di {company}.",
            f"Saya tertarik dengan kesempatan ini karena {fit_reason}.{experience_sentence}",
            strengths_sentence if not concise_mode else f"{phrases['fit']} {_join_list(highlighted_skills)}.",
        ]
        if growth_sentence and not concise_mode:
            body_lines[-1] = f"{body_lines[-1]}{growth_sentence}"
        if not concise_mode:
            body_lines.append(
                "Saya antusias untuk membawa kemampuan kolaborasi, tanggung jawab, dan eksekusi yang baik ke posisi ini."
            )
        body_lines.extend(
            [
                "",
                f"Terima kasih telah mempertimbangkan lamaran saya. {phrases['closing']} {company}.{contact_block}",
                "",
                "Hormat saya,",
                applicant_name,
            ]
        )
    else:
        strengths_sentence = (
            f"{phrases['fit']} {relevant_skills}, and that is one reason this opportunity stands out to me."
            if highlighted_skills
            else f"{phrases['fit']} {relevant_skills}."
        )
        growth_sentence = ""
        if missing_skills:
            growth_sentence = (
                f" I am also prepared to deepen my hands-on experience with {_join_list(missing_skills[:3])} "
                "where the role would benefit from it."
            )
        experience_sentence = ""
        if experience_summary:
            experience_sentence = f" {phrases['experience']} {experience_summary.strip(' .')}."

        concise_mode = effective_tone == "concise" or "lebih singkat" in custom_prompt.casefold() or "shorter" in custom_prompt.casefold()
        body_lines = [
            f"Dear {company} Hiring Team,",
            "",
            f"My name is {applicant_name}, and {phrases['intro']} the {job_title} role at {company}.",
            f"I am drawn to this opportunity because of {fit_reason}.{experience_sentence}",
            strengths_sentence if not concise_mode else f"{phrases['fit']} {relevant_skills}.",
        ]
        if growth_sentence and not concise_mode:
            body_lines[-1] = f"{body_lines[-1]}{growth_sentence}"
        if not concise_mode:
            body_lines.append(
                "I am excited by the opportunity to bring strong collaboration, ownership, and practical execution to this position."
            )
        body_lines.extend(
            [
                "",
                f"Thank you for considering my application. {phrases['closing']} {company}'s goals.{contact_block}",
                "",
                "Sincerely,",
                applicant_name,
            ]
        )
    return "\n".join(body_lines)
