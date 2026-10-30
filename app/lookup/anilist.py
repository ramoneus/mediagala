"""Anime from AniList (https://docs.anilist.co), a free GraphQL API with no key needed.

AniList lists every season of a show as its own entry, so a result fills in one season.
"""

from dataclasses import replace
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
DETAIL_FIELDS = (
    "format status duration averageScore source studios(isMain: true) { nodes { name } } trailer { id site }"
)
DETAILS_QUERY = "query ($id: Int) { Media(id: $id, type: ANIME) { %s %s } }" % (FIELDS, DETAIL_FIELDS)
# AniList's codes, in words.
FORMATS = {"TV": "TV series", "TV_SHORT": "TV short", "MOVIE": "Movie", "SPECIAL": "Special", "OVA": "OVA",
           "ONA": "Web series", "MUSIC": "Music video"}
STATUSES = {"FINISHED": "Finished", "RELEASING": "Airing", "NOT_YET_RELEASED": "Not aired yet",
            "CANCELLED": "Cancelled", "HIATUS": "On hiatus"}
ORIGINS = {"MANGA": "Manga", "LIGHT_NOVEL": "Light novel", "NOVEL": "Novel", "VISUAL_NOVEL": "Visual novel",
           "VIDEO_GAME": "Video game", "WEB_NOVEL": "Web novel", "ORIGINAL": "Original story"}


def _facts(media: dict) -> tuple[tuple[str, str], ...]:
    studios = (media.get("studios") or {}).get("nodes") or []
    average = media.get("averageScore")  # out of 100
    return base.facts(
        ("Studio", base.names([studio.get("name") for studio in studios], 2)),
        ("Format", FORMATS.get(media.get("format") or "", "")),
        ("Based on", ORIGINS.get(media.get("source") or "", "")),
        ("Status", STATUSES.get(media.get("status") or "", "")),
        ("Episode length", base.duration(media.get("duration"))),
        ("Rating on AniList", base.score(average / 10 if average else None, 10)),
    )


def _trailer(media: dict) -> str:
    trailer = media.get("trailer") or {}
    return base.youtube(trailer.get("id")) if trailer.get("site") == "youtube" else ""


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
    if not media:
        return None
    return replace(
        _match(media), facts=_facts(media), page_url=f"https://anilist.co/anime/{media_id}", trailer_url=_trailer(media)
    )
