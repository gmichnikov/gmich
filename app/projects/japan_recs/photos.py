"""Japan Recs personal photos stored in Cloudflare R2 (same bucket as Travel Log)."""

import logging
import mimetypes
import re
from datetime import datetime, timezone

from app.services.r2_storage import (
    generate_presigned_download_url,
    get_r2_bucket_name,
    get_r2_client,
    object_exists,
)

PHOTO_PREFIX = "japan_recs/"
PHOTO_PATH_RE = re.compile(
    r"^[a-z0-9][a-z0-9/_-]*\.(jpg|jpeg|png|webp)$",
    re.IGNORECASE,
)
PHOTO_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$", re.IGNORECASE)
PHOTO_URL_EXPIRES = 86400  # 24 hours
ALLOWED_CITIES = ("kyoto", "tokyo")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def normalize_photo_path(path):
    """Validate and normalize a photo path like kyoto/kinkaku-ji.jpg."""
    if not path:
        return None
    normalized = path.strip().lstrip("/")
    if ".." in normalized or not PHOTO_PATH_RE.match(normalized):
        return None
    return normalized


def normalize_slug(slug):
    """Validate a photo slug like bamboo-forest (extension optional)."""
    if not slug:
        return None
    normalized = slug.strip().lstrip("/").lower()
    if "/" in normalized:
        return None
    if "." in normalized:
        stem, ext = normalized.rsplit(".", 1)
        if ext in ("jpg", "jpeg", "png", "webp"):
            normalized = stem
    if not PHOTO_SLUG_RE.match(normalized):
        return None
    return normalized


def build_photo_path(city, slug, extension):
    """Build a photo path from city, slug, and uploaded file extension."""
    city = (city or "").strip().lower()
    slug = normalize_slug(slug)
    if city not in ALLOWED_CITIES or not slug:
        return None
    if extension not in ALLOWED_EXTENSIONS:
        return None
    return normalize_photo_path(f"{city}/{slug}{extension}")


def r2_key(path):
    normalized = normalize_photo_path(path)
    if not normalized:
        return None
    return PHOTO_PREFIX + normalized


def resolve_photo_url(path):
    """Return a presigned R2 URL for the photo, or None if missing/invalid."""
    key = r2_key(path)
    if not key or not object_exists(key):
        return None
    return generate_presigned_download_url(key, expires_in=PHOTO_URL_EXPIRES)


def list_photos():
    """Return metadata for uploaded Japan Recs photos."""
    try:
        client = get_r2_client()
        bucket = get_r2_bucket_name()
    except ValueError:
        return []

    photos = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=PHOTO_PREFIX):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            if not key or key.endswith("/"):
                continue
            path = key[len(PHOTO_PREFIX) :]
            if not normalize_photo_path(path):
                continue
            updated = obj.get("LastModified")
            if isinstance(updated, datetime) and updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            photos.append(
                {
                    "path": path,
                    "size": obj.get("Size", 0),
                    "updated_at": updated,
                }
            )

    photos.sort(key=lambda item: item["path"])
    return photos


def upload_photo(path, file_storage):
    """Upload an image to R2. Returns the normalized path or raises ValueError."""
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a photo file to upload.")

    normalized = normalize_photo_path(path)
    if not normalized:
        raise ValueError(
            "Photo key must look like kyoto/place-name.jpg (letters, numbers, dashes)."
        )

    ext = _extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Upload a JPG, PNG, or WebP image.")

    if not normalized.lower().endswith(ext):
        stem = normalized.rsplit(".", 1)[0]
        normalized = normalize_photo_path(f"{stem}{ext}")
        if not normalized:
            raise ValueError("Could not build a valid photo key from that slug.")

    key = r2_key(normalized)
    content_type = file_storage.content_type or mimetypes.types_map.get(ext, "image/jpeg")

    try:
        client = get_r2_client()
        bucket = get_r2_bucket_name()
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_storage.stream,
            ContentType=content_type,
        )
    except ValueError:
        raise
    except Exception as exc:
        logging.exception("Japan Recs photo upload failed for %s", key)
        raise ValueError("Upload failed. Check R2 credentials and try again.") from exc

    return normalized


def delete_photo(path):
    """Delete a photo from R2. Returns True if deleted."""
    key = r2_key(path)
    if not key:
        raise ValueError("Invalid photo path.")
    try:
        client = get_r2_client()
        bucket = get_r2_bucket_name()
        client.delete_object(Bucket=bucket, Key=key)
        return True
    except ValueError:
        raise
    except Exception as exc:
        logging.exception("Japan Recs photo delete failed for %s", key)
        raise ValueError("Delete failed. Check R2 credentials and try again.") from exc


def photo_key_snippet(path):
    """JS snippet to paste into kyoto.js or tokyo.js."""
    return f'photoKey: "{path}",'


def extension_for_upload(file_storage):
    """Return a normalized extension from an uploaded file."""
    if not file_storage or not file_storage.filename:
        return None
    ext = _extension(file_storage.filename)
    if ext in ALLOWED_EXTENSIONS:
        return ext
    return None


def _extension(filename):
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()

