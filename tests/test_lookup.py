"""'Find it online'. The services' answers are faked (shaped like the real ones),
so the tests run offline and stay fast."""

import os

import httpx
import pytest
from conftest import PNG, form

from app import crud, lookup
from app.catalog import Kind, Status
from app.lookup import anilist, base, openlibrary, tmdb, tvmaze, wikipedia
from app.models import Title
from app.posters import POSTER_DIR
from app.settings import load_env_file

SEVERANCE = {
    "id": 44933,
    "name": "Severance",
    "premiered": "2022-02-18",
    "genres": ["Science-Fiction", "Drama"],
    "summary": "<p>Mark leads a team at <b>Lumon</b> &amp; finds a mystery.</p>",
    "image": {"medium": "https://static.tvmaze.com/m.jpg", "original": "https://static.tvmaze.com/o.jpg"},
}
FRIEREN = {
    "id": 154587,
    "title": {"romaji": "Sousou no Frieren", "english": "Frieren: Beyond Journey's End"},
    "startDate": {"year": 2023},
    "genres": ["Adventure", "Drama", "Fantasy"],
    "episodes": 28,
    "description": "The adventure is over.<br><br>(Source: Crunchyroll)",
    "coverImage": {"medium": "https://s4.anilist.co/m.jpg", "extraLarge": "https://s4.anilist.co/xl.jpg"},
}
NAME_OF_THE_WIND = {
    "key": "/works/OL8479867W",
    "title": "The Name of the Wind",
    "author_name": ["Patrick Rothfuss", "Marc Simonetti"],
    "first_publish_year": 2007,
    "number_of_pages_median": 736,
    "cover_i": 11480483,
    "subject": ["orphans", "Fiction", "fantasy fiction", "Magicians"],
}
ARRIVAL_TMDB = {
    "id": 329865,
    "title": "Arrival",
    "release_date": "2016-11-10",
    "overview": "Taking place after alien crafts land around the world.",
    "poster_path": "/x2FJsf1ElAgr63Y3PNPtJrcmpoe.jpg",
    "genre_ids": [18, 878, 9648],  # Drama, Science Fiction, Mystery
}
# What only the details requests return: credits, videos, studios and the like.
ARRIVAL_TMDB_EXTRAS = {
    "runtime": 116,
    "vote_average": 7.638,
    "vote_count": 19000,
    "credits": {
        "cast": [{"name": "Amy Adams"}, {"name": "Jeremy Renner"}, {"name": "Forest Whitaker"},
                 {"name": "Michael Stuhlbarg"}, {"name": "Mark O'Brien"}],
        "crew": [{"name": "Denis Villeneuve", "job": "Director"}, {"name": "Eric Heisserer", "job": "Screenplay"},
                 {"name": "Ted Chiang", "job": "Short Story"}],
    },
    "videos": {"results": [
        {"site": "YouTube", "type": "Clip", "official": True, "key": "clip123456"},
        {"site": "YouTube", "type": "Trailer", "official": False, "key": "fanmade123"},
        {"site": "YouTube", "type": "Trailer", "official": True, "key": "tFMo3UJ4B4g"},
    ]},
}
SEVERANCE_EXTRAS = {"network": None, "webChannel": {"name": "Apple TV+"}, "status": "Running", "averageRuntime": 49,
                    "rating": {"average": 8.4}}
SEVERANCE_PEOPLE = {
    "cast": [{"person": {"name": "Adam Scott"}}, {"person": {"name": "Britt Lower"}}, {"person": None}],
    "crew": [{"type": "Creator", "person": {"name": "Dan Erickson"}}, {"type": "Casting", "person": {"name": "X"}}],
}
FRIEREN_EXTRAS = {"format": "TV", "status": "FINISHED", "duration": 24, "averageScore": 89, "source": "MANGA",
                  "studios": {"nodes": [{"name": "Madhouse"}]}, "trailer": {"id": "qgQHnKEf4VE\t", "site": "youtube"}}
NAME_OF_THE_WIND_EXTRAS = {"person": ["Kvothe", "Denna", "Bast"], "place": ["Imre", "Tarbean"], "edition_count": 112,
                           "ratings_average": 4.41, "ratings_count": 350}
