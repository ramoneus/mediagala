"""What every online source shares: the result type, the HTTP calls and text clean-up."""

import html
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

# httpx logs every request's full URL at INFO level, and some API keys travel in the URL
# (TMDB's ?api_key=…). Keep those lines out of the logs whatever logging is set up.
logging.getLogger("httpx").setLevel(logging.WARNING)

TIMEOUT = httpx.Timeout(6.0)
# Wikipedia and Open Library ask API users to say who they are.
HEADERS = {"User-Agent": "MediaGala/1.0 (personal media tracker; https://github.com/ramoneus/mediagala)"}
MAX_RESULTS = 6
MAX_DESCRIPTION = 2000
UNAVAILABLE = "The online database didn't answer. You can still fill in the form by hand."
REFUSED = "The online database refused the request. If it needs an API key, check the one in your .env file."


class LookupFailed(Exception):
    """The online database couldn't be reached or didn't answer as expected."""


@dataclass(frozen=True)
class Match:
    """One result, already translated into the app's own fields."""

    source_id: str
    title: str
    year: int | None
    genre: str  # one of the kind's genres, or "" when none of theirs fits
    description: str
    image_url: str  # full-size image, downloaded when the title is saved
    thumb_url: str  # small image for the list of results
    seasons: tuple[int, ...] = field(default=())  # episodes per season (series and anime)
    author: str = ""  # books
    pages: int | None = None  # books


def _json(response: httpx.Response) -> Any:
    if response.status_code == 404:
        return None
    if response.status_code in (401, 403):
        raise LookupFailed(REFUSED)
    response.raise_for_status()
    return response.json()


def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    """GET a JSON document; None when the service says it doesn't exist (404)."""
    try:
        return _json(httpx.get(url, params=params, timeout=TIMEOUT, headers={**HEADERS, **(headers or {})}))
    except (httpx.HTTPError, ValueError) as exc:
        raise LookupFailed(UNAVAILABLE) from exc


def post_json(url: str, payload: dict[str, Any]) -> Any:
    """POST a JSON body (GraphQL APIs such as AniList)."""
    try:
        return _json(httpx.post(url, json=payload, timeout=TIMEOUT, headers=HEADERS))
    except (httpx.HTTPError, ValueError) as exc:
        raise LookupFailed(UNAVAILABLE) from exc


# --- Text helpers -------------------------------------------------------------


def plain_text(markup: str | None) -> str:
    """Strip HTML tags and Markdown emphasis from summaries, and fit our description limit."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup or "")).replace("*", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= MAX_DESCRIPTION else text[: MAX_DESCRIPTION - 1].rstrip() + "…"


def year_in(text: str | None) -> int | None:
    """The first plausible year in a date or a sentence ("Sep 17, 2020", "2016 film")."""
    found = re.search(r"\b(1[89]\d\d|20\d\d)\b", text or "")
    return int(found.group()) if found else None


def first_genre(candidates: list[str], allowed: tuple[str, ...], aliases: dict[str, str] | None = None) -> str:
    """The first of the service's genres that the app knows, after renaming (e.g. "Science-Fiction")."""
    for name in candidates:
        name = (aliases or {}).get(name, name)
        if name in allowed:
            return name
    return ""


def _find(word: str, text: str) -> re.Match | None:
    return re.search(rf"\b{re.escape(word)}", text)


def genre_from_words(text: str, keywords: list[tuple[str, str]]) -> str:
    """Pick a genre from free text: of the keywords present, the one mentioned first wins.

    "2016 American science fiction drama film" -> "Sci-Fi", because "science fiction" comes before "drama".
    """
    text = text.lower()
    hits = [(found.start(), genre) for word, genre in keywords if (found := _find(word, text))]
    return min(hits)[1] if hits else ""


def genre_by_priority(text: str, keywords: list[tuple[str, str]]) -> str:
    """Pick a genre from free text: the first keyword in the list that appears anywhere wins.

    For text where word order says little, like a book's list of subjects, so the list
    puts specific genres before broad ones ("science fiction" before "fiction").
    """
    text = text.lower()
    return next((genre for word, genre in keywords if _find(word, text)), "")
