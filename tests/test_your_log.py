"""Your own record of a title: where you watched/played/read it, when, and your notes."""

from datetime import date, timedelta

import pytest
from conftest import form
from pydantic import ValidationError

from app.catalog import Status
from app.models import Title
from app.schemas import TitleIn

TODAY = date.today()


def log(**fields) -> TitleIn:
    return TitleIn.model_validate({"title": "Severance", "year": 2022, "genre": "Drama", "kind": "series",
                                   "seasons": ["9"], **fields})


def test_form_saves_where_when_and_notes(client, db):
    fields = form(status="watched", rating="9", platform="Cinema", finished_on="2024-03-02",
                  notes="Saw it twice.\nThe sound!")
    assert client.post("/titles", data=fields).status_code == 303
    item = db.query(Title).one()
    assert (item.platform, item.finished_on, item.notes) == ("Cinema", date(2024, 3, 2), "Saw it twice.\nThe sound!")

    page = client.get(f"/titles/{item.id}").text
    assert "<dt>Where</dt><dd>Cinema</dd>" in page
    assert "<dt>Watched</dt><dd>2 Mar 2024</dd>" in page
    assert "Saw it twice.\nThe sound!" in page  # line breaks kept (shown with white-space: pre-line)


def test_how_long_it_took(client, db):
    client.post("/titles", data=form(kind="book", genre="Fantasy", status="watched", rating="8",
                                     started_on="2024-03-01", finished_on="2024-03-03"))
    item = db.query(Title).one()
    assert item.days_spent == 3  # the 1st, 2nd and 3rd
    page = client.get(f"/titles/{item.id}").text
    assert "<dt>Took</dt><dd>3 days</dd>" in page and "<dt>Read</dt><dd>3 Mar 2024</dd>" in page


def test_one_day_is_a_day():
    assert log(status="watched", rating="9", started_on=TODAY, finished_on=TODAY).started_on == TODAY
    item = Title(started_on=TODAY, finished_on=TODAY)
    assert item.days_spent == 1


def test_dates_follow_the_status():
    planned = log(status="watchlist", started_on="2024-01-01", finished_on="2024-01-02")
    assert (planned.started_on, planned.finished_on) == (None, None)  # not started yet: no dates
    watching = log(status="watching", started_on="2024-01-01", finished_on="2024-01-02")
    assert (watching.started_on, watching.finished_on) == (date(2024, 1, 1), None)  # not finished yet
    dropped = log(status="dropped", started_on="2024-01-01", finished_on="2024-01-02")
    assert dropped.finished_on == date(2024, 1, 2)  # the day you gave up


def test_movies_have_only_the_day_you_watched_them():
    movie = TitleIn.model_validate({"title": "Heat", "year": 1995, "genre": "Crime", "status": "watched",
                                    "rating": "9", "started_on": "2024-01-01", "finished_on": "2024-01-02"})
    assert (movie.started_on, movie.finished_on) == (None, date(2024, 1, 2))


@pytest.mark.parametrize(
    ("fields", "field", "message"),
    [
        ({"status": "watched", "rating": "8", "started_on": "2024-05-02", "finished_on": "2024-05-01"},
         "finished_on", "before the day you started"),
        ({"status": "watching", "started_on": (TODAY + timedelta(days=1)).isoformat()}, "started_on", "in the future"),
        ({"status": "watched", "rating": "8", "finished_on": (TODAY + timedelta(days=1)).isoformat()},
         "finished_on", "in the future"),
        ({"status": "watching", "started_on": "yesterday"}, "started_on", "valid date"),
        ({"notes": "x" * 5001}, "notes", "at most 5000"),
        ({"platform": "x" * 51}, "platform", "at most 50"),
    ],
)
def test_bad_log_entries(client, fields, field, message):
    response = client.post("/titles", data=form(kind="series", genre="Drama", season_episodes=["9"], **fields))
    assert response.status_code == 422
    assert message in response.text
    assert f'id="{field}-error"' in response.text


def test_starting_something_planned_dates_it_today(client, db, make_title):
    series = make_title(title="Severance", kind="series", genre="Drama", seasons=["9"])
    client.post(f"/titles/{series.id}/next")
    book = make_title(title="Dune", kind="book", genre="Sci-Fi", pages="600")
    client.post(f"/titles/{book.id}/page", data={"current_page": "10"})
    for item in (series, book):
        db.refresh(item)
        assert (item.status, item.started_on) == (Status.IN_PROGRESS, TODAY)


def test_carrying_on_keeps_the_start_date(client, db, make_title):
    item = make_title(title="Severance", kind="series", genre="Drama", seasons=["9"], status="watching",
                      started_on="2024-01-05")
    client.post(f"/titles/{item.id}/next")
    db.refresh(item)
    assert item.started_on == date(2024, 1, 5)


def test_finishing_suggests_today(client, make_title):
    item = make_title(title="Severance", kind="series", genre="Drama", seasons=["1"], status="watching",
                      progress_season="1", progress_episode="1")
    page = client.get(f"/titles/{item.id}/edit?finished=1").text
    assert f'name="finished_on" value="{TODAY.isoformat()}"' in page
    assert "Watched on" in page


def test_form_labels_follow_the_kind(client, make_title):
    assert "Platform" in client.get("/titles/new?kind=game").text
    page = client.get("/titles/new?kind=book").text
    assert "Format" in page and '<option value="Audiobook">' in page
    game = make_title(title="Hades", kind="game", genre="RPG", status="dropped")
    assert "Dropped on" in client.get(f"/titles/{game.id}/edit").text


def test_only_editing_suggests_dates(client, make_title):
    # title-form.js fills in today when you move a title on; a new title may be from years ago.
    assert "data-editing" not in client.get("/titles/new").text
    assert "data-editing" in client.get(f"/titles/{make_title().id}/edit").text


def test_empty_log_and_notes_invite_you_to_fill_them_in(client, make_title):
    item = make_title()
    page = client.get(f"/titles/{item.id}").text
    assert "Add notes" in page and "Add where and when" in page
    assert "<dt>Added</dt>" in page
