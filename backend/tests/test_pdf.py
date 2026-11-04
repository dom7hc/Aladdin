"""PDF uploads: Claude transcribes, the spreadsheet pipeline checks."""

import json

import pytest

from app.agents.llm import LLMError
from app.ingest import pdf
from app.ingest.spreadsheet import DatasetError

PDF = b"%PDF-1.7\n...binary..."


class FakeReader:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    async def read_pdf(self, system, instruction, data, max_tokens):
        self.calls.append({"system": system, "data": data, "max_tokens": max_tokens})
        if self.error:
            raise self.error
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


async def test_table_goes_through_the_spreadsheet_checks():
    reader = FakeReader(
        {
            "columns": ["Invoice", "Date", "Amount (EUR)", "Paid"],
            "rows": [["INV-1", "2026-03-01", 1200.5, "yes"], ["INV-2", "2026-03-04", "980", "no"]],
        }
    )
    dataset = await pdf.parse("invoices.pdf", PDF, reader)
    assert [(c.key, c.type) for c in dataset.columns] == [
        ("invoice", "text"),
        ("date", "date"),
        ("amount_eur", "number"),
        ("paid", "boolean"),
    ]
    assert dataset.rows[1] == {
        "invoice": "INV-2",
        "date": "2026-03-04",
        "amount_eur": 980.0,
        "paid": False,
    }
    # The user is told where the numbers came from, first.
    assert dataset.notes[0] == pdf.READ_NOTE
    assert reader.calls[0]["data"] == PDF
    assert reader.calls[0]["max_tokens"] == pdf.MAX_OUTPUT_TOKENS


async def test_reply_in_a_code_fence_is_accepted():
    reply = '```json\n{"columns": ["a"], "rows": [[1], [2]]}\n```'
    dataset = await pdf.parse("x.pdf", PDF, FakeReader(reply))
    assert dataset.rows == [{"a": 1}, {"a": 2}]


async def test_odd_cells_become_text_rather_than_failing():
    dataset = await pdf.parse(
        "x.pdf", PDF, FakeReader({"columns": ["a"], "rows": [[{"nested": 1}], [None]]})
    )
    assert dataset.rows[0]["a"] == "{'nested': 1}"


@pytest.mark.parametrize(
    ("data", "reader", "status", "match"),
    [
        (b"MZ\x90\x00", FakeReader({}), 415, "PDF"),
        (b"%PDF-" + b"x" * (5 * 1024 * 1024), FakeReader({}), 413, "larger than"),
        (PDF, FakeReader({"columns": [], "rows": []}), 422, "No table"),
        (PDF, FakeReader("I cannot see a table, sorry."), 502, "Could not read"),
        (PDF, FakeReader(error=LLMError("Claude declined the request")), 502, "declined"),
        (PDF, FakeReader({"columns": "a,b", "rows": []}), 502, "Could not read a table"),
    ],
    ids=["not-a-pdf", "too-big", "no-table", "prose-reply", "refusal", "bad-shape"],
)
async def test_unusable_pdfs_are_refused_with_a_reason(data, reader, status, match):
    with pytest.raises(DatasetError, match=match) as error:
        await pdf.parse("x.pdf", data, reader)
    assert error.value.status == status


async def test_a_refused_file_never_reaches_claude():
    reader = FakeReader({"columns": ["a"], "rows": [[1]]})
    with pytest.raises(DatasetError):
        await pdf.parse("renamed.pdf", b"MZ\x90\x00", reader)
    assert reader.calls == []