WIKIPEDIA_PAGES = {
    "arrival": [
        {"key": "Arrival", "title": "Arrival", "description": "Topics referred to by the same term"},
        {"key": "Arrival_(film)", "title": "Arrival (film)", "description": "2016 American science fiction drama film",
         "thumbnail": {"url": "//upload.wikimedia.org/t.jpg"}},
        {"key": "Arrival_(soundtrack)", "title": "Arrival (soundtrack)", "description": "2016 film soundtrack album"},
        {"key": "The_Arrival_(1996_film)", "title": "The Arrival (1996 film)", "description": "1996 film by David Twohy"},
    ],
    "hades": [
        {"key": "Hades", "title": "Hades", "description": "God of the underworld in Greek mythology"},
        {"key": "Hades_(video_game)", "title": "Hades (video game)", "description": "2020 video game"},
        {"key": "Hades_II", "title": "Hades II", "description": "2025 video game"},
        {"key": "Music_of_Hades", "title": "Music of Hades", "description": "Music from the video game Hades"},
        {"key": "Hades:_The_Board_Game", "title": "Hades: The Board Game",
         "description": "Board game based on the video game Hades"},
        {"key": "Hades_(series)", "title": "Hades (series)", "description": "Video game series"},
    ],
    "god of war": [
        {"key": "God_of_War_(2018_video_game)", "title": "God of War (2018 video game)",
         "description": "Action-adventure video game"},
        {"key": "God_of_War_(2005_video_game)", "title": "God of War (2005 video game)",
         "description": "Action-adventure video game"},
    ],
    "hearthstone": [
        {"key": "Hearthstone", "title": "Hearthstone", "description": "2014 digital collectible card game"},
        {"key": "Hearthstone_(board_game)", "title": "Hearthstone (board game)", "description": "2016 board game"},
    ],
}
WIKIPEDIA_SUMMARIES = {
    "Arrival_%28film%29": {
        "type": "standard",
        "title": "Arrival (film)",
        "description": "2016 American science fiction drama film",
        "extract": "Arrival is a 2016 American science fiction drama film directed by Denis Villeneuve.",
        "originalimage": {"source": "https://upload.wikimedia.org/wikipedia/en/d/df/Arrival.jpg"},
    },
    "Minecraft": {  # its description names no genre
        "type": "standard",
        "title": "Minecraft",
        "description": "Sandbox video game",
        "extract": "Minecraft is a sandbox game developed by Mojang Studios. It was released in 2011.",
    },
    "Hades_%28video_game%29": {
        "type": "standard",
        "title": "Hades (video game)",
        "description": "2020 video game",
        "extract": "Hades is a 2020 roguelike action role-playing game developed by Supergiant Games. It sold well.",
        "originalimage": {"source": "https://upload.wikimedia.org/wikipedia/en/c/cc/Hades.jpg"},
    },
}

tmdb_calls: list[tuple[dict, dict]] = []  # (params, headers) of each TMDB request


def fake_get(url, params=None, headers=None):
    params = params or {}
    if url.startswith(tmdb.API):
        tmdb_calls.append((params, headers or {}))
        if url == f"{tmdb.API}/search/movie":
            return {"results": [ARRIVAL_TMDB]}
        if url == f"{tmdb.API}/movie/329865":
            genres = [{"id": 18, "name": "Drama"}, {"id": 878, "name": "Science Fiction"}, {"id": 9648, "name": "Mystery"}]
            return {**ARRIVAL_TMDB, "genres": genres, **ARRIVAL_TMDB_EXTRAS}
        return None
    if url == f"{tvmaze.API}/search/shows":
        return [{"score": 0.9, "show": SEVERANCE}]
    if url == f"{tvmaze.API}/shows/44933":
        seasons = [
            {"number": 1, "episodeOrder": 9},
            {"number": 2, "episodeOrder": None},  # no total given: count the episodes
            {"number": 3, "episodeOrder": None},  # announced, nothing yet: skipped
        ]
        embedded = {"seasons": seasons, "episodes": [{"season": 2}] * 10, **SEVERANCE_PEOPLE}
        return {**SEVERANCE, **SEVERANCE_EXTRAS, "_embedded": embedded}
    if url == wikipedia.SEARCH_API:
        return {"pages": WIKIPEDIA_PAGES.get(params["q"], [])}
    if url.startswith(wikipedia.SUMMARY_API):
        return WIKIPEDIA_SUMMARIES.get(url.rsplit("/", 1)[1])
    if url == f"{openlibrary.API}/search.json":
        if params["q"] == "key:/works/OL8479867W":
            return {"docs": [{**NAME_OF_THE_WIND, **NAME_OF_THE_WIND_EXTRAS}]}
        return {"docs": [NAME_OF_THE_WIND] if params["q"] == "the name of the wind" else []}
    if url == f"{openlibrary.API}/works/OL8479867W.json":
        return {"description": {"value": "***The Name of the Wind*** is a fantasy novel.\r\n----------\nSee also: …"},
                "subjects": ["Fantasy fiction"]}
    return None  # anything else: the service's 404


def fake_post(url, payload):
    assert url == anilist.API
    variables = payload["variables"]
    if "q" in variables:
        return {"data": {"Page": {"media": [FRIEREN]}}}
    return {"data": {"Media": {**FRIEREN, **FRIEREN_EXTRAS} if variables["id"] == 154587 else None}}


