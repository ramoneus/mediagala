"""Database engine, session factory and the declarative base."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'movies.db'}"

# check_same_thread=False: FastAPI may serve a request on a different thread
# than the one that opened the connection. Each request still gets its own session.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    # SQLite ignores foreign keys (and ON DELETE CASCADE) unless this is switched on per connection.
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so they are registered on Base.metadata before create_all.
    from app import models  # noqa: F401

    _rename_legacy_table()
    Base.metadata.create_all(engine)
    _add_missing_columns()


# Lightweight migrations for databases created by earlier versions of the app.
# create_all() only creates missing tables and never alters existing ones;
# for a project this size that's simpler than adding Alembic.

NEW_COLUMNS = {
    "poster_filename": "VARCHAR(100)",
    "kind": "VARCHAR(20) NOT NULL DEFAULT 'movie'",
    "progress_season": "INTEGER",
    "progress_episode": "INTEGER",
    "completion": "VARCHAR(20)",
    "hours_played": "INTEGER",
    "author": "VARCHAR(200) NOT NULL DEFAULT ''",
    "pages": "INTEGER",
    "current_page": "INTEGER",
}


def _rename_legacy_table() -> None:
    """The table was called "movies" before series were added."""
    tables = inspect(engine).get_table_names()
    if "movies" in tables and "titles" not in tables:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE movies RENAME TO titles"))


def _add_missing_columns() -> None:
    existing = {column["name"] for column in inspect(engine).get_columns("titles")}
    with engine.begin() as conn:
        for name, definition in NEW_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE titles ADD COLUMN {name} {definition}"))
