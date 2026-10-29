"""Movies from TMDB (https://developer.themoviedb.org), used only when a free API key is set.

Put the key in a `.env` file as TMDB_API_KEY (see .env.example). Without it, movies are
looked up on Wikipedia instead, so the app works the same out of the box.
"""

import os
from functools import lru_cache

from app.catalog import SCREEN_GENRES
from app.lookup import base
from app.lookup.base import MAX_RESULTS, Match

NAME = "TMDB"
NOTICE = "This product uses the TMDB API but is not endorsed or certified by TMDB."
API = "https://api.themoviedb.org/3"
IMAGES = "https://image.tmdb.org/t/p"
GENRE_ALIASES = {"Science Fiction": "Sci-Fi", "Music": "Musical"}
# Search results name genres by id only; these are TMDB's fixed movie genre ids.
GENRE_NAMES = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime", 99: "Documentary",
    18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Science Fiction", 10770: "TV Movie", 53: "Thriller",
    10752: "War", 37: "Western",
}


def has_key() -> bool:
    return bool(os.environ.get("TMDB_API_KEY", "").strip())


def _auth() -> tuple[dict[str, str], dict[str, str]]:
    """Query parameters and headers that carry the key.

    TMDB's settings page shows two credentials and either one works here: the short
    "API Key" goes in the query string, the long "API Read Access Token" in a header.
    """
    key = os.environ.get("TMDB_API_KEY", "").strip()
    if key.startswith("eyJ"):  # the read access token is a JWT, which always starts like this
        return {}, {"Authorization": f"Bearer {key}"}
    return {"api_key": key}, {}


def _get(path: str, params: dict[str, str] | None = None) -> object:
    auth_params, headers = _auth()
    return base.get_json(f"{API}{path}", {"language": "en-US", **(params or {}), **auth_params}, headers)


def _image(path: str | None, size: str) -> str:
    return f"{IMAGES}/{size}{path}" if path else ""


def _match(movie: dict, genres: list[str] | None = None) -> Match:
    # TMDB tags most movies "Drama", often first ("Drama, Science Fiction"), so it's the fallback.
    genres = sorted(genres or [], key=lambda name: name == "Drama")
    return Match(
        source_id=str(movie["id"]),
        title=movie.get("title") or "",
        year=base.year_in(movie.get("release_date")),
        genre=base.first_genre(genres, SCREEN_GENRES, GENRE_ALIASES),
        description=base.plain_text(movie.get("overview")),
        image_url=_image(movie.get("poster_path"), "w780"),
        thumb_url=_image(movie.get("poster_path"), "w92"),
    )


@lru_cache(maxsize=128)
def search(query: str) -> tuple[Match, ...]:
    body = _get("/search/movie", {"query": query, "include_adult": "false"}) or {}
    return tuple(
        _match(movie, [GENRE_NAMES.get(genre_id, "") for genre_id in movie.get("genre_ids") or []])
        for movie in (body.get("results") or [])[:MAX_RESULTS]
    )


@lru_cache(maxsize=128)
def details(movie_id: str) -> Match | None:
    if not movie_id.isdigit():
        return None
    movie = _get(f"/movie/{movie_id}")
    if not isinstance(movie, dict) or "id" not in movie:
        return None
    return _match(movie, [genre.get("name", "") for genre in movie.get("genres") or []])