def offline(*args, **kwargs):
    raise lookup.LookupFailed(base.UNAVAILABLE)


@pytest.fixture(autouse=True)
def fake_services(monkeypatch):
    lookup.clear_cache()
    tmdb_calls.clear()
    monkeypatch.setattr(base, "get_json", fake_get)
    monkeypatch.setattr(base, "post_json", fake_post)
    monkeypatch.setattr(lookup, "_download", lambda url, limit: PNG)
    yield
    lookup.clear_cache()


@pytest.fixture
def tmdb_key(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef")


# --- Each source, translated into the app's fields ---


def test_tvmaze_series():
    (match,) = tvmaze.search("severance")
    assert (match.title, match.year, match.genre) == ("Severance", 2022, "Sci-Fi")  # "Science-Fiction" renamed
    assert match.description == "Mark leads a team at Lumon & finds a mystery."
    assert tvmaze.details("44933").seasons == (9, 10)
    assert tvmaze.details("123") is None
    assert tvmaze.details("../etc") is None


def test_anilist_anime():
    (match,) = anilist.search("frieren")
    assert (match.title, match.year, match.genre) == ("Frieren: Beyond Journey's End", 2023, "Adventure")
    assert match.description == "The adventure is over. (Source: Crunchyroll)"
    assert anilist.details("154587").seasons == (28,)  # one AniList entry is one season
    assert anilist.details("999") is None


def test_wikipedia_movies_keep_only_films():
    matches = wikipedia.search_movies("arrival")
    assert [(m.title, m.year) for m in matches] == [("Arrival", 2016), ("The Arrival", 1996)]
    assert matches[0].genre == "Sci-Fi"  # "science fiction" comes before "drama" in the description
    assert matches[0].thumb_url == "https://upload.wikimedia.org/t.jpg"
    movie = wikipedia.movie_details("Arrival_(film)")
    assert movie.description.startswith("Arrival is a 2016 American")
    assert movie.image_url.startswith("https://upload.wikimedia.org/")
    assert wikipedia.movie_details("Nothing_here") is None
    assert wikipedia.movie_details("a/b") is None


def test_wikipedia_games_keep_only_video_games():
    assert [m.title for m in wikipedia.search_games("hades")] == ["Hades", "Hades II"]
    # Two games with the same name: the year in the page title tells them apart.
    assert [(m.title, m.year) for m in wikipedia.search_games("god of war")] == [("God of War", 2018),
                                                                                ("God of War", 2005)]
    # A card game counts when it's a video game too.
    assert [m.title for m in wikipedia.search_games("hearthstone")] == ["Hearthstone"]


def test_wikipedia_game_details_read_the_first_sentence():
    game = wikipedia.game_details("Hades_(video_game)")
    assert (game.title, game.year) == ("Hades", 2020)
    assert game.genre == "RPG"  # from "roguelike action role-playing game", not just "2020 video game"


def test_open_library_books():
    (match,) = openlibrary.search("the name of the wind")
    assert (match.author, match.pages, match.genre) == ("Patrick Rothfuss", 736, "Fantasy")
    assert match.image_url == "https://covers.openlibrary.org/b/id/11480483-L.jpg"
    book = openlibrary.details("OL8479867W")
    assert book.description == "The Name of the Wind is a fantasy novel."
    assert openlibrary.details("OL1W") is None
    assert openlibrary.details("../../etc") is None


@pytest.mark.parametrize(
    ("subjects", "genre"),
    [
        # The Hobbit: one graphic-novel edition doesn't make it a comic.
        (["Fantasy", "Graphic novels", "Comics & graphic novels, fantasy", "Fantasy fiction", "hobbits",
          "Fiction, fantasy, general"], "Fantasy"),
        (["Graphic novels", "Comic books, strips", "Superheroes", "Fiction"], "Comics & Manga"),
        (["Fiction", "Classic Literature", "Fiction"], "Fiction"),  # broad genres only when nothing else fits
        (["Fiction", "Classic Literature", "Classics"], "Classics"),
        (["Love stories", "Mystery fiction"], "Mystery"),  # a tie goes to the more specific genre in the list
        (["orphans", "Cats"], ""),
    ],
)
def test_book_genre_is_what_most_subjects_say(subjects, genre):
    assert openlibrary._genre(subjects) == genre


@pytest.mark.parametrize(
    ("text", "genre"),
    [("2021 American epic space opera film", "Sci-Fi"), ("1994 crime drama film", "Crime"),
     ("2019 Korean dark comedy thriller film", "Comedy"), ("1987 film", "")],
)
def test_movie_genre_from_the_description(text, genre):
    assert base.genre_from_words(text, wikipedia.MOVIE_GENRES) == genre


@pytest.mark.parametrize(
    ("text", "genre"),
    [("2017 Metroidvania action-adventure game", "Platformer"), ("2022 action role-playing game", "RPG"),
     ("2019 survival horror game", "Horror"), ("2016 first-person shooter game", "Shooter"),
     ("2017 action-adventure game", "Adventure"), ("2016 farm life simulation game", "Simulation"),
     ("2011 puzzle-platform video game", "Puzzle"), ("2014 online collectible card game", "Strategy"),
     ("2011 sandbox game", "")],
)
def test_game_genre_from_the_description(text, genre):
    assert base.genre_by_priority(text, wikipedia.GAME_GENRES) == genre


def test_long_descriptions_are_cut_to_fit():
    text = base.plain_text("<p>" + "word " * 1000 + "</p>")
    assert len(text) == base.MAX_DESCRIPTION and text.endswith("…")


# --- TMDB, used for movies only when a key is set ---


def test_movies_use_wikipedia_without_a_key():
    assert lookup.source_for(Kind.MOVIE).name == "Wikipedia"


def test_movies_use_tmdb_with_a_key(tmdb_key):
    assert lookup.source_for(Kind.MOVIE).name == "TMDB"
    assert lookup.source_for(Kind.GAME).name == "Wikipedia"  # the key only changes movies


def test_tmdb_movies(tmdb_key):
    (match,) = tmdb.search("arrival")
    assert (match.title, match.year, match.genre) == ("Arrival", 2016, "Sci-Fi")  # from the genre ids
    assert match.thumb_url == "https://image.tmdb.org/t/p/w92/x2FJsf1ElAgr63Y3PNPtJrcmpoe.jpg"
    movie = tmdb.details("329865")
    assert movie.genre == "Sci-Fi"  # TMDB's "Science Fiction"; its "Drama" comes first but says less
    assert movie.image_url == "https://image.tmdb.org/t/p/w780/x2FJsf1ElAgr63Y3PNPtJrcmpoe.jpg"
    assert tmdb.details("1") is None
    assert tmdb.details("abc") is None


def test_tmdb_short_api_key_goes_in_the_query(tmdb_key):
    tmdb.search("arrival")
    params, headers = tmdb_calls[-1]
    assert params["api_key"] == "0123456789abcdef" and "Authorization" not in headers


def test_tmdb_read_access_token_goes_in_a_header(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "eyJhbGciOiJIUzI1NiJ9.token")
    tmdb.search("arrival")
    params, headers = tmdb_calls[-1]
    assert headers["Authorization"] == "Bearer eyJhbGciOiJIUzI1NiJ9.token" and "api_key" not in params


def test_a_refused_key_says_so():
    with pytest.raises(lookup.LookupFailed, match="check the one in your .env file"):
        base._json(httpx.Response(401, json={"status_message": "Invalid API key"}))


def test_form_shows_the_tmdb_credit_only_with_tmdb(client, tmdb_key):
    assert tmdb.NOTICE in client.get("/titles/new?kind=movie").text


def test_form_has_no_tmdb_credit_without_a_key(client):
    assert tmdb.NOTICE not in client.get("/titles/new?kind=movie").text


# --- The .env file ---


def test_env_file_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv("MEDIAGALA_TEST_A", raising=False)
    monkeypatch.delenv("MEDIAGALA_TEST_B", raising=False)
    monkeypatch.setenv("MEDIAGALA_TEST_C", "from the terminal")
    env = tmp_path / ".env"
    env.write_text('# a comment\n\nMEDIAGALA_TEST_A=abc123\nMEDIAGALA_TEST_B = "quoted"\nMEDIAGALA_TEST_C=from the file\n')
    load_env_file(env)
    assert (os.environ["MEDIAGALA_TEST_A"], os.environ["MEDIAGALA_TEST_B"]) == ("abc123", "quoted")
    assert os.environ["MEDIAGALA_TEST_C"] == "from the terminal"  # already set: left alone
    monkeypatch.delenv("MEDIAGALA_TEST_A")
    monkeypatch.delenv("MEDIAGALA_TEST_B")


def test_missing_env_file_is_fine(tmp_path):
    load_env_file(tmp_path / "nothing-here")


# --- The endpoints the form calls ---


@pytest.mark.parametrize(
    ("kind", "query", "source", "title"),
    [("movie", "arrival", "Wikipedia", "Arrival"), ("series", "severance", "TVmaze", "Severance"),
     ("anime", "frieren", "AniList", "Frieren: Beyond Journey's End"), ("game", "hades", "Wikipedia", "Hades"),
     ("book", "the name of the wind", "Open Library", "The Name of the Wind")],
)
def test_search_endpoint_for_every_kind(client, kind, query, source, title):
    body = client.get(f"/lookup/{kind}?q={query}").json()
    assert body["source"] == source
    assert body["results"][0]["title"] == title


def test_movie_search_endpoint_with_tmdb(client, tmdb_key):
    body = client.get("/lookup/movie?q=arrival").json()
    assert body["source"] == "TMDB" and body["results"][0]["source_id"] == "329865"


def test_short_queries_dont_call_the_service(client, monkeypatch):
    monkeypatch.setattr(base, "get_json", offline)
    assert client.get("/lookup/series?q=s").json()["results"] == []


def test_details_endpoint(client):
    assert client.get("/lookup/series/44933").json()["result"]["seasons"] == [9, 10]
    assert client.get("/lookup/book/OL8479867W").json()["result"]["author"] == "Patrick Rothfuss"
    assert client.get("/lookup/series/123").status_code == 404


def test_unknown_kind(client):
    assert client.get("/lookup/vinyl?q=abbey").status_code == 404


def test_service_down_gives_a_friendly_error(client, monkeypatch):
    monkeypatch.setattr(base, "get_json", offline)
    response = client.get("/lookup/series?q=severance")
    assert response.status_code == 502
    assert "fill in the form by hand" in response.json()["error"]


def test_form_has_the_search_box(client):
    page = client.get("/titles/new?kind=book").text
    assert "data-lookup" in page and "Open Library" in page


# --- Quick add: one click puts a search result in the fridge ---


def test_quick_add_puts_a_result_in_the_fridge_as_planned(client, db):
    response = client.post("/lookup/series/44933/add")
    assert response.status_code == 201
    item = db.get(Title, response.json()["id"])
    assert (item.title, item.year, item.genre, item.status) == ("Severance", 2022, "Sci-Fi", Status.PLANNED)
    assert [season.episode_count for season in item.seasons] == [9, 10]
    assert item.poster_filename.endswith(".webp")


def test_quick_add_twice_points_to_the_one_in_the_fridge(client):
    first = client.post("/lookup/series/44933/add").json()["id"]
    response = client.post("/lookup/series/44933/add")
    assert response.status_code == 409 and response.json()["id"] == first


def test_search_marks_what_is_already_in_the_fridge(client, make_title):
    item = make_title(title="Severance", kind="series", genre="Drama", year=2022, seasons=["9"])
    (series,) = client.get("/lookup/series?q=severance").json()["results"]
    assert series["in_collection"] == item.id
    (book,) = client.get("/lookup/book?q=the name of the wind").json()["results"]
    assert book["in_collection"] is None


def test_titles_match_loosely(db, make_title):
    item = make_title(title="Frieren: Beyond Journey's End", kind="anime", genre="Fantasy", year=2023, seasons=["28"])
    candidates = [
        ("frieren:  beyond journey’s end", 2023),  # case, spacing and a curly apostrophe don't matter
        ("Frieren: Beyond Journey's End", 2020),  # another year is another title
        ("Frieren: Beyond Journey's End", None),  # an unknown year matches any
    ]
    assert crud.find_in_collection(db, Kind.ANIME, candidates) == [item.id, None, item.id]


def test_quick_add_sends_you_to_the_form_when_a_detail_is_missing(client, db):
    response = client.post("/lookup/game/Minecraft/add")  # Wikipedia names no genre for it
    assert response.status_code == 422
    assert response.json()["form_url"] == "/titles/new?kind=game&pick=Minecraft"
    assert db.query(Title).count() == 0


def test_quick_add_without_a_cover_when_the_image_fails(client, db, monkeypatch):
    monkeypatch.setattr(lookup, "_download", offline)
    item = db.get(Title, client.post("/lookup/anime/154587/add").json()["id"])
    assert item.poster_filename is None  # gets a typeset cover instead
    assert item.seasons[0].episode_count == 28


def test_quick_add_of_something_unknown(client):
    assert client.post("/lookup/series/123/add").status_code == 404
    assert client.post("/lookup/vinyl/1/add").status_code == 404


def test_home_names_what_was_just_added(client, make_title):
    item = make_title(title="Arrival")
    page = client.get(f"/?added={item.id}").text
    assert "Added <strong>Arrival</strong> to the fridge (Watchlist)" in page
    assert f'action="/titles/{item.id}/delete"' in page  # Undo
    assert 'class="card is-new"' in page


def test_home_counts_several_added_and_ignores_junk(client, make_title):
    first, second = make_title(title="Arrival").id, make_title(title="Heat").id
    assert "Added 2 titles to the fridge." in client.get(f"/?added={first},{second}").text
    assert "to the fridge" not in client.get("/?added=abc,99999,<b>").text


def test_every_page_has_the_quick_add(client):
    page = client.get("/titles/new").text
    assert 'id="quick-add"' in page and "data-quick-add" in page and "js/quick-add.js" in page


# --- Images picked online ---


def series_form(**fields):
    return form(kind="series", genre="Drama", season_episodes=["9"], **fields)


def test_picked_cover_is_downloaded_on_save(client):
    response = client.post("/titles", data=series_form(poster_url="https://static.tvmaze.com/o.jpg"))
    assert response.status_code == 303
    (saved,) = POSTER_DIR.iterdir()
    assert saved.suffix == ".webp"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/x.png",
        "http://static.tvmaze.com/o.jpg",  # not HTTPS
        "https://static.tvmaze.com.evil.example/o.jpg",  # looks similar, different site
        "https://user@static.tvmaze.com/o.jpg",
        "file:///C:/secret.png",
        "/etc/passwd",
    ],
)
def test_covers_only_come_from_the_sources_image_sites(client, url):
    response = client.post("/titles", data=series_form(poster_url=url))
    assert response.status_code == 422
    assert "That image can&#39;t be used." in response.text
    assert not any(POSTER_DIR.iterdir())


