"""Tests for application status helpers."""

import pandas as pd
import pytest

from src.applications import (
    DEFAULT_APPLICATION_STATUS,
    ensure_application_columns,
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
