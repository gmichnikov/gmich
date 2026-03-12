"""Cloudflare R2 presigned URLs for Travel Log photo upload/download."""

import logging
import uuid

import boto3
from botocore.exceptions import ClientError


def _get_r2_client():
    """S3-compatible client for Cloudflare R2."""
    from flask import current_app
    account_id = current_app.config.get("R2_ACCOUNT_ID")
    access_key = current_app.config.get("R2_ACCESS_KEY_ID")
    secret_key = current_app.config.get("R2_SECRET_ACCESS_KEY")
    if not all((account_id, access_key, secret_key)):
        raise ValueError("R2 credentials not configured")
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def generate_presigned_upload_url(key, content_type="image/jpeg", expires_in=300):
    """Generate presigned PUT URL for browser upload. Returns (url, key) or (None, None) on error."""
    from flask import current_app
    try:
        client = _get_r2_client()
        bucket = current_app.config.get("R2_BUCKET_NAME")
        if not bucket:
            raise ValueError("R2_BUCKET_NAME not configured")
        url = client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return url, key
    except Exception as e:
        logging.exception("R2 presigned upload URL failed: %s", e)
        return None, None


def generate_presigned_download_url(key, expires_in=3600):
    """Generate presigned GET URL for viewing photo. Returns None on error."""
    try:
        from flask import current_app
        client = _get_r2_client()
        bucket = current_app.config.get("R2_BUCKET_NAME")
        if not bucket:
            return None
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception as e:
        logging.exception("R2 presigned download URL failed: %s", e)
        return None


def generate_photo_key(user_id, entry_id):
    """Generate R2 object key: travel_log/{user_id}/{entry_id}/{uuid}.jpg"""
    return f"travel_log/{user_id}/{entry_id}/{uuid.uuid4().hex}.jpg"
