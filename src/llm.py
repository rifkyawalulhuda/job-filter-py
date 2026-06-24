"""LLM client with BYOK (Bring Your Own Key) support.

Uses OpenAI-compatible API — works with dough.id, OpenAI, Groq, etc.
Configuration persisted to SQLite via ``src.database``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.database import DEFAULT_DATABASE_PATH, init_database
from src.database import SQLALCHEMY_AVAILABLE

if SQLALCHEMY_AVAILABLE:
    from src.database import Base, _get_session_factory
    from sqlalchemy import String, Text, Integer
    from sqlalchemy.orm import Mapped, mapped_column

    class LLMConfigRecord(Base):
        """Stored LLM configuration row."""

        __tablename__ = "llm_config"

        id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
        provider: Mapped[str] = mapped_column(String(50), default="openai")
        api_key: Mapped[str] = mapped_column(Text, default="")
        api_base: Mapped[str] = mapped_column(String(500), default="https://api.openai.com/v1")
        model: Mapped[str] = mapped_column(String(100), default="gpt-4o-mini")


@dataclass(slots=True)
class LLMConfig:
    """User-provided LLM credentials and preferences."""

    provider: str = "openai"
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"

    @property
    def is_configured(self) -> bool:
        """Return True if the LLM is ready to use."""
        return bool(self.api_key.strip() and self.api_base.strip())

    @property
    def headers(self) -> dict[str, str]:
        """Build HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @property
    def chat_url(self) -> str:
        """Full chat completions endpoint URL."""
        base = self.api_base.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/chat/completions"


# ── Persistence ──────────────────────────────────────────────────────────────


def _ensure_llm_table(path: str = DEFAULT_DATABASE_PATH) -> None:
    """Create llm_config table if SQLAlchemy is not available."""
    if SQLALCHEMY_AVAILABLE:
        session_factory = _get_session_factory(path)
        Base.metadata.create_all(session_factory.kw["bind"])
        return

    import sqlite3
    from src.database import resolve_database_path

    resolved = resolve_database_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(resolved)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_config (
            id INTEGER PRIMARY KEY DEFAULT 1,
            provider TEXT NOT NULL DEFAULT 'openai',
            api_key TEXT NOT NULL DEFAULT '',
            api_base TEXT NOT NULL DEFAULT 'https://api.openai.com/v1',
            model TEXT NOT NULL DEFAULT 'gpt-4o-mini'
        )
        """
    )
    conn.commit()
    conn.close()


def save_llm_config(config: LLMConfig, path: str = DEFAULT_DATABASE_PATH) -> None:
    """Persist LLM configuration to SQLite."""
    _ensure_llm_table(path)

    if SQLALCHEMY_AVAILABLE:
        session_factory = _get_session_factory(path)
        with session_factory() as session:
            record = session.get(LLMConfigRecord, 1)
            if record is None:
                record = LLMConfigRecord(id=1)

            record.provider = config.provider
            record.api_key = config.api_key
            record.api_base = config.api_base
            record.model = config.model

            session.add(record)
            session.commit()
        return

    import sqlite3
    from src.database import resolve_database_path

    resolved = resolve_database_path(path)
    conn = sqlite3.connect(resolved)
    conn.execute(
        """
        INSERT INTO llm_config (id, provider, api_key, api_base, model)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            provider = excluded.provider,
            api_key = excluded.api_key,
            api_base = excluded.api_base,
            model = excluded.model
        """,
        (config.provider, config.api_key, config.api_base, config.model),
    )
    conn.commit()
    conn.close()


def load_llm_config(path: str = DEFAULT_DATABASE_PATH) -> LLMConfig:
    """Load LLM configuration from SQLite, or return defaults."""
    _ensure_llm_table(path)

    if SQLALCHEMY_AVAILABLE:
        session_factory = _get_session_factory(path)
        with session_factory() as session:
            record = session.get(LLMConfigRecord, 1)
            if record is None:
                return LLMConfig()
            return LLMConfig(
                provider=str(record.provider or "openai"),
                api_key=str(record.api_key or ""),
                api_base=str(record.api_base or "https://api.openai.com/v1"),
                model=str(record.model or "gpt-4o-mini"),
            )

    import sqlite3
    from src.database import resolve_database_path

    resolved = resolve_database_path(path)
    conn = sqlite3.connect(resolved)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM llm_config WHERE id = 1").fetchone()
    conn.close()

    if row is None:
        return LLMConfig()

    return LLMConfig(
        provider=str(row["provider"] or "openai"),
        api_key=str(row["api_key"] or ""),
        api_base=str(row["api_base"] or "https://api.openai.com/v1"),
        model=str(row["model"] or "gpt-4o-mini"),
    )


# ── LLM Client ───────────────────────────────────────────────────────────────


@dataclass(slots=True)
class LLMClient:
    """OpenAI-compatible chat completions client."""

    config: LLMConfig = field(default_factory=LLMConfig)
    timeout: int = 60

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send a chat request and return the assistant's response text."""
        import requests

        if not self.config.is_configured:
            raise ValueError(
                "LLM is not configured. Please set your API key and endpoint "
                "in the BYOK panel in the sidebar."
            )

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(
                self.config.chat_url,
                headers=self.config.headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            message = data["choices"][0]["message"]
            # Support reasoning models (e.g. deepseek-v4-pro, o1) —
            # actual answer may be in "reasoning_content" when "content" is empty
            content = message.get("content", "") or ""
            if not content.strip():
                content = message.get("reasoning_content", "") or ""
            return content
        except requests.RequestException as exc:
            raise RuntimeError(f"LLM API request failed: {exc}") from exc
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Unexpected LLM API response: {exc}"
            ) from exc


