"""Series from TVmaze (https://www.tvmaze.com/api). No key needed; data licensed CC BY-SA."""

from functools import lru_cache

from app.catalog import SCREEN_GENRES
from app.lookup import base
from app.lookup.base import MAX_RESULTS, Match
from app.schemas import MAX_EPISODES_PER_SEASON, MAX_SEASONS

NAME = "TVmaze"
API = "https://api.tvmaze.com"
# TVmaze genres that go by another name in the app; the rest either match or are skipped.
GENRE_ALIASES = {
    "Science-Fiction": "Sci-Fi",
    "Anime": "Animation",
    "Music": "Musical",
    "Supernatural": "Fantasy",
    "Espionage": "Thriller",
    "Children": "Family",
}


def _match(show: dict, seasons: tuple[int, ...] = ()) -> Match:
    image = show.get("image") or {}
    return Match(
        source_id=str(show["id"]),
        title=show.get("name") or "",
        year=base.year_in(show.get("premiered")),
        genre=base.first_genre(show.get("genres") or [], SCREEN_GENRES, GENRE_ALIASES),
        description=base.plain_text(show.get("summary")),
        image_url=image.get("original") or image.get("medium") or "",
        thumb_url=image.get("medium") or "",
        seasons=seasons,
    )


@lru_cache(maxsize=128)
def search(query: str) -> tuple[Match, ...]:
    results = base.get_json(f"{API}/search/shows", {"q": query}) or []
    return tuple(_match(result["show"]) for result in results[:MAX_RESULTS])


@lru_cache(maxsize=128)
def details(show_id: str) -> Match | None:
    if not show_id.isdigit():
        return None
    show = base.get_json(f"{API}/shows/{show_id}", {"embed[]": ["seasons", "episodes"]})
    if not isinstance(show, dict):
        return None
    embedded = show.get("_embedded") or {}
    # Count the listed episodes too: older seasons sometimes have no episode total.
    listed: dict[int, int] = {}
    for episode in embedded.get("episodes") or []:
        listed[episode.get("season")] = listed.get(episode.get("season"), 0) + 1
    counts = []
    for season in embedded.get("seasons") or []:
        count = season.get("episodeOrder") or listed.get(season.get("number"), 0)
        if count:  # skip announced seasons with no episodes yet
            counts.append(min(count, MAX_EPISODES_PER_SEASON))
    return _match(show, tuple(counts[:MAX_SEASONS]))