@pytest.mark.parametrize(
    ("url", "allowed"),
    [("https://image.tmdb.org/t/p/w780/x.jpg", True), ("https://s4.anilist.co/x.jpg", True),
     ("https://ia800505.us.archive.org/x.jpg", True), ("https://notarchive.org/x.jpg", False),
     ("https://archive.org.evil.example/x.jpg", False)],
)
def test_image_sites_include_subdomains_only(url, allowed):
    assert lookup._allowed(httpx.URL(url)) is allowed


def test_redirects_to_other_sites_are_refused():
    def redirect_elsewhere(request):
        if request.url.host == "covers.openlibrary.org":
            return httpx.Response(302, headers={"Location": "https://evil.example/x.jpg"})
        return httpx.Response(200, content=PNG)

    client = httpx.Client(transport=httpx.MockTransport(redirect_elsewhere), follow_redirects=True,
                          event_hooks={"request": [lookup._check_each_request]})
    with pytest.raises(lookup.LookupFailed):
        client.get("https://covers.openlibrary.org/b/id/1-L.jpg")


def test_a_fake_image_online_is_still_rejected(client, monkeypatch):
    monkeypatch.setattr(lookup, "_download", lambda url, limit: b"<html>not an image</html>")
    response = client.post("/titles", data=series_form(poster_url="https://static.tvmaze.com/o.jpg"))
    assert response.status_code == 422
    assert not any(POSTER_DIR.iterdir())


