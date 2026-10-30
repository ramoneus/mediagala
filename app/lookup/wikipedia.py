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


# --- Credits read from the article's opening sentences -------------------------

# Lower-case words that can sit inside a name: "Guillermo del Toro", "Joel and Ethan Coen".
NAME_JOINERS = {"de", "del", "der", "van", "von", "da", "di", "du", "le", "la", "and", "&"}
# Where the names after "directed by" end: punctuation (not the dot of an initial, as in "D. B. Weiss"),
# or a small word that starts the next part of the sentence ("and written by", "with", "who").
CREDIT_END = r"(?=,|;|:|\(|(?<!\b[A-Z])\.|\s(?:and|with|who|from|for|in|on|as|based|under|at|after)\s(?![A-Z])|$)"
NICKNAME = re.compile(r"\s[\"“][^\"”]*[\"”]")  # Eric "ConcernedApe" Barone


def _is_name_word(word: str) -> bool:
    return word[0].isupper() or word[0].isdigit() or word in NAME_JOINERS


def _trailing_name(text: str) -> str:
    """The names at the end of a phrase: "the Swedish company Mojang Studios" -> "Mojang Studios"."""
    words = text.split()
    start = len(words)
    while start and _is_name_word(words[start - 1]):
        start -= 1
    while start < len(words) and words[start] in NAME_JOINERS:  # never start with "and"
        start += 1
    name = " ".join(words[start:])
    return name if len(name) <= 80 else ""


def credit(text: str, verb: str) -> str:
    """Who did it, from a sentence: credit("…film directed by Denis Villeneuve and written by…", "directed")."""
    # Other jobs may come between the verb and "by": "directed, produced, and edited by Joel and Ethan Coen".
    other_jobs = r"(?:,? (?:and )?[a-z-]+)*"
    found = re.search(rf"\b{verb}{other_jobs} by (.+?){CREDIT_END}", NICKNAME.sub("", text))
    return _trailing_name(found.group(1)) if found else ""


def stars(text: str) -> str:
    """ "The film stars Amy Adams as Louise Banks, a linguist…" -> "Amy Adams" (the first few names)."""
    found = re.search(rf"\b(?:(?:film|It|movie) stars|Starring) (.+?)(?:(?<!\b[A-Z])\.|$)", text)
    if not found:
        return ""
    people = []
    for part in re.split(r",\s*(?:and\s+)?|\s+and\s+", found.group(1)):
        person = part.split(" as ")[0].strip()
        if not person or not all(_is_name_word(word) for word in person.split()):
            break  # the list of names is over ("a linguist engaged by…")
        people.append(person)
    return base.names(people)


def movie_facts(text: str) -> tuple[tuple[str, str], ...]:
    return base.facts(("Director", credit(text, "directed")), ("Starring", stars(text)))


def game_facts(text: str) -> tuple[tuple[str, str], ...]:
    both = credit(text, "developed and published")
    if both:
        return base.facts(("Developer & publisher", both), ("Director", credit(text, "directed")))
    return base.facts(
        # "…a role-playing video game by Larian Studios" names only the studio.
        ("Developer", credit(text, "[Dd]eveloped") or credit(text, "game")),
        ("Publisher", credit(text, "published")),
        ("Director", credit(text, "directed")),
    )


# --- Search and details, shared by both ----------------------------------------


def _https(url: str | None) -> str:
    return f"https:{url}" if url and url.startswith("//") else url or ""


def _make_source(
    noun: str,
    unwanted: Callable[[str], bool],
    genre_of: Callable[[str], str],
    facts_of: Callable[[str], tuple[tuple[str, str], ...]],
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
            # The credits are in the opening sentences ("Developed by …, it was released…").
            facts=facts_of(extract[:800]),
            page_url=f"https://en.wikipedia.org/wiki/{quote(page_key)}",
        )

    return search, details


search_movies, movie_details = _make_source(
    "film",
    lambda text: bool(NOT_A_MOVIE.search(text)),
    lambda text: base.genre_from_words(text, MOVIE_GENRES),
    movie_facts,
)
search_games, game_details = _make_source(
    "game", _not_a_game, lambda text: base.genre_by_priority(text, GAME_GENRES), game_facts
)
