"""Utilities for loading and normalizing job vacancy data."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
import re

import pandas as pd

REQUIRED_COLUMNS = ("job_title", "company")
OPTIONAL_COLUMNS = (
    "location",
    "work_mode",
    "job_level",
    "salary_min",
    "salary_max",
    "currency",
    "skills",
    "posted_date",
    "job_type",
    "apply_url",
    "description",
)
TEXT_COLUMNS = (
    "job_title",
    "company",
    "location",
    "work_mode",
    "job_level",
    "currency",
    "skills",
    "job_type",
    "apply_url",
    "description",
)


class UploadedFileLike(Protocol):
    """Minimal protocol for uploaded files with a filename."""

    name: str


def _resolve_sample_path(sample_path: str) -> Path:
    """Resolve the sample dataset path relative to the project root when needed."""
    candidate = Path(sample_path)
    if candidate.is_absolute():
        return candidate

    project_root = Path(__file__).resolve().parent.parent
    return project_root / candidate


def _to_snake_case(value: object) -> str:
    """Convert a column label to lowercase snake_case text."""
    text = str(value).strip()
    text = re.sub(r"[\s\-/]+", "_", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^0-9a-zA-Z_]", "", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_").lower()


def load_jobs(
    uploaded_file: UploadedFileLike | None = None,
    sample_path: str = "data/sample_jobs.csv",
) -> pd.DataFrame:
    """Load job data from an uploaded file or from the bundled sample file.

    Parameters
    ----------
    uploaded_file:
        A file-like object with a ``name`` attribute, such as Streamlit's
        uploaded file object. When ``None``, the function loads ``sample_path``.
    sample_path:
        Path to the fallback sample dataset.

    Returns
    -------
    pandas.DataFrame
        A normalized DataFrame with the expected project schema.

    Raises
    ------
    ValueError
        If the file format is unsupported or the required columns are missing.
    """
    source: UploadedFileLike | Path = (
        uploaded_file if uploaded_file is not None else _resolve_sample_path(sample_path)
    )
    file_name = uploaded_file.name if uploaded_file is not None else sample_path
    suffix = Path(file_name).suffix.lower()

    if suffix == ".csv":
        dataframe = pd.read_csv(source)
    elif suffix in {".xlsx", ".xls"}:
        dataframe = pd.read_excel(source)
    else:
        raise ValueError(
            "Unsupported file format. Please upload a CSV or Excel file (.csv, .xlsx, or .xls)."
        )

    return normalize_jobs(dataframe)


def normalize_jobs(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize job vacancy data into a consistent schema.

    The function standardizes column names, validates required fields, adds any
    missing optional columns, converts numeric/date fields, and fills missing
    text values with empty strings.

    Parameters
    ----------
    df:
        The raw job vacancy DataFrame.

    Returns
    -------
    pandas.DataFrame
        A cleaned DataFrame ready for filtering and scoring operations.

    Raises
    ------
    ValueError
        If the required columns ``job_title`` and ``company`` are missing.
    """
    normalized = df.copy()
    normalized.columns = [_to_snake_case(column) for column in normalized.columns]

    missing_required = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing_required:
        missing_text = ", ".join(missing_required)
        raise ValueError(
            "Your file is missing required column(s): "
            f"{missing_text}. Please include at least 'job_title' and 'company'."
        )

    for column in OPTIONAL_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = pd.NA

    normalized["salary_min"] = pd.to_numeric(normalized["salary_min"], errors="coerce")
    normalized["salary_max"] = pd.to_numeric(normalized["salary_max"], errors="coerce")
    normalized["posted_date"] = pd.to_datetime(normalized["posted_date"], errors="coerce")

    for column in TEXT_COLUMNS:
        normalized[column] = normalized[column].fillna("")

    ordered_columns = list(REQUIRED_COLUMNS) + list(OPTIONAL_COLUMNS)
    remaining_columns = [
        column for column in normalized.columns if column not in ordered_columns
    ]
    return normalized.loc[:, ordered_columns + remaining_columns]
