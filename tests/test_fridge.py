"""The fridge: magnets that count and filter by status, and the shelves behind the door."""

import re
from datetime import datetime, timedelta


def shelves(html: str) -> list[str]:
    inside = html.split('id="fridge-inside"', 1)[1].split('class="fridge-door"', 1)[0]
    return re.findall(r'class="fridge-item-title">(.*?)<', inside)


def test_magnets_count_by_status(client, make_title):
    make_title(title="Arrival", status="watched", rating=9)
    make_title(title="Her")
    make_title(title="Severance", kind="series", genre="Drama", seasons=["9"], status="watching")
    page = client.get("/").text
    assert "<strong>3</strong> chilling" in page
    for count, label in [(1, "finished"), (1, "in progress"), (1, "planned")]:
        assert re.search(rf"<strong>{count}</strong> {label}", page)
    # The dropped magnet only appears once something has been dropped.
    assert "dropped</a>" not in page.replace("\n", "").replace(" ", "")


def test_active_magnet_links_back_to_everything(client, make_title):
    make_title(status="watched", rating=8)
    page = client.get("/?status=watched").text
    assert re.search(r'class="magnet seg-finished is-active"\s+href="/"', page)


def test_shelves_show_open_titles_last_touched_first(client, db, make_title):
    older = make_title(title="Severance", kind="series", genre="Drama", seasons=["9"], status="watching")
    newer = make_title(title="Dune", kind="book", genre="Sci-Fi", pages=600, status="watching", current_page=300)
    make_title(title="Her")  # planned, so not on the shelves
    older.updated_at, newer.updated_at = datetime(2026, 1, 1), datetime(2026, 1, 2)
    db.commit()
    assert shelves(client.get("/").text) == ["Dune", "Severance"]

    client.post(f"/titles/{older.id}/next")  # watching an episode moves it to the top
    page = client.get("/").text
    assert shelves(page) == ["Severance", "Dune"]
    assert "Next: S1 · E2" in page and "50% read" in page


def test_at_most_five_shelves_then_a_link(client, db, make_title):
    start = datetime(2026, 1, 1)
    for n in range(7):
        item = make_title(title=f"Book {n}", kind="book", genre="Fiction", status="watching")
        item.updated_at = start + timedelta(days=n)
    db.commit()
    page = client.get("/").text
    assert shelves(page) == ["Book 6", "Book 5", "Book 4", "Book 3", "Book 2"]
    assert "All 7 in progress →" in page


def test_empty_fridge_inside(client, make_title):
    make_title()
    page = client.get("/").text
    assert "Nothing open." in page
    assert "Peek inside" in page


def test_inside_starts_closed(client):
    assert 'id="fridge-inside" inert' in client.get("/").text
