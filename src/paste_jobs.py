"""Helpers for turning pasted job text into structured job rows."""

from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

from src.data_loader import normalize_jobs

FIELD_ALIASES = {
    "job_title": ("job title", "title", "position", "role"),
    "company": ("company", "employer"),
    "location": ("location", "lokasi"),
    "work_mode": ("work mode", "mode kerja", "mode"),
    "job_level": ("job level", "level", "seniority"),
    "salary_min": ("salary min", "minimum salary", "gaji minimum"),
    "salary_max": ("salary max", "maximum salary", "gaji maximum", "gaji maksimum"),
    "currency": ("currency", "mata uang"),
    "skills": ("skills", "skill", "tech stack", "requirements"),
    "posted_date": ("posted date", "posted", "date posted", "tanggal"),
    "job_type": ("job type", "employment type", "type"),
    "apply_url": ("apply url", "apply link", "url", "link"),
    "description": ("description", "desc", "ringkasan"),
}
WORK_MODE_VALUES = ("remote", "hybrid", "onsite", "on-site")
JOB_LEVEL_VALUES = ("internship", "entry", "junior", "mid", "senior", "lead", "manager")
JOB_TYPE_VALUES = ("full-time", "part-time", "contract", "internship", "temporary", "freelance")
KNOWN_SKILLS = (
    "python",
    "sql",
    "react",
    "django",
    "fastapi",
    "postgresql",
    "aws",
    "docker",
    "javascript",
    "excel",
    "typescript",
    "node.js",
    "nodejs",
)
SKILL_PATTERNS = {
    "python": r"\bpython\b",
    "sql": r"\bsql\b",
    "react": r"\breact\b",
    "django": r"\bdjango\b",
    "fastapi": r"\bfastapi\b",
    "postgresql": r"\bpostgresql\b",
    "aws": r"\baws\b",
    "docker": r"\bdocker\b",
    "javascript": r"\bjavascript\b",
    "excel": r"\bexcel\b",
    "typescript": r"\btypescript\b",
    "node.js": r"\bnode\.js\b",
    "nodejs": r"\bnodejs\b",
}
LOCATION_STOPWORDS = {
    "remote",
    "hybrid",
    "onsite",
    "on-site",
    "full-time",
    "part-time",
    "contract",
    "internship",
    "temporary",
    "freelance",
}


def _clean_line(line: str) -> str:
    """Collapse extra whitespace and remove bullet prefixes from one text line."""
    line = re.sub(r"^[\-\*\u2022]+\s*", "", line.strip())
    return re.sub(r"\s+", " ", line)


def _detect_labeled_value(line: str) -> tuple[str, str] | None:
    """Return a normalized field name and value for a labeled line when possible."""
    for field_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            pattern = rf"^{re.escape(alias)}\s*[:\-]\s*(.+)$"
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if match:
                return field_name, match.group(1).strip()
    return None


def _find_first_url(text: str) -> str:
    """Extract the first URL from text, if present."""
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip(").,]") if match else ""


def _contains_letters(text: str) -> bool:
    """Return whether a token contains alphabetical characters."""
    return bool(re.search(r"[A-Za-z]", text))


def _normalize_work_mode(text: str) -> str:
    """Infer work mode from text."""
    lowered = text.casefold()
    for value in WORK_MODE_VALUES:
        if value in lowered:
            return "onsite" if value == "on-site" else value
    return ""


def _normalize_job_level(text: str) -> str:
    """Infer job level from text."""
    lowered = text.casefold()
    for value in JOB_LEVEL_VALUES:
        if value in lowered:
            return value
    return ""


def _normalize_job_type(text: str) -> str:
    """Infer job type from text."""
    lowered = text.casefold()
    for value in JOB_TYPE_VALUES:
        if value in lowered:
            return value
    return ""


def _normalize_skill_name(skill: str) -> str:
    """Normalize one skill label for output."""
    mapping = {
        "python": "Python",
        "sql": "SQL",
        "react": "React",
        "django": "Django",
        "fastapi": "FastAPI",
        "postgresql": "PostgreSQL",
        "aws": "AWS",
        "docker": "Docker",
        "javascript": "JavaScript",
        "excel": "Excel",
        "typescript": "TypeScript",
        "node.js": "Node.js",
        "nodejs": "Node.js",
    }
    return mapping.get(skill.casefold(), skill)


def _infer_skills(text: str) -> str:
    """Infer a semicolon-separated skills string from free text."""
    found: list[str] = []
    lowered = text.casefold()
    for skill in KNOWN_SKILLS:
        pattern = SKILL_PATTERNS.get(skill, rf"\b{re.escape(skill)}\b")
        if re.search(pattern, lowered):
            normalized = _normalize_skill_name(skill)
            if normalized not in found:
                found.append(normalized)
    return ";".join(found)


def _extract_salary_info(text: str) -> tuple[str, str, str]:
    """Extract salary min, max, and currency from free text when possible."""
    lowered = text.casefold()
    currency = ""
    if "idr" in lowered or "rp" in lowered or "rupiah" in lowered:
        currency = "IDR"
    elif "usd" in lowered or "$" in text:
        currency = "USD"

    number_matches = re.findall(
        r"(?:rp|\$|usd|idr)?\s*([\d][\d,\.]*)\s*(?:jt|mio|million|k)?",
        text,
        flags=re.IGNORECASE,
    )
    normalized_numbers = [match.replace(",", "").strip() for match in number_matches if match.strip()]

    if len(normalized_numbers) >= 2:
        return normalized_numbers[0], normalized_numbers[1], currency
    if len(normalized_numbers) == 1:
        return normalized_numbers[0], "", currency
    return "", "", currency