def test_picked_cover_survives_a_form_error(client):
    response = client.post("/titles", data=series_form(title="", poster_url="https://static.tvmaze.com/o.jpg"))
    assert response.status_code == 422
    assert 'name="poster_url" value="https://static.tvmaze.com/o.jpg"' in response.text


# --- Details: credits, links and trailers for the title's page ---


def test_tmdb_details_have_credits_and_the_official_trailer(tmdb_key):
    movie = tmdb.details("329865")
    assert dict(movie.facts) == {
        "Director": "Denis Villeneuve",
        "Writers": "Eric Heisserer",  # the screenplay, not the short story it's based on
        "Starring": "Amy Adams, Jeremy Renner, Forest Whitaker, Michael Stuhlbarg",
        "Runtime": "1 h 56 min",
        "Rating on TMDB": "7.6/10",
    }
    assert movie.trailer_url == "https://www.youtube.com/watch?v=tFMo3UJ4B4g"  # official beats fan-made
    assert movie.page_url == "https://www.themoviedb.org/movie/329865"
    assert tmdb_calls[-1][0]["append_to_response"] == "credits,videos"  # still one request
    assert tmdb.search("arrival")[0].facts == ()  # search results stay light


def test_tvmaze_details():
    series = tvmaze.details("44933")
    assert dict(series.facts) == {
        "Created by": "Dan Erickson",
        "Starring": "Adam Scott, Britt Lower",  # cast entries without a person are skipped
        "Network": "Apple TV+",  # a streaming channel when there's no TV network
        "Status": "Running",
        "Episode length": "49 min",
        "Rating on TVmaze": "8.4/10",
    }
    assert series.page_url == "https://www.tvmaze.com/shows/44933"


