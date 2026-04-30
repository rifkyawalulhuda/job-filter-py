"""Application tracking helpers for job vacancy records."""

from __future__ import annotations

import pandas as pd

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
