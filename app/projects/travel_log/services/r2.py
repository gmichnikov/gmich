"""Cloudflare R2 presigned URLs for Travel Log photo upload/download."""

import logging
import uuid

from app.services.r2_storage import (
    generate_presigned_download_url,
    get_r2_bucket_name,
    get_r2_client,
)


def generate_presigned_upload_url(key, content_type="image/jpeg", expires_in=300):
    """Generate presigned PUT URL for browser upload. Returns (url, key) or (None, None) on error."""
    try:
        client = get_r2_client()
        bucket = get_r2_bucket_name()
        url = client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return url, key
    except Exception as e:
        logging.exception("R2 presigned upload URL failed: %s", e)
        return None, None


def generate_photo_key(user_id, entry_id):
    """Generate R2 object key: travel_log/{user_id}/{entry_id}/{uuid}.jpg"""
    return f"travel_log/{user_id}/{entry_id}/{uuid.uuid4().hex}.jpg"


__all__ = [
    "generate_presigned_download_url",
    "generate_presigned_upload_url",
    "generate_photo_key",
]