def test_anilist_details():
    anime = anilist.details("154587")
    assert dict(anime.facts) == {
        "Studio": "Madhouse", "Format": "TV series", "Based on": "Manga", "Status": "Finished",
        "Episode length": "24 min", "Rating on AniList": "8.9/10",
    }
    assert anime.trailer_url == "https://www.youtube.com/watch?v=qgQHnKEf4VE"  # AniList's stray tab trimmed
    assert anime.page_url == "https://anilist.co/anime/154587"


def test_open_library_details():
    book = openlibrary.details("OL8479867W")
    assert dict(book.facts) == {
        "Characters": "Kvothe, Denna, Bast", "Setting": "Imre, Tarbean", "Editions": "112",
        "Rating on Open Library": "4.4/5",
    }
    assert book.page_url == "https://openlibrary.org/works/OL8479867W"


def test_wikipedia_details_link_to_the_article():
    movie = wikipedia.movie_details("Arrival_(film)")
    assert dict(movie.facts) == {"Director": "Denis Villeneuve"}
    assert movie.page_url == "https://en.wikipedia.org/wiki/Arrival_%28film%29"
    assert dict(wikipedia.game_details("Hades_(video_game)").facts) == {"Developer": "Supergiant Games"}


@pytest.mark.parametrize(
    ("text", "verb", "names"),
    [
        ("Arrival is a 2016 film directed by Denis Villeneuve and written by Eric Heisserer.", "directed",
         "Denis Villeneuve"),
        ("…a dark fantasy film produced, written, and directed by Guillermo del Toro.", "directed",
         "Guillermo del Toro"),
        ("…film written, directed, produced, and edited by Joel and Ethan Coen, based on…", "directed",
         "Joel and Ethan Coen"),
        ("…film directed by Bong Joon Ho, who co-wrote the screenplay.", "directed", "Bong Joon Ho"),
        ("…a sandbox game developed and published by the Swedish company Mojang Studios. Following…",
         "developed and published", "Mojang Studios"),
        ('…a farm life simulation video game developed by Eric "ConcernedApe" Barone. Players…', "[Dd]eveloped",
         "Eric Barone"),
        ("…George R. R. Martin. Developed by FromSoftware and published by Bandai Namco Entertainment, it was…",
         "[Dd]eveloped", "FromSoftware"),
        ("…and published by Bandai Namco Entertainment, it was first released…", "published",
         "Bandai Namco Entertainment"),
        ("Created by D. B. Weiss.", "Created", "D. B. Weiss"),
        ("A film about a man who was directed by fate.", "directed", ""),  # no name: nothing
        ("Nothing to see here.", "directed", ""),
    ],
)
def test_wikipedia_credits_from_a_sentence(text, verb, names):
    assert wikipedia.credit(text, verb) == names


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("The film stars Amy Adams as Louise Banks, a linguist engaged by the Army.", "Amy Adams"),
        ("It stars Song Kang-ho, Lee Sun-kyun, Cho Yeo-jeong, Choi Woo-shik, and Park So-dam.",
         "Song Kang-ho, Lee Sun-kyun, Cho Yeo-jeong, Choi Woo-shik"),  # the first four
        ("Starring Tommy Lee Jones, Javier Bardem, and Josh Brolin, the film is set in Texas.",
         "Tommy Lee Jones, Javier Bardem, Josh Brolin"),
        ("A film with no cast list.", ""),
    ],
)
def test_wikipedia_cast_from_a_sentence(text, names):
    assert wikipedia.stars(text) == names


