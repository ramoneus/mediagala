"""Shared Jinja2 environment (autoescaping is enabled for .html templates)."""

from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.catalog import Status
from app.lookup import available_sources

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

templates = Jinja2Templates(directory=APP_DIR / "templates")


def static_url(path: str) -> str:
    """URL of a static file tagged with its modification time.

    When the file changes the URL changes too, so browsers never keep using a stale cached copy.
    """
    version = int((STATIC_DIR / path).stat().st_mtime)
    return f"/static/{path}?v={version}"


def lookup_sources() -> dict[str, dict[str, str]]:
    """What the online search boxes need for each kind that can be searched: the source's
    name and credit line, the kind's name, and what the kind calls "planned" ("Backlog")."""
    return {
        kind.value: {
            "name": source.name,
            "notice": source.notice,
            "label": kind.label,
            "planned": kind.config.status_labels[Status.PLANNED],
        }
        for kind, source in available_sources().items()
    }


def nice_date(value: date | datetime | None) -> str:
    """12 Oct 2026 (no zero-padded day, the same on every operating system)."""
    return f"{value.day} {value:%b %Y}" if value else ""


templates.env.globals["static_url"] = static_url
templates.env.globals["lookup_sources"] = lookup_sources
templates.env.filters["nice_date"] = nice_date
