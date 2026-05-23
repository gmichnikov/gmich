"""Resize uploaded screenshots before vision API calls."""

import io

from PIL import Image

MAX_EDGE_PX = 1600
JPEG_QUALITY = 85


class ImageProcessingError(ValueError):
    """Uploaded file could not be decoded as an image."""


def prepare_image_for_api(file_storage) -> tuple[bytes, int, int]:
    """
    Decode upload, resize longest edge to MAX_EDGE_PX, return JPEG bytes + dimensions.
    """
    raw = file_storage.read()
    if not raw:
        raise ImageProcessingError("The shared image was empty.")

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except OSError as exc:
        raise ImageProcessingError("Could not read the shared image.") from exc

    image = image.convert("RGB")
    width, height = image.size
    long_edge = max(width, height)

    if long_edge > MAX_EDGE_PX:
        scale = MAX_EDGE_PX / long_edge
        width = max(1, int(width * scale))
        height = max(1, int(height * scale))
        image = image.resize((width, height), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue(), width, height
