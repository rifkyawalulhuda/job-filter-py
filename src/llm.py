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
            return data["choices"][0]["message"]["content"]
        except requests.RequestException as exc:
            raise RuntimeError(f"LLM API request failed: {exc}") from exc
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Unexpected LLM API response: {exc}"
            ) from exc


# ── AI Features ──────────────────────────────────────────────────────────────


def generate_ai_cover_letter(
    job_title: str,
    company: str,
    location: str,
    skills_text: str,
    applicant_name: str,
    cv_summary: str = "",
    tone: str = "formal",
    config: LLMConfig | None = None,
) -> str:
    """Generate a personalized cover letter using the LLM."""
    llm = LLMClient(config=config or load_llm_config())

    tone_instruction = {
        "formal": "Write in a professional, formal tone suitable for corporate applications.",
        "concise": "Keep it brief and to the point. Short paragraphs, no fluff.",
        "confident": "Use a confident, assertive tone that highlights achievements.",
    }.get(tone, "Write in a professional tone.")

    system_prompt = (
        "You are a professional cover letter writer for job applications in Indonesia. "
        "Write in a natural mix of English and Indonesian where appropriate. "
        "Keep it to 3-4 short paragraphs. Do NOT use placeholder brackets like [Name] or [Company]."
    )

    user_prompt = f"""Write a cover letter for this job:

Job Title: {job_title}
Company: {company}
Location: {location}
Skills Required: {skills_text or 'Not specified'}

Applicant Name: {applicant_name}
{f'CV Summary: {cv_summary}' if cv_summary else ''}

{tone_instruction}

The letter should:
1. Open with a strong introduction expressing interest in the role
2. Connect the applicant's background to the job requirements
3. Show enthusiasm for the company
4. Close with a call to action

Include the applicant's name at the top and end with 'Sincerely,' followed by the name."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return llm.chat(messages, temperature=0.7, max_tokens=1000)


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
