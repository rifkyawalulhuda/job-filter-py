"""Local persistence helpers with SQLAlchemy-first SQLite storage."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

DEFAULT_DATABASE_PATH = "job_vacancy_filter.db"

try:
    from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

    SQLALCHEMY_AVAILABLE = True
except ModuleNotFoundError:
    SQLALCHEMY_AVAILABLE = False


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def resolve_database_path(path: str = DEFAULT_DATABASE_PATH) -> Path:
    """Resolve a database file path relative to the project root."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    project_root = Path(__file__).resolve().parent.parent
    return project_root / candidate


if SQLALCHEMY_AVAILABLE:
    class Base(DeclarativeBase):
        """Base class for SQLAlchemy ORM models."""


    class UserProfileRecord(Base):
        """Stored user profile row."""

        __tablename__ = "user_profiles"

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        name: Mapped[str] = mapped_column(String(255), default="")
        email: Mapped[str] = mapped_column(String(255), default="")
        phone: Mapped[str] = mapped_column(String(100), default="")
        linkedin_url: Mapped[str] = mapped_column(String(500), default="")
        portfolio_url: Mapped[str] = mapped_column(String(500), default="")
        updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


    class ApplicationRecord(Base):
        """Stored application tracking row keyed by a stable job fingerprint."""

        __tablename__ = "applications"

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        job_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
        job_title: Mapped[str] = mapped_column(String(255), default="")
        company: Mapped[str] = mapped_column(String(255), default="")
        location: Mapped[str] = mapped_column(String(255), default="")
        apply_url: Mapped[str] = mapped_column(String(1000), default="")
        status: Mapped[str] = mapped_column(String(50), default="Not Applied")
        cover_letter_text: Mapped[str] = mapped_column(Text, default="")
        updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


    _SESSION_FACTORY_CACHE: dict[Path, sessionmaker[Session]] = {}


    def _get_session_factory(path: str = DEFAULT_DATABASE_PATH) -> sessionmaker[Session]:
        """Return a cached SQLAlchemy session factory."""
        resolved_path = resolve_database_path(path)
        if resolved_path not in _SESSION_FACTORY_CACHE:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(
                f"sqlite:///{resolved_path.as_posix()}",
                future=True,
            )
            Base.metadata.create_all(engine)
            _SESSION_FACTORY_CACHE[resolved_path] = sessionmaker(
                bind=engine,
                future=True,
                expire_on_commit=False,
            )
        return _SESSION_FACTORY_CACHE[resolved_path]


    def init_database(path: str = DEFAULT_DATABASE_PATH) -> None:
        """Create the SQLite database and tables if they do not exist yet."""
        session_factory = _get_session_factory(path)
        session_factory.close_all()


    def load_profile_data(path: str = DEFAULT_DATABASE_PATH) -> dict[str, str]:
        """Load user profile data from SQLite or return empty values."""
        session_factory = _get_session_factory(path)
        with session_factory() as session:
            record = session.get(UserProfileRecord, 1)

        if record is None:
            return _empty_profile_data()

        return {
            "name": record.name,
            "email": record.email,
            "phone": record.phone,
            "linkedin_url": record.linkedin_url,
            "portfolio_url": record.portfolio_url,
        }


    def save_profile_data(data: Mapping[str, Any], path: str = DEFAULT_DATABASE_PATH) -> None:
        """Upsert one user profile row into the SQLite database."""
        session_factory = _get_session_factory(path)
        with session_factory() as session:
            record = session.get(UserProfileRecord, 1)
            if record is None:
                record = UserProfileRecord(id=1, updated_at=_utcnow())

            record.name = str(data.get("name", "") or "")
            record.email = str(data.get("email", "") or "")
            record.phone = str(data.get("phone", "") or "")
            record.linkedin_url = str(data.get("linkedin_url", "") or "")
            record.portfolio_url = str(data.get("portfolio_url", "") or "")
            record.updated_at = _utcnow()

            session.add(record)
            session.commit()


    def load_application_status_map(path: str = DEFAULT_DATABASE_PATH) -> dict[str, str]:
        """Load all persisted application statuses keyed by job fingerprint."""
        session_factory = _get_session_factory(path)
        with session_factory() as session:
            records = session.scalars(select(ApplicationRecord)).all()

        return {record.job_key: record.status for record in records}


    def save_application_data(
        job: Mapping[str, Any],
        status: str,
        path: str = DEFAULT_DATABASE_PATH,
        cover_letter_text: str = "",
    ) -> None:
        """Upsert one application tracking row."""
        job_key = build_job_key(job)
        session_factory = _get_session_factory(path)

        with session_factory() as session:
            record = session.scalar(
                select(ApplicationRecord).where(ApplicationRecord.job_key == job_key)
            )
            if record is None:
                record = ApplicationRecord(
                    job_key=job_key,
                    updated_at=_utcnow(),
                )

            record.job_title = str(job.get("job_title", "") or "")
            record.company = str(job.get("company", "") or "")
            record.location = str(job.get("location", "") or "")
            record.apply_url = str(job.get("apply_url", "") or "")
            record.status = status
            if cover_letter_text:
                record.cover_letter_text = cover_letter_text
            record.updated_at = _utcnow()

            session.add(record)
            session.commit()

