"""Movies and video games from English Wikipedia (https://en.wikipedia.org/w/rest.php), free and with no key.

Wikipedia has no "movies" or "games" API, so the search keeps the pages whose short description
calls them a film or a game ("2016 American science fiction drama film", "2017 video game").
The description and the article's first sentence also give the year and the genre.
Covers and posters on Wikipedia are non-free images, kept at low resolution by Wikipedia.
"""

import re
from collections.abc import Callable
from functools import lru_cache
from urllib.parse import quote

from app.lookup import base
from app.lookup.base import MAX_RESULTS, Match

NAME = "Wikipedia"
SEARCH_API = "https://en.wikipedia.org/w/rest.php/v1/search/title"
SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary"

# --- What counts as a movie or a game, and their genres ------------------------

NOT_A_MOVIE = re.compile(
    r"\b(soundtrack|album|song|score|series|franchise|character|novel|festival|award|video game)\b"
)
# Movies: the genre named first in "2016 American science fiction drama film" wins.
MOVIE_GENRES = [
    ("science fiction", "Sci-Fi"),
    ("sci-fi", "Sci-Fi"),
    ("space opera", "Sci-Fi"),
    ("cyberpunk", "Sci-Fi"),
    ("animated", "Animation"),
    ("documentary", "Documentary"),
    ("horror", "Horror"),
    ("thriller", "Thriller"),
    ("psychological", "Thriller"),
    ("spy", "Thriller"),
    ("comedy", "Comedy"),
    ("satirical", "Comedy"),
    ("musical", "Musical"),
    ("western", "Western"),
    ("war", "War"),
    ("crime", "Crime"),
    ("heist", "Crime"),
    ("gangster", "Crime"),
    ("noir", "Crime"),
    ("mystery", "Mystery"),
    ("romantic", "Romance"),
    ("romance", "Romance"),
    ("fantasy", "Fantasy"),
    ("adventure", "Adventure"),
    ("action", "Action"),
    ("superhero", "Action"),
    ("disaster", "Action"),
    ("family", "Family"),
    ("drama", "Drama"),
    ("biographical", "Drama"),
    ("coming-of-age", "Drama"),
]

ABOUT_A_GAME = re.compile(
    r"\b(series|franchise|character|soundtrack|album|television|engine|console|company|studio|developer|publisher"
    r"|designer|director|composer|awards?|convention|festival|magazine|website|genre|mechanic|theory|tournament"
    # "Music from the video game Hollow Knight", "Board game based on the video game Stardew Valley"
    r"|league)\b|\b(from|in|of|on|for) the (video )?game\b"
)
UNPLUGGED = re.compile(r"\b(board|card|tabletop|dice)\b")
PLUGGED_IN = re.compile(r"\b(video|digital|online|mobile|browser)\b")


def _not_a_game(description: str) -> bool:
    if ABOUT_A_GAME.search(description):
        return True
    # A card or board game counts only when it's a video game too ("digital collectible card game").
    return bool(UNPLUGGED.search(description)) and not PLUGGED_IN.search(description)
# Games: "action role-playing game" is an RPG and "Metroidvania action-adventure game" a platformer,
# so specific genres are listed first and the first one found anywhere wins.
GAME_GENRES = [
    ("fighting", "Fighting"),
    ("beat 'em up", "Fighting"),
    ("racing", "Racing"),
    ("sports", "Sports"),
    ("football", "Sports"),
    ("golf", "Sports"),
    ("shooter", "Shooter"),
    ("battle royale", "Shooter"),
    ("puzzle", "Puzzle"),  # before platformer: "puzzle-platform game" (Portal) is a puzzle game
    ("platform game", "Platformer"),
    ("platform video game", "Platformer"),
    ("platformer", "Platformer"),
    ("metroidvania", "Platformer"),
    ("horror", "Horror"),
    ("survival", "Survival"),
    ("strategy", "Strategy"),
    ("tactics", "Strategy"),
    ("tower defense", "Strategy"),
    ("deck-building", "Strategy"),
    ("card game", "Strategy"),
    ("simulation", "Simulation"),
    ("city-building", "Simulation"),
    ("role-playing", "RPG"),
    ("role playing", "RPG"),
    ("adventure", "Adventure"),
    ("visual novel", "Adventure"),
    ("point-and-click", "Adventure"),
    ("action", "Action"),
    ("hack and slash", "Action"),
    ("stealth", "Action"),
    ("indie", "Indie"),
]


# --- Search and details, shared by both ----------------------------------------


def _https(url: str | None) -> str:
    return f"https:{url}" if url and url.startswith("//") else url or ""


def _make_source(
    noun: str, unwanted: Callable[[str], bool], genre_of: Callable[[str], str]
) -> tuple[Callable[[str], tuple[Match, ...]], Callable[[str], Match | None]]:
    """Build the search and details functions for one kind of page ("film" or "game")."""

    def wanted(description: str) -> bool:
        description = description.lower()
        return bool(re.search(rf"\b{noun}\b", description)) and not unwanted(description)

    def clean_title(title: str) -> str:
        # "Arrival (film)", "Hades (2020 video game)" -> the title itself.
        return re.sub(rf"\s*\((?:[^()]*\s)?{noun}\)$", "", title)

    @lru_cache(maxsize=128)
    def search(query: str) -> tuple[Match, ...]:
        body = base.get_json(SEARCH_API, {"q": query, "limit": 20}) or {}
        matches = [
            Match(
                source_id=page["key"],
                title=clean_title(page.get("title") or ""),
                # "God of War (2018 video game)": the page title tells same-named games apart.
                year=base.year_in(page.get("description")) or base.year_in(page.get("title")),
                genre=genre_of(page.get("description") or ""),
                description="",
                image_url="",
                thumb_url=_https((page.get("thumbnail") or {}).get("url")),
            )
            for page in body.get("pages") or []
            if wanted(page.get("description") or "")
        ]
        return tuple(matches[:MAX_RESULTS])

    @lru_cache(maxsize=128)
    def details(page_key: str) -> Match | None:
        if not page_key or "/" in page_key:
            return None
        page = base.get_json(f"{SUMMARY_API}/{quote(page_key)}")
        if not isinstance(page, dict) or page.get("type") != "standard":
            return None
        description = page.get("description") or ""
        extract = page.get("extract") or ""
        # "Hades is a 2020 roguelike action role-playing game…" says more than "2020 video game".
        first_sentence = extract.split(". ")[0]
        image = _https((page.get("originalimage") or page.get("thumbnail") or {}).get("source"))
        return Match(
            source_id=page_key,
            title=clean_title(page.get("title") or ""),
            # Some short descriptions have no year ("Sandbox video game"); then look further.
            year=base.year_in(description) or base.year_in(first_sentence) or base.year_in(extract),
            genre=genre_of(f"{description} {first_sentence}"),
            description=base.plain_text(extract),
            image_url=image,
            thumb_url=image,
        )

    return search, details


search_movies, movie_details = _make_source(
    "film", lambda text: bool(NOT_A_MOVIE.search(text)), lambda text: base.genre_from_words(text, MOVIE_GENRES)
)
search_games, game_details = _make_source(
    "game", _not_a_game, lambda text: base.genre_by_priority(text, GAME_GENRES)
)
