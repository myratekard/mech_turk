"""Local object storage emulating the presigned-URL flow the frontend expects.

Flow (see lib/object-storage-web/src/use-upload.ts):
  1. POST /api/storage/uploads/request-url  -> { uploadURL, objectPath, metadata }
  2. PUT <uploadURL>  (raw file body)        -> bytes saved under uploads/<objectId>
  3. GET /api/storage/objects/<objectId>     -> serves the bytes back

objectPath is "/objects/<objectId>"; the frontend builds imageUrl as
"/api/storage/objects/<objectId>".
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from app.core.config import settings

_UPLOAD_DIR = Path(settings.artifact_dir) / "uploads"


def _safe_name(name: str) -> str:
    name = name.strip().replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "file"
    return name[:120]


def new_object_id(file_name: str) -> str:
    return f"{uuid.uuid4().hex}__{_safe_name(file_name)}"


def upload_url_for(object_id: str) -> str:
    # Relative URL — the frontend fetches it same-origin and Vite proxies /api.
    return f"/api/storage/upload/{object_id}"


def object_path_for(object_id: str) -> str:
    return f"/objects/{object_id}"


def _path_for(object_id: str) -> Path:
    # Guard against traversal; object ids are flat.
    object_id = object_id.replace("\\", "/").split("/")[-1]
    return _UPLOAD_DIR / object_id


def save_bytes(object_id: str, data: bytes) -> Path:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    p = _path_for(object_id)
    p.write_bytes(data)
    return p


def read_object(object_ref: str) -> Optional[bytes]:
    """Accepts an objectId, an '/objects/<id>' path, or a full imageUrl tail."""
    object_id = object_ref.replace("\\", "/").rstrip("/").split("/")[-1]
    p = _path_for(object_id)
    return p.read_bytes() if p.exists() else None


def object_file(object_id: str) -> Optional[Path]:
    p = _path_for(object_id)
    return p if p.exists() else None
