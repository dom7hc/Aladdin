"""User uploads: the first untrusted input the platform accepts."""

import io
from datetime import date, datetime, time

import pytest
from openpyxl import Workbook

from app.ingest import spreadsheet as s

SALES_CSV = (
    b"Order Date,Region,Units,Revenue (EUR),Paid\n"
    b"2026-01-03,North,12,1499.50,yes\n"
    b"2026-01-04,South,7,820,no\n"
    b"2026-01-05,North,,1020.25,yes\n"
)


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_csv_columns_get_keys_labels_and_types():
    dataset = s.parse("sales.csv", SALES_CSV)
    assert [(c.key, c.label, c.type) for c in dataset.columns] == [
        ("order_date", "Order Date", "date"),
        ("region", "Region", "text"),
        ("units", "Units", "integer"),
        ("revenue_eur", "Revenue (EUR)", "number"),
        ("paid", "Paid", "boolean"),
    ]
    assert dataset.rows[0] == {
        "order_date": "2026-01-03",
        "region": "North",
        "units": 12,
        "revenue_eur": 1499.5,
        "paid": True,
    }
    # A blank cell is a missing value, not a reason to call the column text.
    assert dataset.rows[2]["units"] is None
    assert dataset.row_count == 3 and not dataset.truncated


def test_semicolon_csv_and_windows_encoding():
    data = "Stadt;Umsatz\nMünchen;10\nKöln;12\n".encode("cp1252")
    dataset = s.parse("de.csv", data)
    assert [c.key for c in dataset.columns] == ["stadt", "umsatz"]
    assert dataset.rows[0] == {"stadt": "München", "umsatz": 10}


def test_duplicate_blank_and_numeric_headers_get_unique_keys():
    dataset = s.parse("x.csv", b"Name,Name,,2026\na,b,c,1\n")
    assert [c.key for c in dataset.columns] == ["name", "name_2", "column_3", "c_2026"]


def test_xlsx_with_real_dates_and_numbers():
    data = _xlsx(
        [
            ["Day", "Visits", "Rate"],
            # Excel stores no zone, so openpyxl hands back naive datetimes.
            [datetime.combine(date(2026, 2, 1), time()), 120, 0.25],
            [date(2026, 2, 2), 98, 0.5],
        ]
    )
    dataset = s.parse("traffic.xlsx", data)
    assert [c.type for c in dataset.columns] == ["date", "integer", "number"]
    assert dataset.rows[1] == {"day": "2026-02-02", "visits": 98, "rate": 0.5}


def test_rows_past_the_cap_are_dropped_and_reported():
    body = "".join(f"{i}\n" for i in range(s.MAX_ROWS + 25))
    dataset = s.parse("big.csv", f"n\n{body}".encode())
    assert len(dataset.rows) == s.MAX_ROWS
    assert dataset.truncated and dataset.row_count == s.MAX_ROWS + 25
    assert "first 5000" in dataset.notes[0]


# Built lazily and given short ids: pytest puts parameters in an environment
# variable, and a multi-megabyte one is over Windows' limit.
REFUSED = {
    "too-big": ("huge.csv", lambda: b"a\n" + b"1\n" * (s.MAX_BYTES // 2 + 1), 413, "larger than"),
    "too-wide": (
        "wide.csv",
        lambda: (",".join(f"c{i}" for i in range(10_000)) + "\n1\n").encode(),
        422,
        "columns",
    ),
    "exe-as-csv": ("renamed.csv", lambda: b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64, 415, "CSV"),
    "exe-as-xlsx": ("renamed.xlsx", lambda: b"MZ\x90\x00\x03\x00\x00\x00", 415, "Excel"),
    "wrong-extension": ("notes.txt", lambda: b"hello", 415, "CSV, Excel"),
    "blank": ("empty.csv", lambda: b"  \n", 422, "empty"),
    "header-only": ("header-only.csv", lambda: b"a,b\n", 422, "no data rows"),
}


@pytest.mark.parametrize("case", list(REFUSED))
def test_unusable_files_are_refused_with_a_reason(case):
    filename, make, status, match = REFUSED[case]
    with pytest.raises(s.DatasetError, match=match) as error:
        s.parse(filename, make())
    assert error.value.status == status


def test_long_cells_are_capped():
    dataset = s.parse("x.csv", ("note\n" + "x" * 2000 + "\n").encode())
    assert len(dataset.rows[0]["note"]) == s.MAX_CELL_CHARS


def test_summary_gives_the_agents_columns_examples_and_ranges():
    summary = s.summary(s.parse("sales.csv", SALES_CSV))
    assert summary["rowCount"] == 3
    region = next(c for c in summary["columns"] if c["key"] == "region")
    assert region["examples"] == ["North", "South"]
    revenue = next(c for c in summary["columns"] if c["key"] == "revenue_eur")
    assert (revenue["min"], revenue["max"]) == (820.0, 1499.5)
    assert len(summary["sampleRows"]) == 3
