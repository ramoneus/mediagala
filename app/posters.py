"""Validating, saving and deleting user-uploaded movie images."""

import secrets
from pathlib import Path
from typing import BinaryIO

from app.database import DATA_DIR

POSTER_DIR = DATA_DIR / "posters"
POSTER_DIR.mkdir(exist_ok=True)

MAX_POSTER_BYTES = 5 * 1024 * 1024
ACCEPTED_TYPES = "image/jpeg,image/png,image/webp"  # hint for the <input accept="..."> attribute


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
        raise PosterError("The image is too large (max 5 MB).")
    extension = _image_extension(data)
    if extension is None:
        raise PosterError("Please upload a JPG, PNG or WebP image.")
    return data, extension


def save_poster(data: bytes, extension: str) -> str:
    """Store the image under a random name and return that name."""
    filename = secrets.token_hex(16) + extension
    (POSTER_DIR / filename).write_bytes(data)
    return filename


def delete_poster(filename: str | None) -> None:
    if filename:
        # Path(...).name strips any directory part, so only files in POSTER_DIR can be removed.
        (POSTER_DIR / Path(filename).name).unlink(missing_ok=True)