# ── AI Features ──────────────────────────────────────────────────────────────


def _detect_language(text: str) -> str:
    """Detect if text is Indonesian or English based on common words."""
    id_words = {
        "dan", "yang", "untuk", "dengan", "ini", "dari", "pada", "adalah",
        "akan", "oleh", "juga", "lebih", "atau", "telah", "sudah", "bisa",
        "dalam", "saya", "tidak", "ada", "itu", "ke", "di", "bisa",
        "sangat", "tertarik", "melamar", "posisi", "pekerjaan", "perusahaan",
        "pengalaman", "kemampuan", "terima kasih", "hormat",
    }
    words = set(text.lower().split())
    matches = words & id_words
    return "indonesian" if len(matches) >= 2 else "english"


def generate_ai_cover_letter(
    job_title: str,
    company: str,
    location: str,
    skills_text: str,
    applicant_name: str,
    cv_summary: str = "",
    tone: str = "formal",
    custom_prompt: str = "",
    config: LLMConfig | None = None,
) -> str:
    """Generate a personalized cover letter using the LLM.

    Automatically detects language from custom_prompt:
    - Indonesian prompt → Indonesian cover letter
    - English prompt → English cover letter
    - No prompt → follows tone setting (default English)
    """
    llm = LLMClient(config=config or load_llm_config())

    # Detect language from custom prompt
    if custom_prompt.strip():
        lang = _detect_language(custom_prompt)
    else:
        lang = "english"

    tone_instruction = {
        "formal": {
            "english": "Write in a professional, formal tone suitable for corporate applications.",
            "indonesian": "Tulis dalam bahasa Indonesia dengan nada formal dan profesional yang cocok untuk lamaran kerja korporat.",
        },
        "concise": {
            "english": "Keep it brief and to the point. Short paragraphs, no fluff.",
            "indonesian": "Tulis dengan singkat dan padat. Paragraf pendek, langsung ke inti.",
        },
        "confident": {
            "english": "Use a confident, assertive tone that highlights achievements.",
            "indonesian": "Gunakan nada percaya diri dan tegas yang menonjolkan pencapaian.",
        },
    }.get(tone, {
        "english": "Write in a professional tone.",
        "indonesian": "Tulis dengan nada profesional.",
    }).get(lang, "Write in a professional tone.")

    # Build language instruction
    if lang == "indonesian":
        lang_instruction = (
            "IMPORTANT: Write the ENTIRE cover letter in Indonesian (Bahasa Indonesia). "
            "Do NOT mix English. Use proper Indonesian business language."
        )
        closing = "Hormat saya,"
    else:
        lang_instruction = (
            "IMPORTANT: Write the ENTIRE cover letter in English. "
            "Do NOT mix Indonesian. Use professional English."
        )
        closing = "Sincerely,"

    system_prompt = (
        "You are a professional cover letter writer for job applications. "
        f"{lang_instruction} "
        "Keep it to 3-4 short paragraphs. "
        "Do NOT use placeholder brackets like [Name] or [Company]. "
        "Write naturally as if the applicant is writing directly."
    )

    # Build user prompt
    prompt_parts = [f"Write a cover letter for this job:\n"]
    prompt_parts.append(f"Job Title: {job_title}")
    prompt_parts.append(f"Company: {company}")
    if location:
        prompt_parts.append(f"Location: {location}")
    if skills_text:
        prompt_parts.append(f"Skills Required: {skills_text}")
    prompt_parts.append(f"\nApplicant Name: {applicant_name}")
    if cv_summary:
        prompt_parts.append(f"Applicant Background: {cv_summary}")
    prompt_parts.append(f"\nTone: {tone_instruction}")
    if custom_prompt.strip():
        prompt_parts.append(f"\nAdditional instructions from the applicant: {custom_prompt.strip()}")

    if lang == "indonesian":
        prompt_parts.append(f"""
Surat lamaran harus:
1. Buka dengan perkenalan yang kuat dan nyatakan ketertarikan pada posisi tersebut
2. Hubungkan latar belakang pelamar dengan kebutuhan pekerjaan
3. Tunjukkan antusiasme terhadap perusahaan
4. Tutup dengan ajakan untuk diskusi lebih lanjut

Sertakan nama pelamar di akhir, diikuti '{closing}'""")
    else:
        prompt_parts.append(f"""
The letter should:
1. Open with a strong introduction expressing interest in the role
2. Connect the applicant's background to the job requirements
3. Show enthusiasm for the company
4. Close with a call to action

Include the applicant's name at the top and end with '{closing}' followed by the name.""")

    user_prompt = "\n".join(prompt_parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return llm.chat(messages, temperature=0.7, max_tokens=4000)


def ai_search_jobs(
    keyword: str,
    location: str = "",
    job_level: str = "",
    work_mode: str = "",
    skills: str = "",
    max_results: int = 10,
    config: LLMConfig | None = None,
) -> list[dict[str, str]]:
    """Use the LLM to search for current job listings and return structured data."""
    llm = LLMClient(config=config or load_llm_config())

    location_hint = f" in/near {location}" if location else ""
    level_hint = f", {job_level} level" if job_level and job_level.lower() != "any" else ""
    mode_hint = f", {work_mode} work mode" if work_mode and work_mode.lower() != "any" else ""
    skills_hint = f". Skills: {skills}" if skills else ""

    system_prompt = (
        "You are a job search assistant. Based on your training data, return realistic "
        "job listings as structured JSON. Include real companies that operate in Indonesia. "
        "Only return the JSON array, no other text."
    )

    user_prompt = f"""List {max_results} current job openings for: {keyword}{location_hint}{level_hint}{mode_hint}{skills_hint}.

Return ONLY a JSON array of objects with these fields:
- title: job title (e.g., "Backend Engineer")
- company: company name (e.g., "GoTo Group")
- location: city/area (e.g., "Jakarta")
- apply_url: a realistic LinkedIn job URL
- snippet: short description (1-2 sentences)

Example:
[
  {{"title": "Backend Engineer", "company": "GoTo Group", "location": "Jakarta", "apply_url": "https://www.linkedin.com/jobs/view/123", "snippet": "Build scalable backend services..."}},
  ...
]

Return ONLY valid JSON. No markdown, no explanation."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = llm.chat(messages, temperature=0.3, max_tokens=3000)

    # Extract JSON from response (may be wrapped in ```json ... ```)
    json_start = response.find("[")
    json_end = response.rfind("]")
    if json_start < 0 or json_end < 0:
        raise ValueError(f"LLM did not return valid JSON. Response: {response[:200]}")

    try:
        return json.loads(response[json_start : json_end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse LLM response as JSON: {exc}"
        ) from exc


def ai_enhance_jobs(
    jobs: list[dict[str, str]],
    config: LLMConfig | None = None,
) -> list[dict[str, str]]:
    """Use LLM to enrich scraped job listings with missing fields.

    Takes raw scraped data (title, company, location, URL) and uses the LLM
    to infer: skills, job_level, work_mode, salary range, description.
    """
    llm = LLMClient(config=config or load_llm_config())

    # Build compact input for the LLM
    jobs_input = []
    for i, job in enumerate(jobs):
        jobs_input.append({
            "id": i,
            "title": job.get("title", job.get("job_title", "")),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
        })

    system_prompt = (
        "You are a job data enrichment assistant for the Indonesian job market. "
        "Given a list of job entries with title, company, and location, infer "
        "the missing structured fields. Only return valid JSON."
    )

    user_prompt = f"""Enrich these job listings. For each, infer realistic values.

Jobs:
{json.dumps(jobs_input, ensure_ascii=False, indent=2)}

Return ONLY a JSON array of objects with these fields for EACH job:
- skills: semicolon-separated relevant skills (e.g., "Python;Docker;PostgreSQL")
- job_level: one of "internship", "entry", "junior", "mid", "senior", "lead", "manager"
- work_mode: one of "remote", "hybrid", "onsite"
- salary_min: realistic minimum monthly salary in IDR (number only, e.g., 8000000)
- salary_max: realistic maximum monthly salary in IDR (number only, e.g., 15000000)
- description: 1-2 sentence job description in English

IMPORTANT:
- Infer skills from the job title (e.g., "Backend Engineer" → Python;Go;Docker)
- Infer level from title keywords (Junior→junior, Senior→senior, Lead→lead)
- Use Indonesian salary ranges (Jakarta: 5-50 jt IDR/month for tech)
- work_mode: default "onsite" unless "remote" or "hybrid" in title

Return ONLY valid JSON array. No markdown, no explanation."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = llm.chat(messages, temperature=0.2, max_tokens=4000)

    json_start = response.find("[")
    json_end = response.rfind("]")
    if json_start < 0 or json_end < 0:
        raise ValueError(f"LLM did not return valid JSON. Response: {response[:200]}")

    try:
        enrichments = json.loads(response[json_start : json_end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse LLM response: {exc}") from exc

    # Merge enrichments back into original jobs
    enhanced = []
    for i, job in enumerate(jobs):
        enriched = dict(job)  # copy original
        if i < len(enrichments) and isinstance(enrichments[i], dict):
            data = enrichments[i]
            # Only fill missing fields
            if not enriched.get("skills") and data.get("skills"):
                enriched["skills"] = data["skills"]
            if not enriched.get("job_level") and data.get("job_level"):
                enriched["job_level"] = data["job_level"]
            if not enriched.get("work_mode") and data.get("work_mode"):
                enriched["work_mode"] = data["work_mode"]
            if not enriched.get("salary_min") and data.get("salary_min"):
                enriched["salary_min"] = str(data["salary_min"])
            if not enriched.get("salary_max") and data.get("salary_max"):
                enriched["salary_max"] = str(data["salary_max"])
            if not enriched.get("description") and data.get("description"):
                enriched["description"] = data["description"]
        enhanced.append(enriched)

    return enhanced


def ai_generate_profile_summary(
    name: str,
    skills: str = "",
    experience: str = "",
    target_role: str = "",
    config: LLMConfig | None = None,
) -> str:
    """Generate a professional summary / bio using the LLM."""
    llm = LLMClient(config=config or load_llm_config())

    system_prompt = (
        "You are a professional career coach in Indonesia. Write a concise, "
        "compelling professional summary for a job seeker's profile. "
        "Write in English, 3-4 sentences. Be specific and impactful."
    )

    user_prompt = f"""Generate a professional summary for this person:

Name: {name}
Skills: {skills or 'Not specified'}
Experience: {experience or 'Not specified'}
Target Role: {target_role or 'Not specified'}

The summary should:
1. Open with their professional identity and years of experience
2. Highlight key technical skills
3. Mention their career goal or target role
4. End with a value proposition

Write ONLY the summary text. No title, no labels, no quotes."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return llm.chat(messages, temperature=0.7, max_tokens=2000)


def ai_generate_cv(
    name: str,
    email: str = "",
    phone: str = "",
    linkedin: str = "",
    skills: str = "",
    experience: str = "",
    education: str = "",
    target_role: str = "",
    config: LLMConfig | None = None,
) -> str:
    """Generate a complete CV/resume text using the LLM."""
    llm = LLMClient(config=config or load_llm_config())

    system_prompt = (
        "You are a professional resume writer for the Indonesian tech job market. "
        "Write a clean, ATS-friendly CV in plain text format. "
        "Use clear section headers. Be specific and professional."
    )

    user_prompt = f"""Generate a complete CV for:

Name: {name}
Email: {email}
Phone: {phone}
LinkedIn: {linkedin}
Skills: {skills or 'Not specified'}
Experience: {experience or 'Not specified'}
Education: {education or 'Not specified'}
Target Role: {target_role or 'Not specified'}

Structure the CV with these sections:
1. Header (name + contact info)
2. Professional Summary (3-4 sentences)
3. Technical Skills (grouped by category)
4. Work Experience (use bullet points with action verbs)
5. Education
6. Certifications (if inferrable from skills)

Rules:
- Use professional English
- Be specific with technologies and achievements
- Use action verbs: Developed, Implemented, Designed, Optimized
- Include metrics where possible
- Keep it concise but comprehensive
- Format for ATS readability

Write ONLY the CV text. No markdown code blocks."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return llm.chat(messages, temperature=0.5, max_tokens=8000)
