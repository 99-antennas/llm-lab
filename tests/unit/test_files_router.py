from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.parsers.file_parser import FileParseError, ParsedFile
from apps.api.parsers.gcs_loader import GCSLoadError
from apps.api.routers.files import router

# Minimal app — no Tortoise lifespan, just the files router
_app = FastAPI()
_app.include_router(router)
client = TestClient(_app)

_PARSED = ParsedFile(filename="sample.txt", extension=".txt", text="hello world")
_PARSED_EXCEL = ParsedFile(
    filename="data.xlsx",
    extension=".xlsx",
    text="[Sheet: Sales]\nName\tRevenue",
    sheets=[],
)


# ---------------------------------------------------------------------------
# POST /files/upload
# ---------------------------------------------------------------------------


def test_upload_returns_parsed_file():
    with patch("apps.api.routers.files.parse_file", return_value=_PARSED):
        resp = client.post(
            "/files/upload",
            files={"file": ("sample.txt", b"hello world", "text/plain")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "sample.txt"
    assert body["extension"] == ".txt"
    assert body["text"] == "hello world"
    assert body["sheets"] is None


def test_upload_excel_includes_sheets():
    with patch("apps.api.routers.files.parse_file", return_value=_PARSED_EXCEL):
        resp = client.post(
            "/files/upload",
            files={"file": ("data.xlsx", b"<binary>", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 200
    assert resp.json()["sheets"] == []


def test_upload_parse_error_returns_422():
    with patch(
        "apps.api.routers.files.parse_file",
        side_effect=FileParseError("Unsupported file type: '.bmp'"),
    ):
        resp = client.post(
            "/files/upload",
            files={"file": ("photo.bmp", b"data", "image/bmp")},
        )
    assert resp.status_code == 422
    assert "Unsupported file type" in resp.json()["detail"]


def test_upload_missing_file_returns_422():
    resp = client.post("/files/upload")
    assert resp.status_code == 422


def test_upload_passes_filename_to_parser():
    with patch("apps.api.routers.files.parse_file", return_value=_PARSED) as mock_parse:
        client.post(
            "/files/upload",
            files={"file": ("my_doc.txt", b"content", "text/plain")},
        )
    mock_parse.assert_called_once()
    _, called_filename = mock_parse.call_args.args
    assert called_filename == "my_doc.txt"


# ---------------------------------------------------------------------------
# POST /files/from-gcs
# ---------------------------------------------------------------------------


def test_from_gcs_returns_parsed_file():
    with (
        patch("apps.api.routers.files.load_from_gcs", return_value=(b"hello", "note.txt")),
        patch("apps.api.routers.files.parse_file", return_value=_PARSED),
    ):
        resp = client.post(
            "/files/from-gcs",
            json={"uri": "gs://my-bucket/note.txt"},
        )
    assert resp.status_code == 200
    assert resp.json()["text"] == "hello world"


def test_from_gcs_load_error_returns_422():
    with patch(
        "apps.api.routers.files.load_from_gcs",
        side_effect=GCSLoadError("Bucket not found"),
    ):
        resp = client.post(
            "/files/from-gcs",
            json={"uri": "gs://missing-bucket/file.txt"},
        )
    assert resp.status_code == 422
    assert "Bucket not found" in resp.json()["detail"]


def test_from_gcs_parse_error_returns_422():
    with (
        patch("apps.api.routers.files.load_from_gcs", return_value=(b"data", "file.bmp")),
        patch(
            "apps.api.routers.files.parse_file",
            side_effect=FileParseError("Unsupported file type: '.bmp'"),
        ),
    ):
        resp = client.post(
            "/files/from-gcs",
            json={"uri": "gs://bucket/file.bmp"},
        )
    assert resp.status_code == 422
    assert "Unsupported" in resp.json()["detail"]


def test_from_gcs_missing_uri_returns_422():
    resp = client.post("/files/from-gcs", json={})
    assert resp.status_code == 422


def test_from_gcs_passes_gcs_uri_to_loader():
    with (
        patch("apps.api.routers.files.load_from_gcs", return_value=(b"x", "f.txt")) as mock_load,
        patch("apps.api.routers.files.parse_file", return_value=_PARSED),
    ):
        client.post("/files/from-gcs", json={"uri": "gs://bucket/path/f.txt"})
    mock_load.assert_called_once_with("gs://bucket/path/f.txt")
