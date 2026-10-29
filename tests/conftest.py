"""Shared test setup: every test runs against a fresh database in a temporary folder,
so the tests never touch your real collection in data/."""

import io
import os
import shutil
import tempfile

# Must be set before the app is imported: app.database reads it at import time.
TEST_DATA_DIR = tempfile.mkdtemp(prefix="mediagala-tests-")
os.environ["MEDIAGALA_DATA_DIR"] = TEST_DATA_DIR
# Keep your own .env out of the tests: variables already set aren't replaced by it.
os.environ["TMDB_API_KEY"] = ""

import pytest  # noqa: E402
from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import crud  # noqa: E402
from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Title  # noqa: E402
from app.posters import POSTER_DIR  # noqa: E402
from app.schemas import TitleIn  # noqa: E402



def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (40, 25), mode: str = "RGB") -> bytes:
    """A real, tiny image file in the given format."""
    output = io.BytesIO()
    Image.new(mode, size, "white").save(output, fmt)
    return output.getvalue()


PNG = image_bytes("PNG")


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()  # release the SQLite file so Windows lets us delete it
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    init_db()
    for file in POSTER_DIR.iterdir():
        file.unlink()


@pytest.fixture
def client():
    # follow_redirects=False so tests can check the 303 redirects themselves.
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def make_title(db):
    """Add a title straight to the database. Defaults to a planned movie."""

    def make(**fields) -> Title:
        data = {"title": "Arrival", "year": 2016, "genre": "Sci-Fi", **fields}
        return crud.create_title(db, TitleIn.model_validate(data))

    return make


def form(**fields) -> dict:
    """Form fields as the browser sends them (all strings). Defaults to a planned movie."""
    return {
        "kind": "movie",
        "title": "Arrival",
        "year": "2016",
        "genre": "Sci-Fi",
        "description": "",
        "status": "watchlist",
        "rating": "",
        **fields,
    }
