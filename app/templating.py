"""Shared Jinja2 environment (autoescaping is enabled for .html templates)."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

templates = Jinja2Templates(directory=APP_DIR / "templates")


def static_url(path: str) -> str:
    """URL of a static file tagged with its modification time.

    When the file changes the URL changes too, so browsers never keep using a stale cached copy.
    """
    version = int((STATIC_DIR / path).stat().st_mtime)
    return f"/static/{path}?v={version}"


templates.env.globals["static_url"] = static_url
