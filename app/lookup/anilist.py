"""Anime from AniList (https://docs.anilist.co), a free GraphQL API with no key needed.

AniList lists every season of a show as its own entry, so a result fills in one season.
"""

from functools import lru_cache

from app.catalog import SCREEN_GENRES
from app.lookup import base
from app.lookup.base import MAX_RESULTS, Match
from app.schemas import MAX_EPISODES_PER_SEASON

NAME = "AniList"
API = "https://graphql.anilist.co"
GENRE_ALIASES = {
    "Music": "Musical",
    "Supernatural": "Fantasy",
    "Mahou Shoujo": "Fantasy",
    "Mecha": "Sci-Fi",
    "Psychological": "Thriller",
}

FIELDS = "id title { romaji english } startDate { year } genres episodes description coverImage { medium extraLarge }"
SEARCH_QUERY = (
    "query ($q: String) { Page(perPage: %d) { media(search: $q, type: ANIME, isAdult: false, sort: SEARCH_MATCH)"
    " { %s } } }" % (MAX_RESULTS, FIELDS)
)
DETAILS_QUERY = "query ($id: Int) { Media(id: $id, type: ANIME) { %s } }" % FIELDS


def _match(media: dict) -> Match:
    titles = media.get("title") or {}
    cover = media.get("coverImage") or {}
    episodes = media.get("episodes")  # None while a show is still airing
    return Match(
        source_id=str(media["id"]),
        title=titles.get("english") or titles.get("romaji") or "",
        year=(media.get("startDate") or {}).get("year"),
        genre=base.first_genre(media.get("genres") or [], SCREEN_GENRES, GENRE_ALIASES),
        description=base.plain_text(media.get("description")),
        image_url=cover.get("extraLarge") or cover.get("medium") or "",
        thumb_url=cover.get("medium") or "",
        seasons=(min(episodes, MAX_EPISODES_PER_SEASON),) if episodes else (),
    )


@lru_cache(maxsize=128)
def search(query: str) -> tuple[Match, ...]:
    body = base.post_json(API, {"query": SEARCH_QUERY, "variables": {"q": query}}) or {}
    media = ((body.get("data") or {}).get("Page") or {}).get("media") or []
    return tuple(_match(item) for item in media)


@lru_cache(maxsize=128)
def details(media_id: str) -> Match | None:
    if not media_id.isdigit():
        return None
    body = base.post_json(API, {"query": DETAILS_QUERY, "variables": {"id": int(media_id)}}) or {}
    media = (body.get("data") or {}).get("Media")
    return _match(media) if media else None
