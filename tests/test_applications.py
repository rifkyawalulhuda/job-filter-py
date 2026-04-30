"""Tests for application status helpers."""

import pandas as pd
import pytest

from src.applications import (
    DEFAULT_APPLICATION_STATUS,
    apply_saved_application_statuses,
    ensure_application_columns,
    persist_application_status,
    update_application_status,
)


def test_ensure_application_columns_adds_default_status() -> None:
    dataframe = pd.DataFrame([{"job_title": "Backend Engineer"}])

    result = ensure_application_columns(dataframe)

    assert "application_status" in result.columns
    assert result.loc[0, "application_status"] == DEFAULT_APPLICATION_STATUS
    assert "application_status" not in dataframe.columns


def test_update_application_status_returns_updated_copy() -> None:
    dataframe = pd.DataFrame([{"job_title": "Backend Engineer"}])

    result = update_application_status(dataframe, 0, "Submitted")

    assert result.loc[0, "application_status"] == "Submitted"
    assert "application_status" not in dataframe.columns


def test_update_application_status_raises_for_invalid_status() -> None:
    dataframe = pd.DataFrame([{"job_title": "Backend Engineer"}])

    with pytest.raises(ValueError):
        update_application_status(dataframe, 0, "In Review")


def test_update_application_status_raises_for_invalid_index() -> None:
    dataframe = pd.DataFrame([{"job_title": "Backend Engineer"}])

    with pytest.raises(IndexError):
        update_application_status(dataframe, 99, "Submitted")


def test_apply_saved_application_statuses_overlays_persisted_values(tmp_path) -> None:
    database_path = str(tmp_path / "applications.db")
    dataframe = pd.DataFrame(
        [
            {
                "job_title": "Backend Engineer",
                "company": "Acme",
                "location": "Jakarta",
                "apply_url": "https://example.com/jobs/1",
            }
        ]
    )

    persist_application_status(
        dataframe.loc[0].to_dict(),
        "Submitted",
        path=database_path,
    )

    result = apply_saved_application_statuses(dataframe, path=database_path)

    assert result.loc[0, "application_status"] == "Submitted"
