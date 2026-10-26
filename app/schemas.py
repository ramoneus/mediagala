"""Pydantic schemas used to validate form input before it reaches the database."""

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, field_validator

from app.catalog import ALL_GENRES, Completion, Kind, Status

FIRST_FILM_YEAR = 1888  # Roundhay Garden Scene
MAX_YEAR = date.today().year + 5
MAX_SEASONS = 50
MAX_EPISODES_PER_SEASON = 500
MAX_HOURS_PLAYED = 100_000
MAX_PAGES = 100_000


class TitleIn(BaseModel):
    """Validated data for creating or updating a movie, series or game.

    Field order matters: validators read fields declared before them
    (`genre` reads `kind`, `rating` reads `status`, the progress fields read `seasons`…).
    Fields that don't apply to the chosen kind are cleared rather than rejected,
    because the form still submits its hidden inputs.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    kind: Kind = Kind.MOVIE
    title: str = Field(min_length=1, max_length=200)
    year: int = Field(ge=FIRST_FILM_YEAR, le=MAX_YEAR)
    genre: str
    description: str = Field(default="", max_length=2000)
    status: Status = Status.PLANNED
    rating: int | None = Field(default=None, ge=1, le=10)
    # Series: episodes per season, e.g. [10, 10, 8] (one form input per season).
    seasons: list[int] = Field(default_factory=list)
    # Series: the last episode watched; None means "not started yet".
    progress_season: int | None = None
    progress_episode: int | None = None
    # Games.
    completion: Completion | None = None
    hours_played: int | None = Field(default=None, ge=0, le=MAX_HOURS_PLAYED)
    # Books.
    author: str = Field(default="", max_length=200)
    pages: int | None = Field(default=None, ge=1, le=MAX_PAGES)
    current_page: int | None = Field(default=None, ge=0, le=MAX_PAGES)

    @field_validator("genre")
    @classmethod
    def genre_must_fit_kind(cls, value: str, info: ValidationInfo) -> str:
        kind = info.data.get("kind")
        if value not in (kind.config.genres if kind else ALL_GENRES):
            raise ValueError("Please choose a genre from the list.")
        return value

    @field_validator("status")
    @classmethod
    def status_must_fit_kind(cls, value: Status, info: ValidationInfo) -> Status:
        kind = info.data.get("kind")
        if kind and value not in kind.config.statuses:
            raise ValueError(f"That status isn't available for {kind.config.plural.lower()}.")
        return value

    @field_validator(
        "rating", "progress_season", "progress_episode", "completion", "hours_played", "pages", "current_page",
        mode="before",
    )
    @classmethod
    def blank_is_none(cls, value: Any) -> Any:
        return None if value in ("", None) else value

    @field_validator("rating")
    @classmethod
    def rating_matches_status(cls, value: int | None, info: ValidationInfo) -> int | None:
        status = info.data.get("status")
        if status == Status.PLANNED:
            return None  # You can't rate what you haven't seen or played yet.
        if status == Status.FINISHED and value is None:
            raise ValueError("Give it a rating since you've finished it.")
        return value  # optional while in progress or dropped

    @field_validator("seasons", mode="before")
    @classmethod
    def parse_seasons(cls, value: Any, info: ValidationInfo) -> Any:
        """Turn the per-season form inputs into numbers, naming the season that's wrong."""
        if not cls._has_episodes(info):
            return []
        if not isinstance(value, list):
            return value
        counts = []
        for number, raw in enumerate(value, start=1):
            text = str(raw).strip()
            if not text.isdigit():
                raise ValueError(f"Enter the number of episodes for season {number}.")
            counts.append(int(text))
        return counts

    @field_validator("seasons")
    @classmethod
    def seasons_match_kind(cls, value: list[int], info: ValidationInfo) -> list[int]:
        if not cls._has_episodes(info):
            return []
        if not value:
            raise ValueError("Enter how many episodes each season has.")
        if len(value) > MAX_SEASONS:
            raise ValueError(f"There can be at most {MAX_SEASONS} seasons.")
        if any(not 1 <= count <= MAX_EPISODES_PER_SEASON for count in value):
            raise ValueError(f"Each season needs between 1 and {MAX_EPISODES_PER_SEASON} episodes.")
        return value

    @staticmethod
    def _has_episodes(info: ValidationInfo) -> bool:
        """Series and anime: kinds with seasons and episode tracking."""
        kind = info.data.get("kind")
        return kind is not None and kind.has_episodes

    @classmethod
    def _tracks_progress(cls, info: ValidationInfo) -> bool:
        """Episode progress applies to series and anime that have been started."""
        return (
            cls._has_episodes(info)
            and info.data.get("status") not in (None, Status.PLANNED)
            and bool(info.data.get("seasons"))
        )

    @field_validator("progress_season")
    @classmethod
    def check_progress_season(cls, value: int | None, info: ValidationInfo) -> int | None:
        if not cls._tracks_progress(info):
            return None
        seasons = info.data["seasons"]
        if info.data["status"] == Status.FINISHED:
            return len(seasons)  # a finished series has every episode watched
        if value is not None and not 1 <= value <= len(seasons):
            raise ValueError(f"It only has {len(seasons)} season{'s' if len(seasons) != 1 else ''}.")
        return value

    @field_validator("progress_episode")
    @classmethod
    def check_progress_episode(cls, value: int | None, info: ValidationInfo) -> int | None:
        if not cls._tracks_progress(info):
            return None
        seasons = info.data["seasons"]
        if info.data["status"] == Status.FINISHED:
            return seasons[-1]
        season = info.data.get("progress_season")
        if season is None:
            # A season that failed validation is missing from info.data and already has its own error.
            if value is not None and "progress_season" in info.data:
                raise ValueError("Enter the season too.")
            return None
        if value is None:
            raise ValueError("Enter the episode you stopped at.")
        if not 1 <= value <= seasons[season - 1]:
            raise ValueError(f"Season {season} has {seasons[season - 1]} episodes.")
        return value

    @field_validator("completion")
    @classmethod
    def completion_for_finished_games(cls, value: Completion | None, info: ValidationInfo) -> Completion | None:
        if info.data.get("kind") != Kind.GAME or info.data.get("status") != Status.FINISHED:
            return None
        if value is None:
            raise ValueError("Choose how far you got: story, story + DLC or 100%.")
        return value

    @field_validator("hours_played")
    @classmethod
    def hours_for_games(cls, value: int | None, info: ValidationInfo) -> int | None:
        return value if info.data.get("kind") == Kind.GAME else None

    @staticmethod
    def _has_pages(info: ValidationInfo) -> bool:
        kind = info.data.get("kind")
        return kind is not None and kind.has_pages

    @field_validator("author")
    @classmethod
    def author_for_books(cls, value: str, info: ValidationInfo) -> str:
        return value if cls._has_pages(info) else ""

    @field_validator("pages")
    @classmethod
    def pages_for_books(cls, value: int | None, info: ValidationInfo) -> int | None:
        return value if cls._has_pages(info) else None

    @field_validator("current_page")
    @classmethod
    def check_current_page(cls, value: int | None, info: ValidationInfo) -> int | None:
        if not cls._has_pages(info):
            return None
        status, pages = info.data.get("status"), info.data.get("pages")
        if status == Status.FINISHED:
            return pages  # a finished book has been read to the last page
        if status not in (Status.IN_PROGRESS, Status.DROPPED):
            return None
        if value is not None and pages is not None and value > pages:
            raise ValueError(f"The book only has {pages} pages.")
        return value


FRIENDLY_MESSAGES = {
    "missing": "This field is required.",
    "string_too_short": "This field is required.",
    "int_parsing": "Please enter a whole number.",
    "enum": "Please choose a valid option.",
}


def form_errors(exc: ValidationError) -> dict[str, str]:
    """Flatten a ValidationError into {field_name: first human-readable message}."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        field = str(err["loc"][0]) if err["loc"] else "__all__"
        message = FRIENDLY_MESSAGES.get(err["type"], err["msg"].removeprefix("Value error, "))
        errors.setdefault(field, message)
    return errors
