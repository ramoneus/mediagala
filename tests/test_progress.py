"""Ticking off episodes and updating the page you're on."""

import pytest

from app.catalog import Status
from app.models import Season


@pytest.fixture
def show(make_title):
    """A series with two seasons (3 + 2 episodes), not started yet."""
    return make_title(title="Severance", kind="series", genre="Drama", seasons=["3", "2"])


def progress(db, item):
    db.refresh(item)
    return item.progress


def test_next_episode_button(client, db, show):
    response = client.post(f"/titles/{show.id}/next", data={"return_to": "/?kind=series"})
    assert response.status_code == 303
    assert response.headers["location"] == "/?kind=series"
    assert progress(db, show) == (1, 1)
    assert show.status == Status.IN_PROGRESS  # ticking an episode means you're watching it


@pytest.mark.parametrize("target", ["//evil.example", "https://evil.example", "/\\evil.example"])
def test_next_episode_never_redirects_off_site(client, show, target):
    assert client.post(f"/titles/{show.id}/next", data={"return_to": target}).headers["location"] == "/"


def test_clicking_an_episode_marks_everything_before_it(client, db, show):
    client.post(f"/titles/{show.id}/episodes", data={"position": "2-1"})
    assert progress(db, show) == (2, 1)
    assert show.watched_episodes == 4


def test_clicking_the_last_watched_episode_undoes_it(client, db, show):
    client.post(f"/titles/{show.id}/episodes", data={"position": "2-1"})
    client.post(f"/titles/{show.id}/episodes", data={"position": "2-1"})
    assert progress(db, show) == (1, 3)


def test_reset_progress(client, db, show):
    client.post(f"/titles/{show.id}/episodes", data={"position": "1-2"})
    client.post(f"/titles/{show.id}/episodes", data={"position": "reset"})
    assert progress(db, show) is None


@pytest.mark.parametrize("position", ["3-1", "1-4", "0-1", "nonsense"])
def test_episodes_that_dont_exist(client, show, position):
    assert client.post(f"/titles/{show.id}/episodes", data={"position": position}).status_code == 400


def test_final_episode_asks_for_a_rating(client, show):
    response = client.post(f"/titles/{show.id}/episodes", data={"position": "2-2"})
    assert response.headers["location"] == f"/titles/{show.id}/edit?finished=1"
    assert "You finished" in client.get(response.headers["location"]).text
    # Nothing left to watch.
    assert client.post(f"/titles/{show.id}/next").status_code == 400


def test_movies_have_no_episodes(client, make_title):
    movie = make_title()
    assert client.post(f"/titles/{movie.id}/next").status_code == 400
    assert client.post(f"/titles/{movie.id}/episodes", data={"position": "1-1"}).status_code == 400


def test_deleting_a_series_deletes_its_seasons(client, db, show):
    assert db.query(Season).count() == 2
    client.post(f"/titles/{show.id}/delete")
    assert db.query(Season).count() == 0


# --- Books ---


@pytest.fixture
def novel(make_title):
    return make_title(title="Dune", kind="book", genre="Sci-Fi", year=1965, pages="600")


def test_update_current_page(client, db, novel):
    response = client.post(f"/titles/{novel.id}/page", data={"current_page": "120"})
    assert response.headers["location"] == f"/titles/{novel.id}"
    db.refresh(novel)
    assert novel.current_page == 120 and novel.status == Status.IN_PROGRESS


def test_last_page_asks_for_a_rating(client, db, novel):
    response = client.post(f"/titles/{novel.id}/page", data={"current_page": "700"})
    assert response.headers["location"] == f"/titles/{novel.id}/edit?finished=1"
    db.refresh(novel)
    assert novel.current_page == 600


def test_only_books_have_pages(client, make_title):
    movie = make_title()
    assert client.post(f"/titles/{movie.id}/page", data={"current_page": "10"}).status_code == 400
