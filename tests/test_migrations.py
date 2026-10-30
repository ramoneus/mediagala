"""Databases from older versions of the app are upgraded on start-up without losing data."""

from sqlalchemy import inspect, text

from app.catalog import Kind, Status
from app.database import Base, engine, init_db
from app.models import Title


def test_movies_table_from_the_first_version_is_upgraded(db):
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE movies (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                year INTEGER NOT NULL,
                genre VARCHAR(50) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                rating INTEGER,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("INSERT INTO movies (title, year, genre, rating, status) VALUES ('Alien', 1979, 'Horror', 9, 'watched')"))

    init_db()

    tables = inspect(engine).get_table_names()
    assert "titles" in tables and "movies" not in tables and "seasons" in tables
    movie = db.query(Title).one()
    assert (movie.title, movie.kind, movie.status, movie.rating, movie.author) == ("Alien", Kind.MOVIE, Status.FINISHED, 9, "")
    # Columns added later start empty.
    assert (movie.notes, movie.platform, movie.started_on, movie.facts, movie.source) == ("", "", None, [], "")


def test_starting_twice_changes_nothing():
    init_db()
    init_db()
    assert {"titles", "seasons"} <= set(inspect(engine).get_table_names())
