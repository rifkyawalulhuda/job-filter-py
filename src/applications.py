"""Application tracking helpers for job vacancy records."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from src.database import (
    DEFAULT_DATABASE_PATH,
    build_job_key,
    load_application_status_map,
    save_application_data,
)

VALID_APPLICATION_STATUSES = (
    "Not Applied",
    "Draft Ready",
    "Submitted",
    "Failed",
)
DEFAULT_APPLICATION_STATUS = "Not Applied"


def ensure_application_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the DataFrame with an application status column present."""
    result = df.copy()
    if "application_status" not in result.columns:
        result["application_status"] = DEFAULT_APPLICATION_STATUS
    else:
        result["application_status"] = result["application_status"].fillna(DEFAULT_APPLICATION_STATUS)
    return result


def apply_saved_application_statuses(
    df: pd.DataFrame,
    path: str = DEFAULT_DATABASE_PATH,
) -> pd.DataFrame:
    """Overlay persisted application statuses onto a jobs DataFrame copy."""
    result = ensure_application_columns(df)
    if result.empty:
        return result

    status_map = load_application_status_map(path=path)
    if not status_map:
        return result

    for row_index, row in result.iterrows():
        job_key = build_job_key(row.to_dict())
        if job_key in status_map:
            result.at[row_index, "application_status"] = status_map[job_key]
    return result


def update_application_status(df: pd.DataFrame, row_index: int, status: str) -> pd.DataFrame:
    """Return a copy of the DataFrame with one row's application status updated.

    Raises
    ------
    ValueError
        If the requested status is not valid.
    IndexError
        If the row index does not exist in the DataFrame.
    """
    if status not in VALID_APPLICATION_STATUSES:
        raise ValueError(
            "Invalid application status. Expected one of: "
            + ", ".join(VALID_APPLICATION_STATUSES)
        )

    result = ensure_application_columns(df)

    if row_index not in result.index:
        raise IndexError(f"Row index {row_index} is out of range.")

    result.at[row_index, "application_status"] = status
    return result


def persist_application_status(
    job: Mapping[str, object],
    status: str,
    path: str = DEFAULT_DATABASE_PATH,
    cover_letter_text: str = "",
) -> None:
    """Persist one application status update to SQLite."""
    if status not in VALID_APPLICATION_STATUSES:
        raise ValueError(
            "Invalid application status. Expected one of: "
            + ", ".join(VALID_APPLICATION_STATUSES)
        )

    save_application_data(
        job=job,
        status=status,
        path=path,
        cover_letter_text=cover_letter_text,
    )
