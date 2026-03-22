from __future__ import annotations

from pathlib import Path

import pytest

from apps.api.parsers.file_parser import FileParseError, ParsedFile, parse_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> tuple[bytes, str]:
    path = FIXTURES / name
    return path.read_bytes(), name


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


def test_parse_txt_returns_text():
    data, filename = _load("sample.txt")
    result = parse_file(data, filename)
    assert isinstance(result, ParsedFile)
    assert result.extension == ".txt"
    assert result.filename == "sample.txt"
    assert "Hello from a text file" in result.text
    assert result.sheets is None


def test_parse_txt_preserves_unicode():
    data, filename = _load("sample.txt")
    result = parse_file(data, filename)
    assert "café" in result.text


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def test_parse_pdf_returns_parsed_file():
    data, filename = _load("sample.pdf")
    result = parse_file(data, filename)
    assert result.extension == ".pdf"
    assert result.filename == "sample.pdf"
    assert isinstance(result.text, str)
    assert result.sheets is None


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------


def test_parse_excel_returns_sheets():
    data, filename = _load("sample.xlsx")
    result = parse_file(data, filename)
    assert result.extension == ".xlsx"
    assert result.sheets is not None
    assert len(result.sheets) == 2


def test_parse_excel_first_sheet_structure():
    data, filename = _load("sample.xlsx")
    result = parse_file(data, filename)
    sales = result.sheets[0]
    assert sales.name == "Sales"
    assert sales.headers == ["Name", "Region", "Revenue"]
    assert len(sales.rows) == 2
    assert sales.rows[0][0] == "Alice"


def test_parse_excel_text_contains_headers():
    data, filename = _load("sample.xlsx")
    result = parse_file(data, filename)
    assert "Name" in result.text
    assert "Revenue" in result.text
    assert "Alice" in result.text


# ---------------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------------


def test_parse_word_extracts_paragraphs():
    data, filename = _load("sample.docx")
    result = parse_file(data, filename)
    assert result.extension == ".docx"
    assert "first paragraph" in result.text


def test_parse_word_extracts_table():
    data, filename = _load("sample.docx")
    result = parse_file(data, filename)
    assert "Column A" in result.text
    assert "Value 1" in result.text


def test_parse_word_no_sheets():
    data, filename = _load("sample.docx")
    result = parse_file(data, filename)
    assert result.sheets is None


# ---------------------------------------------------------------------------
# Unsupported type
# ---------------------------------------------------------------------------


def test_unsupported_type_raises():
    with pytest.raises(FileParseError, match="Unsupported file type"):
        parse_file(b"data", "file.csv")
