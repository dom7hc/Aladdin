"""Parse a user's CSV or Excel file into typed columns and rows.

Uploads are the first untrusted input this platform accepts, so the limits
below are part of the feature, not a later pass: a file is refused by size,
by content (not by extension alone) and by column count; rows past the cap are
dropped and reported rather than refusing a file a user cannot easily trim.

The output feeds two consumers. The architect sees a summary (columns, types,
a few examples) and designs widgets around columns that actually exist; the
generated backend gets every row as backend/data/dataset.json and computes
its endpoints from them instead of inventing sample data.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 40
MAX_CELL_CHARS = 500
SUMMARY_EXAMPLES = 3
SUMMARY_ROWS = 5

# Order matters: the first type every non-empty value fits wins.
COLUMN_TYPES = ("integer", "number", "date", "boolean", "text")

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d-%m-%Y")
_BOOLEANS = {"true": True, "false": False, "yes": True, "no": False}


class DatasetError(ValueError):
    """The file cannot be used; the message is safe to show the user."""

    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class Column:
    key: str  # snake_case, unique: what endpoints and the spec use
    label: str  # the header as the user wrote it
    type: str  # one of COLUMN_TYPES


@dataclass
class Dataset:
    filename: str
    columns: list[Column]
    rows: list[dict[str, Any]]
    row_count: int  # rows in the file, before the cap
    truncated: bool = False
    notes: list[str] = field(default_factory=list)


def parse(filename: str, data: bytes) -> Dataset:
    if len(data) > MAX_BYTES:
        raise DatasetError(f"File is larger than {MAX_BYTES // (1024 * 1024)} MB.", status=413)
    if not data.strip():
        raise DatasetError("File is empty.")
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        table, cut_at_read = _read_xlsx(data)
    elif lower.endswith(".csv"):
        table, cut_at_read = _read_csv(data), False
    else:
        raise DatasetError("Upload a .csv or .xlsx file.", status=415)
    return _build(filename, table, cut_at_read)


def _read_csv(data: bytes) -> list[list[Any]]:
    # Content, not extension: a renamed binary has NUL bytes no text file has.
    if b"\x00" in data[:4096]:
        raise DatasetError("This does not look like a CSV text file.", status=415)
    text = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise DatasetError("Could not read the file's text encoding; save it as UTF-8 CSV.")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect)]


def _read_xlsx(data: bytes) -> tuple[list[list[Any]], bool]:
    """The first sheet's rows, and whether reading stopped at the row cap."""
    # An .xlsx is a zip with a content-types manifest; anything else is refused
    # before openpyxl ever sees it.
    buffer = io.BytesIO(data)
    if not zipfile.is_zipfile(buffer):
        raise DatasetError("This does not look like an Excel (.xlsx) file.", status=415)
    with zipfile.ZipFile(buffer) as archive:
        if "[Content_Types].xml" not in archive.namelist():
            raise DatasetError("This does not look like an Excel (.xlsx) file.", status=415)
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a zoo of types on bad files
        raise DatasetError(f"Could not open the workbook: {exc}") from exc
    try:
        sheet = workbook.worksheets[0]
        # MAX_ROWS + a header and some blank lines; never read a huge sheet whole.
        limit = MAX_ROWS + 50
        rows = [list(row) for _, row in zip(range(limit + 1), sheet.iter_rows(values_only=True))]
        return rows[:limit], len(rows) > limit
    finally:
        workbook.close()


