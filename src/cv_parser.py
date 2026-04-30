"""Helpers for extracting useful CV information from uploaded files."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import re
import subprocess
import sys
import tempfile

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


@dataclass(slots=True)
class CVAnalysis:
    """Structured summary extracted from a CV."""

    text: str = ""
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    skills: list[str] = field(default_factory=list)


def _normalize_skill_name(skill: str) -> str:
    """Normalize one skill label for display."""
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


def _fallback_python_candidates() -> list[Path]:
    """Return candidate Python interpreters that may have document parser deps."""
    home = Path.home()
    candidates = [
        Path(sys.executable),
        home / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python" / "python.exe",
        home / "AppData" / "Local" / "Python" / "pythoncore-3.14-64" / "python.exe",
    ]

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate).lower()
        if normalized not in seen and candidate.exists():
            unique_candidates.append(candidate)
            seen.add(normalized)
    return unique_candidates


def _extract_with_external_python(data: bytes, mode: str) -> str:
    """Try extracting document text using another Python interpreter."""
    script = """
from io import BytesIO
from pathlib import Path
import sys

mode = sys.argv[1]
file_path = Path(sys.argv[2])
data = file_path.read_bytes()

if mode == "pdf":
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data))
    parts = [page.extract_text() or "" for page in reader.pages]
    print("\\n".join(parts).strip())
elif mode == "docx":
    from docx import Document
    document = Document(BytesIO(data))
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    print("\\n".join(parts).strip())
else:
    raise ValueError(f"Unsupported mode: {mode}")
""".strip()

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{mode}") as temp_file:
        temp_file.write(data)
        temp_path = Path(temp_file.name)

    try:
        for python_path in _fallback_python_candidates():
            try:
                result = subprocess.run(
                    [str(python_path), "-c", script, mode, str(temp_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return result.stdout.strip()
            except subprocess.CalledProcessError:
                continue
    finally:
        temp_path.unlink(missing_ok=True)

    raise ValueError(
        f"{mode.upper()} CV support is not available in the current environment yet. "
        "Please install the required parser dependency in the Python environment used by Streamlit."
    )


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Extract plain text from a PDF byte stream."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return _extract_with_external_python(data, "pdf")

    reader = PdfReader(BytesIO(data))
    parts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(parts).strip()


def extract_text_from_docx_bytes(data: bytes) -> str:
    """Extract plain text from a DOCX byte stream."""
    try:
        from docx import Document
    except ImportError:
        return _extract_with_external_python(data, "docx")

    document = Document(BytesIO(data))
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(parts).strip()


def analyze_cv_text(text: str) -> CVAnalysis:
    """Extract contact info and skills from plain CV text."""
    cleaned = re.sub(r"\r\n?", "\n", text or "").strip()
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""

    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", cleaned, flags=re.IGNORECASE)
    phone_match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", cleaned)
    linkedin_match = re.search(r"https?://(?:www\.)?linkedin\.com/\S+", cleaned, flags=re.IGNORECASE)
    url_matches = re.findall(r"https?://\S+", cleaned, flags=re.IGNORECASE)

    skills: list[str] = []
    lowered = cleaned.casefold()
    for skill in KNOWN_SKILLS:
        pattern = SKILL_PATTERNS.get(skill, rf"\b{re.escape(skill)}\b")
        if re.search(pattern, lowered):
            normalized = _normalize_skill_name(skill)
            if normalized not in skills:
                skills.append(normalized)

    portfolio_url = ""
    for url in url_matches:
        normalized_url = url.rstrip(").,]")
        if linkedin_match and normalized_url == linkedin_match.group(0).rstrip(").,]"):
            continue
        portfolio_url = normalized_url
        break

    name = ""
    if first_line and len(first_line.split()) <= 5 and "@" not in first_line and "http" not in first_line.lower():
        name = first_line

    return CVAnalysis(
        text=cleaned,
        name=name,
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(1).strip() if phone_match else "",
        linkedin_url=linkedin_match.group(0).rstrip(").,]") if linkedin_match else "",
        portfolio_url=portfolio_url,
        skills=skills,
    )


def analyze_cv_bytes(file_name: str, data: bytes) -> CVAnalysis:
    """Analyze a PDF or DOCX CV from raw bytes."""
    suffix = file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    if suffix == "pdf":
        text = extract_text_from_pdf_bytes(data)
    elif suffix == "docx":
        text = extract_text_from_docx_bytes(data)
    else:
        raise ValueError("Unsupported CV format. Please upload a PDF or DOCX file.")

    return analyze_cv_text(text)
