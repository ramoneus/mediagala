"""The app's vocabulary: kinds of titles, statuses, and what each kind supports.

Every kind-specific rule (allowed statuses, their labels, genres, episode tracking)
lives here, so adding a new kind such as books is mostly one new KIND_CONFIG entry.
"""

import enum
from dataclasses import dataclass


class Kind(enum.StrEnum):
    MOVIE = "movie"
    SERIES = "series"
    ANIME = "anime"
    GAME = "game"
    BOOK = "book"

    @property
    def config(self) -> "KindConfig":
        return KIND_CONFIG[self]

    @property
    def label(self) -> str:
        return self.config.label

    @property
    def has_episodes(self) -> bool:
        return self.config.has_episodes

    @property
    def has_pages(self) -> bool:
        return self.config.has_pages


class Status(enum.StrEnum):
    """Where a title stands. Each kind shows its own labels (e.g. "Watched" vs "Completed").

    The stored values date from when the app only tracked movies; keeping them
    means existing databases need no data migration.
    """

    PLANNED = "watchlist"
    IN_PROGRESS = "watching"
    FINISHED = "watched"
    DROPPED = "dropped"


class Completion(enum.StrEnum):
    """How far a finished game was played."""

    STORY = "story"
    STORY_DLC = "story_dlc"
    FULL = "full"

    @property
    def label(self) -> str:
        return COMPLETION_LABELS[self]


COMPLETION_LABELS = {
    Completion.STORY: "Story",
    Completion.STORY_DLC: "Story + DLC",
    Completion.FULL: "100% completion",
}

SCREEN_GENRES: tuple[str, ...] = (
    "Action",
    "Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "Horror",
    "Musical",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "War",
    "Western",
)

GAME_GENRES: tuple[str, ...] = (
    "Action",
    "Adventure",
    "Fighting",
    "Horror",
    "Indie",
    "Platformer",
    "Puzzle",
    "Racing",
    "RPG",
    "Shooter",
    "Simulation",
    "Sports",
    "Strategy",
    "Survival",
)

BOOK_GENRES: tuple[str, ...] = (
    "Fiction",
    "Classics",
    "Fantasy",
    "Sci-Fi",
    "Mystery",
    "Thriller",
    "Horror",
    "Romance",
    "Historical Fiction",
    "Non-fiction",
    "Biography",
    "History",
    "Science",
    "Philosophy",
    "Self-help",
    "Poetry",
    "Comics & Manga",
)

ALL_GENRES: tuple[str, ...] = tuple(sorted(set(SCREEN_GENRES) | set(GAME_GENRES) | set(BOOK_GENRES)))


@dataclass(frozen=True)
class KindConfig:
    label: str
    plural: str
    genres: tuple[str, ...]
    # The statuses this kind allows, in display order, with the label shown for each.
    status_labels: dict[Status, str]
    year_label: str = "Release year"
    # Where you watch, play or read it: the field's name and the suggestions offered while typing.
    platform_label: str = "Where"
    platforms: tuple[str, ...] = ()
    # Seasons, episodes and "last episode watched" tracking.
    has_episodes: bool = False
    # Author, page count and "current page" tracking.
    has_pages: bool = False

    @property
    def statuses(self) -> tuple[Status, ...]:
        return tuple(self.status_labels)


STREAMING = ("Netflix", "Disney+", "Prime Video", "HBO Max", "Apple TV+")

# Series and anime work exactly the same way.
EPISODIC_STATUS_LABELS = {
    Status.PLANNED: "Watchlist",
    Status.IN_PROGRESS: "Watching",
    Status.FINISHED: "Watched",
    Status.DROPPED: "Dropped",
}

KIND_CONFIG: dict[Kind, KindConfig] = {
    Kind.MOVIE: KindConfig(
        label="Movie",
        plural="Movies",
        genres=SCREEN_GENRES,
        status_labels={Status.PLANNED: "Watchlist", Status.FINISHED: "Watched"},
        platforms=("Cinema", *STREAMING, "Blu-ray", "TV"),
    ),
    Kind.SERIES: KindConfig(
        label="Series",
        plural="Series",
        genres=SCREEN_GENRES,
        status_labels=EPISODIC_STATUS_LABELS,
        platforms=(*STREAMING, "TV"),
        has_episodes=True,
    ),
    Kind.ANIME: KindConfig(
        label="Anime",
        plural="Anime",
        genres=SCREEN_GENRES,
        status_labels=EPISODIC_STATUS_LABELS,
        platforms=("Crunchyroll", *STREAMING, "TV"),
        has_episodes=True,
    ),
    Kind.GAME: KindConfig(
        label="Game",
        plural="Games",
        genres=GAME_GENRES,
        status_labels={
            Status.PLANNED: "Backlog",
            Status.IN_PROGRESS: "Playing",
            Status.FINISHED: "Completed",
            Status.DROPPED: "Dropped",
        },
        platform_label="Platform",
        platforms=("PC", "PlayStation 5", "PlayStation 4", "Xbox Series X|S", "Nintendo Switch", "Nintendo Switch 2",
                   "Steam Deck", "Mobile"),
    ),
    Kind.BOOK: KindConfig(
        label="Book",
        plural="Books",
        genres=BOOK_GENRES,
        status_labels={
            Status.PLANNED: "To read",
            Status.IN_PROGRESS: "Reading",
            Status.FINISHED: "Read",
            Status.DROPPED: "Dropped",
        },
        year_label="Year published",
        platform_label="Format",
        platforms=("Paperback", "Hardcover", "E-book", "Kindle", "Audiobook", "Library copy"),
        has_pages=True,
    ),
}


EPISODIC_KINDS: tuple[Kind, ...] = tuple(kind for kind, config in KIND_CONFIG.items() if config.has_episodes)
PAGED_KINDS: tuple[Kind, ...] = tuple(kind for kind, config in KIND_CONFIG.items() if config.has_pages)


# Kind-neutral names, used when all kinds are shown together (the "All" tab and the fridge magnets).
GENERIC_STATUS_LABELS: dict[Status, str] = {
    Status.PLANNED: "Planned",
    Status.IN_PROGRESS: "In progress",
    Status.FINISHED: "Finished",
    Status.DROPPED: "Dropped",
}


def form_config() -> dict[str, dict]:
    """What the form's JavaScript needs to adapt the fields when the kind changes."""
    return {
        kind.value: {
            "genres": list(config.genres),
            "statuses": {status.value: label for status, label in config.status_labels.items()},
            "year_label": config.year_label,
            "platform_label": config.platform_label,
            "platforms": list(config.platforms),
        }
        for kind, config in KIND_CONFIG.items()
    }
