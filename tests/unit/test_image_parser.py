from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from apps.api.parsers.file_parser import FileParseError, ParsedFile, parse_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_png() -> bytes:
    img = Image.new("RGB", (100, 50), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg() -> bytes:
    img = Image.new("RGB", (100, 50), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _mock_claude_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


# ---------------------------------------------------------------------------
# PNG
# ---------------------------------------------------------------------------


def test_parse_png_calls_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    client = _mock_claude_response("Hello world")

    with patch("anthropic.Anthropic", return_value=client):
        result = parse_file(_make_png(), "photo.png")

    assert isinstance(result, ParsedFile)
    assert result.extension == ".png"
    assert result.text == "Hello world"
    assert result.sheets is None


def test_parse_jpeg_media_type(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    client = _mock_claude_response("Some text")

    with patch("anthropic.Anthropic", return_value=client):
        parse_file(_make_jpeg(), "photo.jpg")

    call_kwargs = client.messages.create.call_args
    image_block = call_kwargs.kwargs["messages"][0]["content"][0]
    assert image_block["source"]["media_type"] == "image/jpeg"


def test_parse_jpeg_extension_alias(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    client = _mock_claude_response("ok")

    with patch("anthropic.Anthropic", return_value=client):
        result = parse_file(_make_jpeg(), "photo.jpeg")

    assert result.extension == ".jpeg"


# ---------------------------------------------------------------------------
# Missing API key
# ---------------------------------------------------------------------------


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(FileParseError, match="ANTHROPIC_API_KEY"):
        parse_file(_make_png(), "photo.png")


# ---------------------------------------------------------------------------
# HEIC (conversion path)
# ---------------------------------------------------------------------------


def _make_heic_stub() -> bytes:
    """Return JPEG bytes masquerading as HEIC — enough to test the conversion branch."""
    return _make_jpeg()


def test_heic_converted_to_jpeg_before_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    client = _mock_claude_response("converted")

    # Patch _heic_to_jpeg so we don't need a real HEIC file
    with (
        patch("apps.api.parsers.file_parser._heic_to_jpeg", return_value=_make_jpeg()) as mock_convert,
        patch("anthropic.Anthropic", return_value=client),
    ):
        result = parse_file(_make_heic_stub(), "photo.heic")

    mock_convert.assert_called_once()
    call_kwargs = client.messages.create.call_args
    image_block = call_kwargs.kwargs["messages"][0]["content"][0]
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert result.text == "converted"


# ---------------------------------------------------------------------------
# Unsupported extension still raises
# ---------------------------------------------------------------------------


def test_unsupported_extension_still_raises():
    with pytest.raises(FileParseError, match="Unsupported file type"):
        parse_file(b"data", "file.bmp")