@pytest.mark.parametrize(
    ("video_id", "url"),
    [("tFMo3UJ4B4g", "https://www.youtube.com/watch?v=tFMo3UJ4B4g"), (" qgQHnKEf4VE\t", "https://www.youtube.com/watch?v=qgQHnKEf4VE"),
     ('x"><script>', ""), ("../../evil", ""), ("", ""), (None, "")],
)
def test_trailer_links_are_only_built_from_real_video_ids(video_id, url):
    assert base.youtube(video_id) == url


def test_helpers_for_details():
    assert [base.duration(m) for m in (116, 60, 24, 0, None)] == ["1 h 56 min", "1 h", "24 min", "", ""]
    assert base.names(["A", " B ", "", None, "A", "C", "D", "E"]) == "A, B, C, D"  # no blanks or repeats
    assert base.facts(("Director", "X"), ("Runtime", ""), ("Editions", 0)) == (("Director", "X"),)


def test_quick_add_keeps_the_details(client, db):
    item = db.get(Title, client.post("/lookup/anime/154587/add").json()["id"])
    assert (item.source, item.source_id) == ("AniList", "154587")
    assert ["Studio", "Madhouse"] in item.facts
    assert item.source_url == "https://anilist.co/anime/154587"
    assert item.trailer_url == "https://www.youtube.com/watch?v=qgQHnKEf4VE"


def test_the_form_saves_the_details_of_the_picked_result(client, db):
    response = client.post("/titles", data=series_form(title="Severance", lookup_source="TVmaze", lookup_id="44933"))
    assert response.status_code == 303
    item = db.query(Title).one()
    assert (item.source, item.source_id, item.source_url) == ("TVmaze", "44933", "https://www.tvmaze.com/shows/44933")
    assert ["Created by", "Dan Erickson"] in item.facts


