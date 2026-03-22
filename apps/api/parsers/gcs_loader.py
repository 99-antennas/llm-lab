from __future__ import annotations

from pathlib import Path

from clients.google_cloud import get_google_cloud


class GCSLoadError(RuntimeError):
    pass


def load_from_gcs(gcs_uri: str) -> tuple[bytes, str]:
    """Download a file from GCS and return (data, filename).

    Args:
        gcs_uri: A GCS URI in the form gs://bucket-name/path/to/file.ext

    Returns:
        A tuple of (file bytes, filename).
    """
    if not gcs_uri.startswith("gs://"):
        raise GCSLoadError(f"Invalid GCS URI: {gcs_uri!r} — must start with gs://")

    without_scheme = gcs_uri[len("gs://"):]
    parts = without_scheme.split("/", 1)
    if len(parts) != 2 or not parts[1]:
        raise GCSLoadError(f"Invalid GCS URI: {gcs_uri!r} — expected gs://bucket/path")

    bucket_name, blob_path = parts
    filename = Path(blob_path).name

    try:
        gcs = get_google_cloud()
        client = gcs.get_storage_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        if not blob.exists():
            raise GCSLoadError(f"File not found in GCS: {gcs_uri!r}")

        data = blob.download_as_bytes()
    except GCSLoadError:
        raise
    except Exception as exc:
        raise GCSLoadError(f"Failed to download {gcs_uri!r}: {exc}") from exc

    return data, filename
