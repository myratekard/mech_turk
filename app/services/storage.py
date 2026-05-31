"""Object storage for uploaded screenshots — local disk (dev) or Cloudflare R2 (deployed).

The frontend flow is unchanged in both modes (API-mediated):
  1. POST /api/storage/uploads/request-url  -> { uploadURL, objectPath, metadata }
  2. PUT  <uploadURL>  (raw file body)       -> save_bytes(objectId, data)
  3. GET  /api/storage/objects/<objectId>    -> read_object(objectId) streamed back

Local disk is used unless Cloudflare R2 creds + bucket are configured (settings.use_r2),
in which case bytes are stored in / served from R2. R2 keys are prefixed `uploads/`.
"""
from __future__ import annotations

import mimetypes
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.config import settings

_UPLOAD_DIR = Path(settings.artifact_dir) / "uploads"
_R2_PREFIX = "uploads/"


def _safe_name(name: str) -> str:
    name = name.strip().replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "file"
    return name[:120]


def _key(object_ref: str) -> str:
    """Flatten any objectId / '/objects/<id>' / imageUrl tail to the bare object id."""
    return object_ref.replace("\\", "/").rstrip("/").split("/")[-1]


def new_object_id(file_name: str) -> str:
    return f"{uuid.uuid4().hex}__{_safe_name(file_name)}"


def upload_url_for(object_id: str) -> str:
    # API-mediated upload (same-origin); the PUT handler calls save_bytes.
    return f"/api/storage/upload/{object_id}"


def object_path_for(object_id: str) -> str:
    return f"/objects/{object_id}"


# --------------------------------------------------------------------- R2 (boto3)
@lru_cache(maxsize=1)
def _r2():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=settings.cloudflare_endpoint,
        aws_access_key_id=settings.cloudflare_access_key_id,
        aws_secret_access_key=settings.cloudflare_secret_key,
        region_name="auto",
    )


# --------------------------------------------------------------------- local disk
def _path_for(object_id: str) -> Path:
    return _UPLOAD_DIR / _key(object_id)


# --------------------------------------------------------------------- public API
def save_bytes(object_id: str, data: bytes) -> Optional[Path]:
    if settings.use_r2:
        _r2().put_object(
            Bucket=settings.cloudflare_bucket,
            Key=_R2_PREFIX + _key(object_id),
            Body=data,
            ContentType=mimetypes.guess_type(object_id)[0] or "application/octet-stream",
        )
        return None
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    p = _path_for(object_id)
    p.write_bytes(data)
    return p


def read_object(object_ref: str) -> Optional[bytes]:
    object_id = _key(object_ref)
    if settings.use_r2:
        try:
            obj = _r2().get_object(Bucket=settings.cloudflare_bucket, Key=_R2_PREFIX + object_id)
            return obj["Body"].read()
        except Exception:
            return None
    p = _path_for(object_id)
    return p.read_bytes() if p.exists() else None


def object_file(object_id: str) -> Optional[Path]:
    """Local-disk file path (for FileResponse). None under R2 — the route uses read_object."""
    if settings.use_r2:
        return None
    p = _path_for(object_id)
    return p if p.exists() else None
