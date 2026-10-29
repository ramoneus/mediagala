"""Validating, saving and deleting user-uploaded movie images."""

import secrets
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.database import DATA_DIR

POSTER_DIR = DATA_DIR / "posters"
POSTER_DIR.mkdir(exist_ok=True)

MAX_POSTER_BYTES = 10 * 1024 * 1024  # what may be uploaded; what's stored is much smaller (see below)
ACCEPTED_TYPES = "image/jpeg,image/png,image/webp"  # hint for the <input accept="..."> attribute

# Every image is shrunk and re-saved as WebP before it's stored, so a phone photo or an
# online cover of a few MB ends up around 50-150 KB. Raise these for sharper images.
MAX_IMAGE_SIDE = 800  # pixels, longest side
WEBP_QUALITY = 80  # 0-100
MAX_PIXELS = 50_000_000  # refuse "decompression bombs": small files that unpack into huge images


class PosterError(ValueError):
    """The uploaded file can't be used as a movie image."""


def _image_extension(data: bytes) -> str | None:
    """Detect the real image type from its first bytes, ignoring the file name.

    SVG is deliberately not accepted: it can contain scripts.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def read_poster(file: BinaryIO) -> tuple[bytes, str]:
    """Read and validate an upload. Returns (bytes, extension) or raises PosterError."""
    data = file.read(MAX_POSTER_BYTES + 1)
    if not data:
        raise PosterError("The selected file is empty.")
    if len(data) > MAX_POSTER_BYTES:
        raise PosterError("The image is too large (max 10 MB).")
    if _image_extension(data) is None:
        raise PosterError("Please upload a JPG, PNG or WebP image.")
    return _shrink(data), ".webp"


def _shrink(data: bytes) -> bytes:
    """Fit the image within MAX_IMAGE_SIDE and re-encode it as WebP.

    Re-encoding also drops metadata such as a photo's GPS location.
    """
    try:
        with Image.open(BytesIO(data)) as original:
            if original.width * original.height > MAX_PIXELS:
                raise PosterError("The image has too many pixels. Try a smaller one.")
            image = ImageOps.exif_transpose(original)  # keep phone photos the right way up
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            image = image.convert("RGBA" if image.has_transparency_data else "RGB")
            output = BytesIO()
            image.save(output, "WEBP", quality=WEBP_QUALITY)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise PosterError("The image couldn't be read. Try another file.") from exc


def save_poster(data: bytes, extension: str) -> str:
    """Store the image under a random name and return that name."""
    filename = secrets.token_hex(16) + extension
    (POSTER_DIR / filename).write_bytes(data)
    return filename


def delete_poster(filename: str | None) -> None:
    if filename:
        # Path(...).name strips any directory part, so only files in POSTER_DIR can be removed.
        (POSTER_DIR / Path(filename).name).unlink(missing_ok=True)
