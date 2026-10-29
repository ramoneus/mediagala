"""Books from Open Library (https://openlibrary.org/developers/api), free and with no key."""

import re
from functools import lru_cache

from app.lookup import base
from app.lookup.base import MAX_RESULTS, Match
from app.schemas import MAX_PAGES

NAME = "Open Library"
API = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org/b/id"
FIELDS = "key,title,author_name,first_publish_year,number_of_pages_median,cover_i,subject"

# Open Library has thousands of free-form subjects. These words map them to the app's genres;
# the order is the priority, so "science fiction" wins over the plain "fiction" a book also has.
SUBJECT_GENRES = [
    ("comics", "Comics & Manga"),
    ("manga", "Comics & Manga"),
    ("graphic novel", "Comics & Manga"),
    ("science fiction", "Sci-Fi"),
    ("fantasy", "Fantasy"),
    ("horror", "Horror"),
    ("detective", "Mystery"),
    ("mystery", "Mystery"),
    ("thriller", "Thriller"),
    ("suspense", "Thriller"),
    ("love stories", "Romance"),
    ("romance", "Romance"),
    ("historical fiction", "Historical Fiction"),
    ("poetry", "Poetry"),
    ("biography", "Biography"),
    ("autobiography", "Biography"),
    ("philosophy", "Philosophy"),
    ("self-help", "Self-help"),
    ("history", "History"),
    ("science", "Science"),
    ("classic", "Classics"),
    ("fiction", "Fiction"),
]


def _genre(subjects: list[str]) -> str:
    return base.genre_by_priority(" | ".join(subjects), SUBJECT_GENRES)


def _match(doc: dict, description: str = "", subjects: list[str] | None = None) -> Match:
    cover = doc.get("cover_i")
    pages = doc.get("number_of_pages_median")
    return Match(
        source_id=doc["key"].removeprefix("/works/"),
        title=doc.get("title") or "",
        year=doc.get("first_publish_year"),
        genre=_genre(subjects if subjects is not None else doc.get("subject") or []),
        description=description,
        image_url=f"{COVERS}/{cover}-L.jpg" if cover else "",
        thumb_url=f"{COVERS}/{cover}-M.jpg" if cover else "",
        author=(doc.get("author_name") or [""])[0],
        pages=min(pages, MAX_PAGES) if pages else None,
    )


def _description(work: dict) -> str:
    text = work.get("description") or ""
    if isinstance(text, dict):
        text = text.get("value") or ""
    # Many descriptions end with a "----------" block of links to other editions.
    return base.plain_text(text.split("----------")[0])


@lru_cache(maxsize=128)
def search(query: str) -> tuple[Match, ...]:
    body = base.get_json(f"{API}/search.json", {"q": query, "limit": MAX_RESULTS, "fields": FIELDS}) or {}
    return tuple(_match(doc) for doc in body.get("docs") or [] if doc.get("key"))


@lru_cache(maxsize=128)
def details(work_id: str) -> Match | None:
    if not re.fullmatch(r"OL\d+W", work_id):
        return None
    body = base.get_json(f"{API}/search.json", {"q": f"key:/works/{work_id}", "fields": FIELDS}) or {}
    docs = body.get("docs") or []
    if not docs:
        return None
    work = base.get_json(f"{API}/works/{work_id}.json") or {}
    return _match(docs[0], _description(work), (work.get("subjects") or []) + (docs[0].get("subject") or []))
