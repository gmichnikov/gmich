#!/usr/bin/env python3
"""Upload a Japan Recs photo to Cloudflare R2 (same bucket as Travel Log).

Usage:
  python scripts/upload_japan_recs_photo.py kyoto/sushi-no-musashi.jpg path/to/photo.jpg

The first argument is the path used in place data (photoKey). The object is stored as
japan_recs/<path> in your R2 bucket.

Requires R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME.
"""

import mimetypes
import os
import re
import sys

import boto3

PHOTO_PREFIX = "japan_recs/"
PHOTO_PATH_RE = re.compile(
    r"^[a-z0-9][a-z0-9/_-]*\.(jpg|jpeg|png|webp)$",
    re.IGNORECASE,
)


def normalize_photo_path(path):
    if not path:
        return None
    normalized = path.strip().lstrip("/")
    if ".." in normalized or not PHOTO_PATH_RE.match(normalized):
        return None
    return normalized


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip())
        sys.exit(1)

    photo_path = normalize_photo_path(sys.argv[1])
    local_path = sys.argv[2]
    if not photo_path:
        print("Invalid photo path. Use something like kyoto/sushi-no-musashi.jpg")
        sys.exit(1)
    if not os.path.isfile(local_path):
        print(f"File not found: {local_path}")
        sys.exit(1)

    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket = os.getenv("R2_BUCKET_NAME")
    if not all((account_id, access_key, secret_key, bucket)):
        print("Missing R2_* environment variables.")
        sys.exit(1)

    key = PHOTO_PREFIX + photo_path
    content_type = mimetypes.guess_type(local_path)[0] or "image/jpeg"

    client = boto3.client(
        service_name="s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )

    with open(local_path, "rb") as handle:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=handle,
            ContentType=content_type,
        )

    print(f"Uploaded s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