@pytest.mark.parametrize(
    ("source", "source_id"),
    [("TMDB", "329865"),  # no key set: TMDB can't be used
     ("Evil", "1"), ("TVmaze", "123"), ("TVmaze", "../x"), ("", "")],
)
def test_a_bad_pick_saves_the_title_without_details(client, db, source, source_id):
    response = client.post("/titles", data=form(lookup_source=source, lookup_id=source_id))
    assert response.status_code == 303
    item = db.query(Title).one()
    assert (item.source, item.facts, item.source_url) == ("", [], "")


def test_details_are_never_taken_from_the_form(client, db):
    fields = series_form(lookup_source="TVmaze", lookup_id="44933", source_url="https://evil.example",
                         trailer_url="javascript:alert(1)", facts="[]")
    client.post("/titles", data=fields)
    item = db.query(Title).one()
    assert item.source_url == "https://www.tvmaze.com/shows/44933" and item.trailer_url == ""


def test_service_down_while_saving_still_saves(client, db, monkeypatch):
    monkeypatch.setattr(base, "get_json", offline)
    response = client.post("/titles", data=series_form(lookup_source="TVmaze", lookup_id="44933"))
    assert response.status_code == 303
    assert db.query(Title).one().facts == []


def test_editing_without_a_new_pick_keeps_the_details(client, db):
    item = db.get(Title, client.post("/lookup/series/44933/add").json()["id"])
    fields = form(kind="series", genre="Drama", title="Severance", year="2022", season_episodes=["9", "10"])
    assert client.post(f"/titles/{item.id}/edit", data=fields).status_code == 303
    db.refresh(item)
    assert item.source == "TVmaze" and item.facts


def test_title_page_shows_the_details(client, db):
    item = db.get(Title, client.post("/lookup/anime/154587/add").json()["id"])
    page = client.get(f"/titles/{item.id}").text
    assert "<dt>Studio</dt><dd>Madhouse</dd>" in page
    assert 'href="https://www.youtube.com/watch?v=qgQHnKEf4VE"' in page and "Trailer" in page
    assert 'href="https://anilist.co/anime/154587"' in page
    assert 'rel="noopener noreferrer"' in page
    assert "Refresh" in page


def test_tmdb_credit_on_the_title_page(client, db, tmdb_key):
    client.post("/titles", data=form(lookup_source="TMDB", lookup_id="329865"))
    page = client.get(f"/titles/{db.query(Title).one().id}").text
    assert tmdb.NOTICE in page and "<li>1 h 56 min</li>" in page  # the runtime is a chip, not a detail row


# --- "Get details" for titles added before (or by hand) ---


def test_get_details_finds_the_title_by_name_and_year(client, db, make_title):
    item = make_title(title="severance", kind="series", genre="Drama", year=2022, seasons=["9"])
    response = client.post(f"/titles/{item.id}/details")
    assert response.headers["location"] == f"/titles/{item.id}?msg=details"
    db.refresh(item)
    assert (item.source, item.source_id) == ("TVmaze", "44933")
    assert item.description == "Mark leads a team at Lumon & finds a mystery."  # was empty: filled in
    assert item.poster_filename.endswith(".webp")  # had none: downloaded
    assert item.title == "severance"  # your own fields are left alone


def test_get_details_keeps_what_you_wrote(client, db, make_title):
    item = make_title(title="Severance", kind="series", genre="Drama", year=2022, seasons=["9"], description="Mine.")
    client.post(f"/titles/{item.id}/details")
    db.refresh(item)
    assert item.description == "Mine." and item.facts


def test_get_details_uses_the_source_it_was_picked_from(client, db, make_title):
    item = db.get(Title, client.post("/lookup/series/44933/add").json()["id"])
    item.facts = []
    db.commit()
    client.post(f"/titles/{item.id}/details")
    db.refresh(item)
    assert item.facts


def test_get_details_for_something_not_online(client, make_title):
    item = make_title(title="My Home Video", year=2020)
    response = client.post(f"/titles/{item.id}/details")
    assert response.headers["location"] == f"/titles/{item.id}?msg=details_missing"
    assert "Find it online" in client.get(response.headers["location"]).text


def test_get_details_with_another_year_is_not_a_match(client, make_title):
    item = make_title(title="Severance", kind="series", genre="Drama", year=1999, seasons=["9"])
    assert client.post(f"/titles/{item.id}/details").headers["location"].endswith("msg=details_missing")


def test_get_details_while_offline(client, monkeypatch, make_title):
    item = make_title(title="Severance", kind="series", genre="Drama", year=2022, seasons=["9"])
    monkeypatch.setattr(base, "get_json", offline)
    assert client.post(f"/titles/{item.id}/details").headers["location"].endswith("msg=details_offline")


def test_title_page_offers_to_get_details(client, make_title):
    item = make_title(title="Severance", kind="series", genre="Drama", year=2022, seasons=["9"])
    page = client.get(f"/titles/{item.id}").text
    assert f'action="/titles/{item.id}/details"' in page and "Get details from TVmaze" in page