else:
    def _connect(path: str = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
        """Open a SQLite connection with row access by column name."""
        resolved_path = resolve_database_path(path)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(resolved_path)
        connection.row_factory = sqlite3.Row
        return connection


    def init_database(path: str = DEFAULT_DATABASE_PATH) -> None:
        """Create required SQLite tables using the stdlib sqlite3 fallback."""
        with _connect(path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    linkedin_url TEXT NOT NULL DEFAULT '',
                    portfolio_url TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY,
                    job_key TEXT NOT NULL UNIQUE,
                    job_title TEXT NOT NULL DEFAULT '',
                    company TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    apply_url TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Not Applied',
                    cover_letter_text TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()


    def load_profile_data(path: str = DEFAULT_DATABASE_PATH) -> dict[str, str]:
        """Load user profile data with sqlite3 fallback."""
        init_database(path)
        with _connect(path) as connection:
            row = connection.execute(
                """
                SELECT name, email, phone, linkedin_url, portfolio_url
                FROM user_profiles
                WHERE id = 1
                """
            ).fetchone()

        if row is None:
            return _empty_profile_data()

        return {
            "name": str(row["name"] or ""),
            "email": str(row["email"] or ""),
            "phone": str(row["phone"] or ""),
            "linkedin_url": str(row["linkedin_url"] or ""),
            "portfolio_url": str(row["portfolio_url"] or ""),
        }


    def save_profile_data(data: Mapping[str, Any], path: str = DEFAULT_DATABASE_PATH) -> None:
        """Save user profile data with sqlite3 fallback."""
        init_database(path)
        with _connect(path) as connection:
            connection.execute(
                """
                INSERT INTO user_profiles (
                    id, name, email, phone, linkedin_url, portfolio_url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    email = excluded.email,
                    phone = excluded.phone,
                    linkedin_url = excluded.linkedin_url,
                    portfolio_url = excluded.portfolio_url,
                    updated_at = excluded.updated_at
                """,
                (
                    1,
                    str(data.get("name", "") or ""),
                    str(data.get("email", "") or ""),
                    str(data.get("phone", "") or ""),
                    str(data.get("linkedin_url", "") or ""),
                    str(data.get("portfolio_url", "") or ""),
                    _utcnow().isoformat(),
                ),
            )
            connection.commit()


    def load_application_status_map(path: str = DEFAULT_DATABASE_PATH) -> dict[str, str]:
        """Load application statuses with sqlite3 fallback."""
        init_database(path)
        with _connect(path) as connection:
            rows = connection.execute(
                """
                SELECT job_key, status
                FROM applications
                """
            ).fetchall()

        return {str(row["job_key"]): str(row["status"]) for row in rows}


    def save_application_data(
        job: Mapping[str, Any],
        status: str,
        path: str = DEFAULT_DATABASE_PATH,
        cover_letter_text: str = "",
    ) -> None:
        """Save one application status with sqlite3 fallback."""
        init_database(path)
        with _connect(path) as connection:
            connection.execute(
                """
                INSERT INTO applications (
                    job_key, job_title, company, location, apply_url, status, cover_letter_text, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_key) DO UPDATE SET
                    job_title = excluded.job_title,
                    company = excluded.company,
                    location = excluded.location,
                    apply_url = excluded.apply_url,
                    status = excluded.status,
                    cover_letter_text = CASE
                        WHEN excluded.cover_letter_text <> '' THEN excluded.cover_letter_text
                        ELSE applications.cover_letter_text
                    END,
                    updated_at = excluded.updated_at
                """,
                (
                    build_job_key(job),
                    str(job.get("job_title", "") or ""),
                    str(job.get("company", "") or ""),
                    str(job.get("location", "") or ""),
                    str(job.get("apply_url", "") or ""),
                    status,
                    cover_letter_text,
                    _utcnow().isoformat(),
                ),
            )
            connection.commit()


def _empty_profile_data() -> dict[str, str]:
    """Return a blank profile payload."""
    return {
        "name": "",
        "email": "",
        "phone": "",
        "linkedin_url": "",
        "portfolio_url": "",
    }


def build_job_key(job: Mapping[str, Any]) -> str:
    """Build a stable job fingerprint for persistence and lookups."""
    apply_url = str(job.get("apply_url", "") or "").strip()
    identity_payload = {
        "apply_url": apply_url,
        "job_title": str(job.get("job_title", "") or "").strip().lower(),
        "company": str(job.get("company", "") or "").strip().lower(),
        "location": str(job.get("location", "") or "").strip().lower(),
    }
    normalized_payload = json.dumps(identity_payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized_payload.encode("utf-8")).hexdigest()
