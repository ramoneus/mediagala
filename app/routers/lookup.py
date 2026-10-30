"""JSON endpoints behind the online search: the form's "Find it online" box and the quick add."""

import io
from dataclasses import asdict
from urllib.parse import urlencode

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app import crud, lookup, posters
from app.catalog import Kind, Status
from app.routers.titles import DbSession, parse_choice
from app.schemas import TitleIn

router = APIRouter(prefix="/lookup")

MIN_QUERY = 2
MAX_QUERY = 100
NO_SOURCE = "There's no online search for this kind yet."


def _source(kind: str) -> tuple[Kind | None, lookup.Source | None]:
    title_kind = parse_choice(Kind, kind)
    return title_kind, lookup.source_for(title_kind) if title_kind else None


def _error(message: str, status_code: int, **extra: object) -> JSONResponse:
    return JSONResponse({"error": message, **extra}, status_code=status_code)


@router.get("/{kind}", name="lookup_search")
def search(kind: str, db: DbSession, q: str = "") -> JSONResponse:
    title_kind, source = _source(kind)
    if source is None:
        return _error(NO_SOURCE, 404)
    query = q.strip()[:MAX_QUERY]
    if len(query) < MIN_QUERY:
        return JSONResponse({"source": source.name, "results": []})
    try:
        matches = source.search(query)
    except lookup.LookupFailed as exc:
        return _error(str(exc), 502)
    # Mark what's already in the fridge, so the quick add can say so before you click.
    owned = crud.find_in_collection(db, title_kind, [(match.title, match.year) for match in matches])
    results = [{**asdict(match), "in_collection": title_id} for match, title_id in zip(matches, owned, strict=True)]
    return JSONResponse({"source": source.name, "results": results})


@router.get("/{kind}/{source_id}", name="lookup_details")
def details(kind: str, source_id: str) -> JSONResponse:
    _, source = _source(kind)
    if source is None:
        return _error(NO_SOURCE, 404)
    try:
        match = source.details(source_id)
    except lookup.LookupFailed as exc:
        return _error(str(exc), 502)
    if match is None:
        return _error("That title wasn't found.", 404)
    return JSONResponse({"source": source.name, "result": asdict(match)})


@router.post("/{kind}/{source_id}/add", name="lookup_add")
def quick_add(kind: str, source_id: str, db: DbSession) -> JSONResponse:
    """The quick add's "+" button: put a search result straight into the fridge, as planned.

    Details and cover come from the source here on the server, so the browser only names the result.
    """
    title_kind, source = _source(kind)
    if source is None:
        return _error(NO_SOURCE, 404)
    try:
        match = source.details(source_id)
    except lookup.LookupFailed as exc:
        return _error(str(exc), 502)
    if match is None:
        return _error("That title wasn't found.", 404)

    (existing,) = crud.find_in_collection(db, title_kind, [(match.title, match.year)])
    if existing:
        return _error("Already in your fridge.", 409, id=existing)

    try:
        data = TitleIn.model_validate(
            {
                "kind": title_kind,
                "title": match.title,
                "year": match.year,
                "genre": match.genre,
                "description": match.description,
                "status": Status.PLANNED,
                "seasons": [str(count) for count in match.seasons],
                "author": match.author,
                "pages": match.pages,
            }
        )
    except ValidationError:
        # Something the form insists on is missing (no genre, no seasons yet…): finish it there.
        form_url = "/titles/new?" + urlencode({"kind": title_kind.value, "pick": source_id})
        return _error("A few details are missing.", 422, form_url=form_url)

    filename = None
    if match.image_url:
        try:
            filename = posters.save_poster(*posters.read_poster(io.BytesIO(lookup.fetch_image(match.image_url))))
        except (lookup.LookupFailed, posters.PosterError):
            pass  # added without an image: it gets a typeset cover instead
    try:
        item = crud.create_title(db, data, poster_filename=filename, online=(source.name, match))
    except Exception:
        posters.delete_poster(filename)  # don't leave an orphaned file behind
        raise
    return JSONResponse({"id": item.id, "title": item.title}, status_code=201)