def _build(filename: str, table: list[list[Any]], cut_at_read: bool = False) -> Dataset:
    rows = [row for row in table if any(_present(cell) for cell in row)]
    if not rows:
        raise DatasetError("No data found in the file.")
    header, body = rows[0], rows[1:]
    width = max(len(row) for row in rows)
    if width > MAX_COLUMNS:
        raise DatasetError(f"The file has {width} columns; the limit is {MAX_COLUMNS}.")
    if not body:
        raise DatasetError("The file has a header row but no data rows.")

    labels = [_clean_label(header[i] if i < len(header) else None, i) for i in range(width)]
    keys = _unique_keys(labels)
    row_count = len(body)
    truncated = row_count > MAX_ROWS or cut_at_read
    body = body[:MAX_ROWS]

    raw_columns = [[row[i] if i < len(row) else None for row in body] for i in range(width)]
    columns: list[Column] = []
    converted: list[list[Any]] = []
    for key, label, values in zip(keys, labels, raw_columns, strict=True):
        column_type = _infer(values)
        columns.append(Column(key=key, label=label, type=column_type))
        converted.append([_convert(value, column_type) for value in values])

    records = [
        {column.key: converted[c][r] for c, column in enumerate(columns)} for r in range(len(body))
    ]
    notes = []
    if cut_at_read:
        notes.append(f"Only the first {MAX_ROWS} rows are used; the sheet has more.")
    elif truncated:
        notes.append(f"Only the first {MAX_ROWS} of {row_count} rows are used.")
    return Dataset(
        filename=filename,
        columns=columns,
        rows=records,
        row_count=row_count,
        truncated=truncated,
        notes=notes,
    )


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _clean_label(value: Any, index: int) -> str:
    text = str(value).strip() if _present(value) else ""
    return text[:80] or f"Column {index + 1}"


def _unique_keys(labels: list[str]) -> list[str]:
    keys: list[str] = []
    for index, label in enumerate(labels):
        key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or f"column_{index + 1}"
        if key[0].isdigit():
            key = f"c_{key}"
        candidate, n = key, 2
        while candidate in keys:
            candidate, n = f"{key}_{n}", n + 1
        keys.append(candidate)
    return keys


def _infer(values: list[Any]) -> str:
    present = [v for v in values if _present(v)]
    if not present:
        return "text"
    for column_type in COLUMN_TYPES[:-1]:
        if all(_fits(v, column_type) for v in present):
            return column_type
    return "text"


def _fits(value: Any, column_type: str) -> bool:
    return _try_convert(value, column_type) is not _NO


_NO = object()


def _try_convert(value: Any, column_type: str) -> Any:
    if column_type == "integer":
        if isinstance(value, bool):
            return _NO
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else _NO
        text = str(value).strip().replace(",", "")
        return int(text) if re.fullmatch(r"[-+]?\d{1,15}", text) else _NO
    if column_type == "number":
        if isinstance(value, bool):
            return _NO
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "").removesuffix("%")
        try:
            return float(text)
        except ValueError:
            return _NO
    if column_type == "date":
        if isinstance(value, datetime):
            return (
                value.date().isoformat()
                if value.time() == datetime.min.time()
                else value.isoformat()
            )
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        for fmt in _DATE_FORMATS:
            try:
                # A calendar date has no zone; only .date() is kept.
                return datetime.strptime(text, fmt).date().isoformat()  # noqa: DTZ007
            except ValueError:
                continue
        return _NO
    if column_type == "boolean":
        if isinstance(value, bool):
            return value
        return _BOOLEANS.get(str(value).strip().lower(), _NO)
    return str(value).strip()[:MAX_CELL_CHARS]


def _convert(value: Any, column_type: str) -> Any:
    if not _present(value):
        return None
    converted = _try_convert(value, column_type)
    return None if converted is _NO else converted


def summary(dataset: Dataset) -> dict[str, Any]:
    """What the agents see: enough to design on, small enough for a prompt."""
    columns = []
    for column in dataset.columns:
        seen: list[Any] = []
        for row in dataset.rows:
            value = row[column.key]
            if value is not None and value not in seen:
                seen.append(value)
            if len(seen) == SUMMARY_EXAMPLES:
                break
        entry: dict[str, Any] = {
            "key": column.key,
            "label": column.label,
            "type": column.type,
            "examples": seen,
        }
        if column.type in ("integer", "number"):
            numbers = [row[column.key] for row in dataset.rows if row[column.key] is not None]
            if numbers:
                entry["min"], entry["max"] = min(numbers), max(numbers)
        columns.append(entry)
    return {
        "filename": dataset.filename,
        "rowCount": len(dataset.rows),
        "columns": columns,
        "sampleRows": dataset.rows[:SUMMARY_ROWS],
    }
