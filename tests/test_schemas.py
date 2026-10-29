"""Form validation rules (TitleIn): what each kind accepts and how fields depend on each other."""

import pytest
from pydantic import ValidationError

from app.catalog import Completion, Kind, Status
from app.schemas import FIRST_FILM_YEAR, MAX_YEAR, TitleIn, form_errors


def validate(**fields) -> TitleIn:
    return TitleIn.model_validate({"title": "Arrival", "year": 2016, "genre": "Sci-Fi", **fields})


def errors_of(**fields) -> dict[str, str]:
    with pytest.raises(ValidationError) as exc:
        validate(**fields)
    return form_errors(exc.value)


def test_minimal_movie_gets_defaults():
    data = validate()
    assert data.kind == Kind.MOVIE
    assert data.status == Status.PLANNED
    assert data.rating is None


def test_title_is_stripped_and_required():
    assert validate(title="  Dune  ").title == "Dune"
    assert errors_of(title="   ")["title"] == "This field is required."


@pytest.mark.parametrize("year", [FIRST_FILM_YEAR - 1, MAX_YEAR + 1])
def test_year_out_of_range(year):
    assert "year" in errors_of(year=year)


def test_year_must_be_a_number():
    assert errors_of(year="soon")["year"] == "Please enter a whole number."


@pytest.mark.parametrize(
    ("kind", "genre", "ok"),
    [("movie", "Sci-Fi", True), ("movie", "RPG", False), ("game", "RPG", True), ("game", "Drama", False),
     ("book", "Poetry", True), ("book", "Western", False)],
)
def test_genre_must_fit_kind(kind, genre, ok):
    if ok:
        assert validate(kind=kind, genre=genre).genre == genre
    else:
        assert errors_of(kind=kind, genre=genre)["genre"] == "Please choose a genre from the list."


@pytest.mark.parametrize("status", ["watching", "dropped"])
def test_movies_are_only_planned_or_watched(status):
    assert "status" in errors_of(status=status, rating="7")


def test_finished_needs_a_rating():
    assert errors_of(status="watched")["rating"] == "Give it a rating since you've finished it."


def test_planned_titles_lose_their_rating():
    assert validate(status="watchlist", rating="9").rating is None


@pytest.mark.parametrize("rating", ["0", "11"])
def test_rating_range(rating):
    assert "rating" in errors_of(status="watched", rating=rating)


def test_fields_of_other_kinds_are_cleared():
    data = validate(seasons=["10"], progress_season="1", author="Someone", pages="300", hours_played="12")
    assert (data.seasons, data.progress_season, data.author, data.pages, data.hours_played) == ([], None, "", None, None)


# --- Series and anime ---


def series(**fields) -> dict:
    return {"kind": "series", "genre": "Drama", **fields}


def test_series_needs_seasons():
    assert "seasons" in errors_of(**series(seasons=[]))


def test_blank_season_is_named():
    assert errors_of(**series(seasons=["8", ""]))["seasons"] == "Enter the number of episodes for season 2."


def test_progress_must_exist_in_the_seasons():
    assert errors_of(**series(seasons=["8"], status="watching", progress_season="2", progress_episode="1"))[
        "progress_season"
    ] == "It only has 1 season."
    assert errors_of(**series(seasons=["8"], status="watching", progress_season="1", progress_episode="9"))[
        "progress_episode"
    ] == "Season 1 has 8 episodes."


def test_finished_series_is_watched_to_the_end():
    data = validate(**series(seasons=["8", "10"], status="watched", rating="9"))
    assert (data.progress_season, data.progress_episode) == (2, 10)


def test_planned_series_has_no_progress():
    data = validate(**series(seasons=["8"], status="watchlist", progress_season="1", progress_episode="3"))
    assert data.progress_season is None and data.progress_episode is None


def test_anime_works_like_series():
    data = validate(kind="anime", genre="Fantasy", seasons=["12"], status="watching", progress_season="1",
                    progress_episode="5")
    assert data.seasons == [12] and data.progress_episode == 5


# --- Games ---


def test_completed_game_needs_completion():
    assert "completion" in errors_of(kind="game", genre="RPG", status="watched", rating="9")
    data = validate(kind="game", genre="RPG", status="watched", rating="9", completion="full", hours_played="80")
    assert data.completion == Completion.FULL and data.hours_played == 80


def test_unfinished_game_has_no_completion():
    assert validate(kind="game", genre="RPG", status="watching", completion="full").completion is None


# --- Books ---


def book(**fields) -> dict:
    return {"kind": "book", "genre": "Fiction", "author": "Ursula K. Le Guin", "pages": "300", **fields}


def test_current_page_cannot_pass_the_last_page():
    assert errors_of(**book(status="watching", current_page="301"))["current_page"] == "The book only has 300 pages."


def test_finished_book_is_on_the_last_page():
    assert validate(**book(status="watched", rating="8")).current_page == 300


def test_planned_book_has_no_current_page():
    assert validate(**book(status="watchlist", current_page="50")).current_page is None
