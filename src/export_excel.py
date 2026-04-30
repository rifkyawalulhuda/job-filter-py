"""Excel export helpers."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Convert a DataFrame into an Excel workbook stored as raw bytes.

    The exported workbook contains a single sheet named ``Filtered Jobs`` with
    a frozen header row, bold headers, and simple auto-sized columns.
    """
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Filtered Jobs", index=False)

        worksheet = writer.book["Filtered Jobs"]
        worksheet.freeze_panes = "A2"

        for cell in worksheet[1]:
            cell.font = Font(bold=True)

        for column_cells in worksheet.columns:
            max_length = 0
            column_letter = column_cells[0].column_letter
            for cell in column_cells:
                cell_value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(cell_value))
            worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 60)

    return buffer.getvalue()


def export_jobs_to_excel(dataframe: pd.DataFrame, output_path: str | Path) -> Path:
    """Export vacancies to an Excel file on disk."""
    path = Path(output_path)
    path.write_bytes(dataframe_to_excel_bytes(dataframe))
    return path