def _split_metadata_tokens(text: str) -> list[str]:
    """Split a metadata line into tokens using common separators."""
    return [token.strip() for token in re.split(r"[|/•·]", text) if token.strip()]


def _looks_like_metadata_token(token: str) -> bool:
    """Return whether a token looks like metadata rather than a company line."""
    lowered = token.casefold()
    return (
        _normalize_work_mode(token) != ""
        or _normalize_job_level(token) != ""
        or _normalize_job_type(token) != ""
        or "ago" in lowered
        or bool(re.search(r"\d", token) and not _contains_letters(token))
    )


def _looks_like_location_token(token: str) -> bool:
    """Return whether a token looks like a location string."""
    lowered = token.casefold()
    if lowered in LOCATION_STOPWORDS or "http" in lowered:
        return False
    return _contains_letters(token) and not _looks_like_metadata_token(token)


def _assign_metadata_tokens(row: dict[str, object], tokens: Iterable[str]) -> None:
    """Fill row fields from generic metadata tokens."""
    for token in tokens:
        if not row["work_mode"]:
            row["work_mode"] = _normalize_work_mode(token)
        if not row["job_level"]:
            row["job_level"] = _normalize_job_level(token)
        if not row["job_type"]:
            row["job_type"] = _normalize_job_type(token)
        if not row["location"] and _looks_like_location_token(token):
            row["location"] = token


def _pick_company_from_candidates(candidates: list[str]) -> str:
    """Choose the most likely company line from unlabeled text lines."""
    for candidate in candidates:
        tokens = _split_metadata_tokens(candidate)
        if len(tokens) >= 2:
            first = tokens[0]
            if first and not _looks_like_metadata_token(first):
                return first
    for candidate in candidates:
        if (
            candidate
            and not _looks_like_metadata_token(candidate)
            and len(candidate.split()) <= 6
            and "http" not in candidate.casefold()
        ):
            return candidate
    return ""


def _extract_unlabeled_candidates(lines: list[str]) -> list[str]:
    """Return non-empty lines that are not labeled metadata or plain URLs."""
    candidates: list[str] = []
    for line in lines:
        if _detect_labeled_value(line):
            continue
        if line.lower().startswith("http://") or line.lower().startswith("https://"):
            continue
        if re.fullmatch(r"(easy apply|apply now|see more|show more)", line, flags=re.IGNORECASE):
            continue
        candidates.append(line)
    return candidates


def _parse_job_block(block: str) -> dict[str, object]:
    """Parse one pasted job block into a structured row."""
    lines = [_clean_line(line) for line in block.splitlines() if _clean_line(line)]
    row: dict[str, object] = {
        "job_title": "",
        "company": "",
        "location": "",
        "work_mode": "",
        "job_level": "",
        "salary_min": "",
        "salary_max": "",
        "currency": "",
        "skills": "",
        "posted_date": "",
        "job_type": "",
        "apply_url": "",
        "description": block.strip(),
    }

    for line in lines:
        labeled = _detect_labeled_value(line)
        if labeled is None:
            continue
        field_name, value = labeled
        row[field_name] = value

    block_text = " ".join(lines)
    if not row["apply_url"]:
        row["apply_url"] = _find_first_url(block_text)
    if not row["work_mode"]:
        row["work_mode"] = _normalize_work_mode(block_text)
    if not row["job_level"]:
        row["job_level"] = _normalize_job_level(block_text)
    if not row["job_type"]:
        row["job_type"] = _normalize_job_type(block_text)
    if not row["skills"]:
        row["skills"] = _infer_skills(block_text)

    salary_min, salary_max, currency = _extract_salary_info(block_text)
    if not row["salary_min"] and salary_min:
        row["salary_min"] = salary_min
    if not row["salary_max"] and salary_max:
        row["salary_max"] = salary_max
    if not row["currency"] and currency:
        row["currency"] = currency

    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b", block_text)
    if not row["posted_date"] and date_match:
        row["posted_date"] = date_match.group(0)

    candidates = _extract_unlabeled_candidates(lines)
    if not row["job_title"] and candidates:
        row["job_title"] = candidates[0]

    if not row["company"] and len(candidates) >= 2:
        metadata_tokens = _split_metadata_tokens(candidates[1])
        if metadata_tokens:
            row["company"] = metadata_tokens[0]
            _assign_metadata_tokens(row, metadata_tokens[1:])

    if not row["company"]:
        row["company"] = _pick_company_from_candidates(candidates[1:])

    if not row["location"] and len(candidates) >= 3:
        metadata_tokens = _split_metadata_tokens(candidates[2])
        _assign_metadata_tokens(row, metadata_tokens)
        if not row["location"] and _looks_like_location_token(candidates[2]):
            row["location"] = candidates[2]

    return row


def parse_pasted_jobs(text: str) -> pd.DataFrame:
    """Parse pasted lowongan text into a normalized DataFrame.

    Jobs should be separated by a blank line. Each block can contain plain lines
    or labeled metadata such as ``Company:`` and ``Location:``.
    """
    if not text.strip():
        raise ValueError("Paste lowongan text first before importing.")

    blocks = [block.strip() for block in re.split(r"\n\s*\n+", text.strip()) if block.strip()]
    rows = [_parse_job_block(block) for block in blocks]
    rows = [
        row
        for row in rows
        if row["job_title"] or row["company"] or row["description"] or row["apply_url"]
    ]
    if not rows:
        raise ValueError(
            "No job entries were detected. Separate each lowongan with a blank line and try again."
        )

    return normalize_jobs(pd.DataFrame(rows))
