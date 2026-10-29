"""The collection page and adding, editing and deleting titles through the web forms."""

import re

import pytest
from conftest import form

from app.models import Title


def card_titles(html: str) -> list[str]:
    return re.findall(r'class="card-link">(.*?)<', html)


def test_empty_collection(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Nothing here yet" in response.text


def test_add_title(client, db):
    response = client.post("/titles", data=form(title="Arrival"))
    assert response.status_code == 303
    assert response.headers["location"] == "/?msg=created"
    assert db.query(Title).one().title == "Arrival"

    page = client.get("/?msg=created").text
    assert "Added to your collection." in page
    assert card_titles(page) == ["Arrival"]


def test_invalid_form_keeps_the_input_and_shows_errors(client, db):
    response = client.post("/titles", data=form(title="Half typed", year="20x6"))
    assert response.status_code == 422
    assert "Please enter a whole number." in response.text
    assert 'value="Half typed"' in response.text
    assert db.query(Title).count() == 0


def test_edit_title(client, db, make_title):
    item = make_title()
    response = client.post(f"/titles/{item.id}/edit", data=form(title="Arrival (2016)", status="watched", rating="9"))
    assert response.headers["location"] == "/?msg=updated"
    db.refresh(item)
    assert (item.title, item.rating) == ("Arrival (2016)", 9)


def test_delete_title(client, make_title):
    item = make_title()
    assert client.post(f"/titles/{item.id}/delete").headers["location"] == "/?msg=deleted"
    assert client.get(f"/titles/{item.id}").status_code == 404


def test_edit_series_seasons_grow_and_shrink(client, db, make_title):
    item = make_title(kind="series", genre="Drama", seasons=["8", "8", "8"])
    series_form = form(kind="series", genre="Drama")
    client.post(f"/titles/{item.id}/edit", data={**series_form, "season_episodes": ["10", "6"]})
    db.refresh(item)
    assert [s.episode_count for s in item.seasons] == [10, 6]

    client.post(f"/titles/{item.id}/edit", data={**series_form, "season_episodes": ["10", "6", "4", "2"]})
    db.refresh(item)
    assert [(s.number, s.episode_count) for s in item.seasons] == [(1, 10), (2, 6), (3, 4), (4, 2)]


def test_cards_are_cover_title_and_one_line(client, make_title):
    item = make_title(title="Arrival", year=2016, genre="Sci-Fi")
    home = client.get("/").text
    assert "2016 · Movie" in home  # on "All", the kind tells same-named titles apart
    assert "2016 · Sci-Fi" in client.get("/?kind=movie").text  # within a kind, the genre
    # Edit and Delete live on the title's own page, not on every card.
    assert f"/titles/{item.id}/edit" not in home and f"/titles/{item.id}/delete" not in home
    assert f"/titles/{item.id}/edit" in client.get(f"/titles/{item.id}").text


def test_progress_bar_on_the_cover_only_while_in_progress(client, make_title):
    make_title(title="Severance", kind="series", genre="Drama", seasons=["9", "10"], status="watching",
               progress_season="1", progress_episode="9")
    make_title(title="Breaking Bad", kind="series", genre="Crime", seasons=["7"], status="watched", rating="10")
    page = client.get("/").text
    assert page.count('class="poster-progress"') == 1
    assert 'aria-valuenow="47"' in page  # 9 of 19 episodes
    assert "✓ S2 · E1" in page  # the quick "next episode" button


def test_filters_apply_without_a_button_when_javascript_runs(client):
    page = client.get("/").text
    assert "js/filters.js" in page and 'class="btn toolbar-apply"' in page


def test_user_text_is_escaped(client, make_title):
    make_title(title="<script>alert(1)</script>")
    page = client.get("/").text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_flash_messages_come_only_from_known_keys(client):
    page = client.get("/?msg=<b>hacked</b>").text
    assert "hacked" not in page


@pytest.mark.parametrize(
    ("url", "status_code", "message"),
    [
        ("/titles/999", 404, "We couldn&#39;t find that title."),
        ("/no-such-page", 404, "This page doesn&#39;t exist."),
        ("/titles/abc", 400, "That request doesn&#39;t look right."),
    ],
)
def test_error_pages(client, url, status_code, message):
    response = client.get(url)
    assert response.status_code == status_code
    assert message in response.text


# --- Search, filters and sorting ---


@pytest.fixture
def collection(make_title):
    make_title(title="Arrival", year=2016, status="watched", rating=9)
    make_title(title="Blade Runner", year=1982, status="watched", rating=8)
    make_title(title="Dune", kind="book", genre="Sci-Fi", year=1965, author="Frank Herbert")
    make_title(title="Hades", kind="game", genre="Action", year=2020)


def test_search_is_case_insensitive_and_covers_authors(client, collection):
    assert card_titles(client.get("/?q=BLADE").text) == ["Blade Runner"]
    assert card_titles(client.get("/?q=herbert").text) == ["Dune"]


def test_search_wildcards_are_literal(client, make_title):
    make_title(title="100% Orange Juice")
    make_title(title="1000 Ways")
    assert card_titles(client.get("/?q=100%25").text) == ["100% Orange Juice"]
    assert card_titles(client.get("/?q=_").text) == []


def test_filters(client, collection):
    assert card_titles(client.get("/?kind=game").text) == ["Hades"]
    assert sorted(card_titles(client.get("/?status=watched").text)) == ["Arrival", "Blade Runner"]
    assert card_titles(client.get("/?kind=book&genre=Sci-Fi").text) == ["Dune"]


def test_unknown_filter_values_are_ignored(client, collection):
    assert len(card_titles(client.get("/?kind=vinyl&status=lost&sort=random").text)) == 4


def test_sorting(client, collection):
    assert card_titles(client.get("/?sort=title").text) == ["Arrival", "Blade Runner", "Dune", "Hades"]
    assert card_titles(client.get("/?sort=year_asc").text)[0] == "Dune"
    # Unrated titles go last whichever way ratings are sorted.
    assert card_titles(client.get("/?sort=rating_desc").text)[:2] == ["Arrival", "Blade Runner"]
    assert card_titles(client.get("/?sort=rating_asc").text)[:2] == ["Blade Runner", "Arrival"]


def test_kind_tabs_show_counts(client, collection):
    page = client.get("/").text
    assert re.search(r">\s*All <span>4</span>", page)
    assert re.search(r">\s*Books <span>1</span>", page)
