from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from apps.api.parsers.file_parser import FileParseError, ParsedFile, parse_file
from apps.api.parsers.gcs_loader import GCSLoadError, load_from_gcs

router = APIRouter(prefix="/files", tags=["files"])


class GCSRequest(BaseModel):
    uri: str


@router.post("/upload", response_model=ParsedFile)
async def upload_file(file: UploadFile) -> ParsedFile:
    """Upload a file and return its parsed contents.

    Supported types: .txt, .pdf, .xlsx, .xls, .docx, .doc
    """
    data = await file.read()
    try:
        return parse_file(data, file.filename or "upload")
    except FileParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/from-gcs", response_model=ParsedFile)
def fetch_from_gcs(request: GCSRequest) -> ParsedFile:
    """Fetch a file from Google Cloud Storage and return its parsed contents.

    Accepts a GCS URI in the form: gs://bucket-name/path/to/file.ext
    """
    try:
        data, filename = load_from_gcs(request.uri)
    except GCSLoadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        return parse_file(data, filename)
    except FileParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
