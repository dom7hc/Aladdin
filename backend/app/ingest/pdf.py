"""Read the table in a user's PDF with Claude, then check it like a spreadsheet.

PDFs have no columns to read, so a model transcribes the table. That makes
three layers of trust: Claude reads, the spreadsheet pipeline validates (the
same limits, typing and key rules as an upload), and the user confirms by
seeing the detected columns and first rows before anything is generated.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.ingest import spreadsheet
from app.ingest.spreadsheet import Dataset, DatasetError

# Transcribing 5000 rows is not what a PDF upload is for; this caps how long
# the request can run (the platform's proxy waits 300s) and what it costs.
MAX_OUTPUT_TOKENS = 32_000

READ_NOTE = "Read from the PDF by Claude: check the columns and first rows before generating."

SYSTEM = (
    "You transcribe tables from documents into JSON. Reply with STRICT JSON "
    'only: {"columns": [<header text>], "rows": [[<cell>, ...]]}.\n'
    "Take the document's main data table. If it continues across pages, or "
    "several tables share the same columns, join them into one. Copy every "
    "row exactly as printed: never invent, merge, total or summarise rows, "
    "and leave out subtotal and grand-total lines. Write numbers plainly "
    "(no currency symbols or thousands separators), dates as YYYY-MM-DD when "
    "the document makes the day and month unambiguous, and an empty cell as "
    'null. If there is no table, reply {"columns": [], "rows": []}.'
)
INSTRUCTION = "Transcribe the main table of this document."


class DocumentReader(Protocol):
    async def read_pdf(self, system: str, instruction: str, pdf: bytes, max_tokens: int) -> str: ...


async def parse(filename: str, data: bytes, reader: DocumentReader) -> Dataset:
    if len(data) > spreadsheet.MAX_BYTES:
        raise DatasetError("File is larger than 5 MB.", status=413)
    # Content, not extension: every PDF starts with this signature.
    if not data.lstrip()[:5] == b"%PDF-":
        raise DatasetError("This does not look like a PDF file.", status=415)

    from app.agents.llm import LLMError, _extract_json

    try:
        reply = await reader.read_pdf(SYSTEM, INSTRUCTION, data, MAX_OUTPUT_TOKENS)
        table = _extract_json(reply)
    except LLMError as exc:
        raise DatasetError(f"Could not read the PDF: {exc}", status=502) from exc

    columns, rows = table.get("columns"), table.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise DatasetError("Could not read a table from the PDF.", status=502)
    if not columns or not rows:
        raise DatasetError("No table found in the PDF.")
    cells: list[list[Any]] = [[_cell(c) for c in columns]]
    for row in rows:
        if isinstance(row, list):
            cells.append([_cell(value) for value in row])

    dataset = spreadsheet.build(filename, cells)
    dataset.notes.insert(0, READ_NOTE)
    return dataset


def _cell(value: Any) -> Any:
    # Strings and numbers pass through for type inference; anything nested a
    # model might emit becomes text rather than breaking the pipeline.
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
