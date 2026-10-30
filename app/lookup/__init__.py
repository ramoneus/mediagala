"""Find titles in free online databases to fill in the add/edit form.

Optional by design: when a service is slow or offline, the form still works by hand.
Each kind lists its sources in order of preference. A source that needs an API key is
used only when the key is set, so out of the box every kind still has a free, key-less
source. Each source module turns its service's answers into the same `Match`, so the
routes and the form treat them all alike.
"""

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.catalog import Kind
from app.lookup import anilist, openlibrary, tmdb, tvmaze, wikipedia
from app.lookup.base import HEADERS, TIMEOUT, LookupFailed, Match
from app.posters import MAX_POSTER_BYTES

__all__ = [
    "LookupFailed", "Match", "Source", "available_sources", "clear_cache", "fetch_image", "source_for", "source_named",
]


@dataclass(frozen=True)
class Source:
    name: str
    search: Callable[[str], tuple[Match, ...]]
    details: Callable[[str], Match | None]
    notice: str = ""  # attribution some services ask to show next to their data
    enabled: Callable[[], bool] = lambda: True  # False while a needed API key is missing


WIKIPEDIA_MOVIES = Source(wikipedia.NAME, wikipedia.search_movies, wikipedia.movie_details)
WIKIPEDIA_GAMES = Source(wikipedia.NAME, wikipedia.search_games, wikipedia.game_details)
TMDB = Source(tmdb.NAME, tmdb.search, tmdb.details, notice=tmdb.NOTICE, enabled=tmdb.has_key)

SOURCES: dict[Kind, tuple[Source, ...]] = {
    Kind.MOVIE: (TMDB, WIKIPEDIA_MOVIES),
    Kind.SERIES: (Source(tvmaze.NAME, tvmaze.search, tvmaze.details),),
    Kind.ANIME: (Source(anilist.NAME, anilist.search, anilist.details),),
    Kind.GAME: (WIKIPEDIA_GAMES,),
    Kind.BOOK: (Source(openlibrary.NAME, openlibrary.search, openlibrary.details),),
}


def source_for(kind: Kind) -> Source | None:
    """The preferred source that can be used right now."""
    return next((source for source in SOURCES.get(kind, ()) if source.enabled()), None)


def source_named(kind: Kind, name: str) -> Source | None:
    """The source a title was picked from, if it can still be used (TMDB needs its key)."""
    return next((s for s in SOURCES.get(kind, ()) if s.name == name and s.enabled()), None)


def available_sources() -> dict[Kind, Source]:
    return {kind: source for kind in Kind if (source := source_for(kind))}


def clear_cache() -> None:
    for sources in SOURCES.values():
        for source in sources:
            source.search.cache_clear()
            source.details.cache_clear()


# --- Images -------------------------------------------------------------------

# Images are only ever downloaded from these sites (and their subdomains), never from any
# URL the browser sends. archive.org is where Open Library's covers redirect to.
IMAGE_DOMAINS = (
    "image.tmdb.org",
    "upload.wikimedia.org",
    "static.tvmaze.com",
    "anilist.co",
    "covers.openlibrary.org",
    "archive.org",
)
BAD_IMAGE = "That image can't be used. Pick a title from the search results again."


def _allowed(url: httpx.URL) -> bool:
    host = url.host or ""
    return url.scheme == "https" and any(host == d or host.endswith("." + d) for d in IMAGE_DOMAINS)


def _check_each_request(request: httpx.Request) -> None:
    # Runs for the first request and for every redirect, so a redirect can't lead elsewhere.
    if not _allowed(request.url):
        raise LookupFailed(BAD_IMAGE)


def _download(url: str, limit: int) -> bytes:
    """Read at most limit + 1 bytes, so an oversized file is detected without fetching all of it."""
    data = bytearray()
    hooks = {"request": [_check_each_request]}
    try:
        with httpx.Client(timeout=TIMEOUT, headers=HEADERS, follow_redirects=True, event_hooks=hooks) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    data += chunk
                    if len(data) > limit:
                        break
    except httpx.HTTPError as exc:
        raise LookupFailed("The image couldn't be downloaded. Try again or upload one yourself.") from exc
    return bytes(data)


def fetch_image(url: str) -> bytes:
    """Download a cover picked from the search results (only from the sources' image sites)."""
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL:
        raise LookupFailed(BAD_IMAGE) from None
    if not _allowed(parsed) or urlsplit(url).username:
        raise LookupFailed(BAD_IMAGE)
    return _download(url, MAX_POSTER_BYTES)
