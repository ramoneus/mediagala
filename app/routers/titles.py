"""HTML routes for movies, series and games: list, detail, create, edit, delete,
plus ticking off watched episodes of a series.

Every state-changing action is a POST that ends in a 303 redirect
(Post/Redirect/Get), so refreshing the page never re-submits a form.
"""

import enum
import io
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app import crud, lookup, posters
from app.catalog import (
    ALL_GENRES,
    EPISODIC_KINDS,
    GENERIC_STATUS_LABELS,
    PAGED_KINDS,
    Completion,
    Kind,
    Status,
    form_config,
)
from app.database import get_db
from app.models import Title
from app.schemas import ENDED, MAX_HOURS_PLAYED, MAX_NOTES, MAX_PAGES, MAX_YEAR, TitleIn, form_errors
from app.templating import templates

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

MAX_ADDED = 50  # titles the quick add can report in one go

# Flash messages are chosen by key from this dict, so the query string can't inject text.
FLASH_MESSAGES = {
    "created": "Added to your collection.",
    "updated": "Changes saved.",
    "deleted": "Removed from your collection.",
    "details": "Details filled in from the online database.",
    "details_missing": "It wasn't found online under this title and year. Edit it and pick it in “Find it online”.",
    "details_offline": "The online database didn't answer. Try again in a moment.",
}


# --- Dependencies -----------------------------------------------------------


async def read_title_form(request: Request) -> dict[str, Any]:
    """Read only the fields we expect from the submitted form, as stripped strings."""
    form = await request.form()
    data: dict[str, Any] = {
        name: str(form.get(name, "")).strip() for name in TitleIn.model_fields if name != "seasons"
    }
    # One "season_episodes" input per season, in order.
    data["seasons"] = [str(value).strip() for value in form.getlist("season_episodes")]
    return data


TitleFormData = Annotated[dict[str, Any], Depends(read_title_form)]


@dataclass(frozen=True)
class PosterInput:
    upload: UploadFile | None  # None when no file was chosen
    remove: bool  # "Remove current image" checkbox on the edit form
    url: str  # cover picked in "Find it online" ("" if none); used when no file was chosen


async def read_poster_input(request: Request) -> PosterInput:
    form = await request.form()  # Starlette caches the parsed form, so this doesn't re-read the body.
    upload = form.get("poster")
    # Browsers send an empty, nameless file part when nothing was selected.
    has_file = isinstance(upload, UploadFile) and bool(upload.filename)
    return PosterInput(
        upload=upload if has_file else None,
        remove=form.get("remove_poster") == "1",
        url=str(form.get("poster_url", "")).strip(),
    )


PosterFormData = Annotated[PosterInput, Depends(read_poster_input)]


@dataclass(frozen=True)
class LookupPick:
    """The result picked in "Find it online", if any: which source and its id there."""

    source: str
    source_id: str


async def read_lookup_pick(request: Request) -> LookupPick:
    form = await request.form()
    return LookupPick(
        source=str(form.get("lookup_source", "")).strip()[:30],
        source_id=str(form.get("lookup_id", "")).strip()[:100],
    )


LookupFormData = Annotated[LookupPick, Depends(read_lookup_pick)]


def get_title_or_404(title_id: int, db: DbSession) -> Title:
    item = crud.get_title(db, title_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that title.")
    return item


ExistingTitle = Annotated[Title, Depends(get_title_or_404)]


def get_series_or_404(item: ExistingTitle) -> Title:
    if not item.kind.has_episodes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only series and anime have episodes.")
    return item


ExistingSeries = Annotated[Title, Depends(get_series_or_404)]


def get_book_or_404(item: ExistingTitle) -> Title:
    if not item.kind.has_pages:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only books have pages.")
    return item


ExistingBook = Annotated[Title, Depends(get_book_or_404)]


# --- Helpers ----------------------------------------------------------------


def parse_choice[E: enum.StrEnum](choices: type[E], value: str) -> E | None:
    """Turn a query-string value into an enum member, ignoring unknown values."""
    try:
        return choices(value)
    except ValueError:
        return None


def index_url(**params: str) -> str:
    query = urlencode({key: value for key, value in params.items() if value})
    return f"/?{query}" if query else "/"


def safe_return_path(value: str) -> str:
    """Only allow redirects back to our own pages (prevents open redirects)."""
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


def redirect_after_progress(item: Title, default_url: str) -> RedirectResponse:
    # Just ticked off the final episode: send the user to rate it and mark it watched.
    if item.next_episode is None:
        return redirect(f"/titles/{item.id}/edit?finished=1")
    return redirect(default_url)


def form_from_title(item: Title) -> dict[str, Any]:
    return {
        "kind": item.kind.value,
        "title": item.title,
        "year": item.year,
        "genre": item.genre,
        "description": item.description,
        "status": item.status.value,
        "rating": item.rating,
        "seasons": [season.episode_count for season in item.seasons],
        "progress_season": item.progress_season,
        "progress_episode": item.progress_episode,
        "completion": item.completion.value if item.completion else "",
        "hours_played": item.hours_played,
        "author": item.author,
        "pages": item.pages,
        "current_page": item.current_page,
        "platform": item.platform,
        "started_on": item.started_on.isoformat() if item.started_on else "",
        "finished_on": item.finished_on.isoformat() if item.finished_on else "",
        "notes": item.notes,
    }


def online_pick(kind: Kind, pick: LookupPick) -> crud.OnlinePick | None:
    """The details of the result picked in the form, fetched again on the server (never trusted from the form)."""
    source = lookup.source_named(kind, pick.source) if pick.source_id else None
    if source is None:
        return None
    try:
        match = source.details(pick.source_id)  # usually cached: the form asked for it a moment ago
    except lookup.LookupFailed:
        return None  # saved without them; "Get details" on the title's page can try again
    return (source.name, match) if match else None


def find_online(item: Title) -> crud.OnlinePick | None:
    """The title's details from the source it was picked from, else from a search by its name and year."""
    source = lookup.source_named(item.kind, item.source) if item.source_id else None
    if source is not None:
        match = source.details(item.source_id)
        return (source.name, match) if match else None
    source = lookup.source_for(item.kind)
    if source is None:
        return None
    wanted = crud.same_title(item.title)
    for result in source.search(item.title):
        if crud.same_title(result.title) == wanted and result.year in (None, item.year):
            match = source.details(result.source_id)
            return (source.name, match) if match else None
    return None


def validate_submission(
    raw: dict[str, Any], poster: PosterInput
) -> tuple[TitleIn | None, tuple[bytes, str] | None, dict[str, str]]:
    """Validate the fields and the optional image together, so every error is shown at once."""
    data: TitleIn | None = None
    image: tuple[bytes, str] | None = None
    errors: dict[str, str] = {}
    try:
        data = TitleIn.model_validate(raw)
    except ValidationError as exc:
        errors.update(form_errors(exc))
    try:
        if poster.upload is not None:
            image = posters.read_poster(poster.upload.file)
        elif poster.url:
            image = posters.read_poster(io.BytesIO(lookup.fetch_image(poster.url)))
    except (posters.PosterError, lookup.LookupFailed) as exc:
        errors["poster"] = str(exc)
    return data, image, errors


def render_form(
    request: Request,
    *,
    form: dict[str, Any],
    errors: dict[str, str] | None = None,
    item: Title | None = None,
    finished: bool = False,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    # The page is rendered for the submitted kind/status so the right fields start visible;
    # title-form.js keeps them in sync when the user changes either.
    current_kind = parse_choice(Kind, str(form.get("kind") or "")) or Kind.MOVIE
    # "Watched on" or "Dropped on": the end date is named after the status.
    ended = parse_choice(Status, str(form.get("status") or ""))
    ended_label = current_kind.config.status_labels.get(ended if ended in ENDED else Status.FINISHED, "Finished")
    return templates.TemplateResponse(
        request,
        "title_form.html",
        {
            "form": form,
            "errors": errors or {},
            "item": item,
            "finished": finished,
            "kinds": list(Kind),
            "current_kind": current_kind,
            "finished_label": current_kind.config.status_labels.get(Status.FINISHED, ""),
            "finished_on_label": f"{ended_label} on",
            "current_status": str(form.get("status") or Status.PLANNED.value),
            "statuses": list(Status),
            # Which kinds offer each status, e.g. "dropped" -> "series game".
            "status_kinds": {s.value: " ".join(k.value for k in Kind if s in k.config.statuses) for s in Status},
            "episodic_kinds": " ".join(k.value for k in EPISODIC_KINDS),
            "paged_kinds": " ".join(k.value for k in PAGED_KINDS),
            # Kinds you can be partway through, so they have a start date (not movies).
            "started_kinds": " ".join(k.value for k in Kind if Status.IN_PROGRESS in k.config.statuses),
            "max_pages": MAX_PAGES,
            "completions": list(Completion),
            "form_config": form_config(),
            "max_year": MAX_YEAR,
            "max_hours": MAX_HOURS_PLAYED,
            "max_notes": MAX_NOTES,
            "today": date.today().isoformat(),
            "accepted_types": posters.ACCEPTED_TYPES,
        },
        status_code=status_code,
    )


# --- Pages ------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse, name="index")
def index(
    request: Request,
    db: DbSession,
    q: str = "",
    genre: str = "",
    status_param: Annotated[str, Query(alias="status")] = "",
    kind: str = "",
    sort: str = crud.DEFAULT_SORT,
    msg: str = "",
    added: str = "",
) -> HTMLResponse:
    # Unknown filter values are ignored instead of producing an error page.
    q = q.strip()[:200]
    title_kind = parse_choice(Kind, kind)
    # Each kind has its own genres and status labels; "All" shows every genre and kind-neutral labels.
    if title_kind:
        genres = title_kind.config.genres
        status_options = list(title_kind.config.status_labels.items())
    else:
        genres = ALL_GENRES
        status_options = list(GENERIC_STATUS_LABELS.items())
    genre = genre if genre in genres else ""
    watch_status = parse_choice(Status, status_param)
    if watch_status not in dict(status_options):
        watch_status = None
    sort = sort if sort in crud.SORT_OPTIONS else crud.DEFAULT_SORT

    params = {
        "q": q,
        "genre": genre,
        "status": watch_status.value if watch_status else "",
        "kind": title_kind.value if title_kind else "",
        "sort": "" if sort == crud.DEFAULT_SORT else sort,
    }
    stats = crud.get_stats(db)
    # Titles you have "open" (in progress), shown on the shelves inside the fridge.
    open_titles = crud.list_open_titles(db, limit=5)
    tab_specs = [("All", "", stats.total)] + [(k.config.plural, k.value, stats.by_kind[k]) for k in Kind]
    kind_tabs = [
        {
            "label": label,
            "count": count,
            "url": index_url(**{**params, "kind": value}),
            "active": params["kind"] == value,
        }
        for label, value, count in tab_specs
    ]

    titles = crud.list_titles(db, query=q, genre=genre or None, status=watch_status, kind=title_kind, sort=sort)
    # Titles the quick add just put in the fridge (?added=3,7): named in a message and highlighted.
    # Only ids are read from the URL; the names shown come from the database.
    added_ids = [int(part) for part in added.split(",")[:MAX_ADDED] if part.isdigit()]
    added_titles = crud.get_titles(db, added_ids) if added_ids else []
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "titles": titles,
            "stats": stats,
            "open_titles": open_titles,
            "kind_tabs": kind_tabs,
            "genres": genres,
            "status_options": status_options,
            "sort_options": {key: label for key, (label, _) in crud.SORT_OPTIONS.items()},
            "filters": {**params, "sort": sort, "active": bool(q or genre or watch_status)},
            "current_url": index_url(**params),
            "reset_url": index_url(kind=params["kind"]),
            "flash": FLASH_MESSAGES.get(msg),
            "added_titles": added_titles,
            "added_ids": {item.id for item in added_titles},
        },
    )


@router.get("/titles/new", response_class=HTMLResponse, name="new_title")
def new_title(request: Request, kind: str = "") -> HTMLResponse:
    title_kind = parse_choice(Kind, kind) or Kind.MOVIE
    return render_form(request, form={"kind": title_kind.value, "status": Status.PLANNED.value})


@router.post("/titles", name="create_title")
def create_title(
    request: Request, db: DbSession, raw: TitleFormData, poster: PosterFormData, pick: LookupFormData
) -> Response:
    data, image, errors = validate_submission(raw, poster)
    if errors or data is None:
        form = {**raw, "poster_url": poster.url, "lookup_source": pick.source, "lookup_id": pick.source_id}
        return render_form(request, form=form, errors=errors, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    filename = posters.save_poster(*image) if image else None
    try:
        crud.create_title(db, data, poster_filename=filename, online=online_pick(data.kind, pick))
    except Exception:
        posters.delete_poster(filename)  # don't leave an orphaned file behind
        raise
    return redirect("/?msg=created")


@router.get("/titles/{title_id}", response_class=HTMLResponse, name="title_detail")
def title_detail(request: Request, item: ExistingTitle, msg: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "title_detail.html",
        {
            "item": item,
            # Where "Get details" would look: the source it was picked from, else this kind's search.
            "online_source": lookup.source_named(item.kind, item.source) or lookup.source_for(item.kind),
            "flash": FLASH_MESSAGES.get(msg),
            "flash_is_error": msg in ("details_missing", "details_offline"),
        },
    )


@router.get("/titles/{title_id}/edit", response_class=HTMLResponse, name="edit_title")
def edit_title(request: Request, item: ExistingTitle, finished: bool = False) -> HTMLResponse:
    form = form_from_title(item)
    finished = finished and (item.kind.has_episodes or item.kind.has_pages)
    if finished:
        form["status"] = Status.FINISHED.value
        form["finished_on"] = form["finished_on"] or date.today().isoformat()  # just finished: today
    return render_form(request, form=form, item=item, finished=finished)


@router.post("/titles/{title_id}/edit", name="update_title")
def update_title(
    request: Request,
    db: DbSession,
    item: ExistingTitle,
    raw: TitleFormData,
    poster: PosterFormData,
    pick: LookupFormData,
) -> Response:
    data, image, errors = validate_submission(raw, poster)
    if errors or data is None:
        form = {**raw, "poster_url": poster.url, "lookup_source": pick.source, "lookup_id": pick.source_id}
        return render_form(
            request, form=form, errors=errors, item=item, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    old_filename = item.poster_filename
    if image:
        new_filename = posters.save_poster(*image)
    elif poster.remove:
        new_filename = None
    else:
        new_filename = old_filename

    try:
        crud.update_title(db, item, data, poster_filename=new_filename, online=online_pick(data.kind, pick))
    except Exception:
        if new_filename != old_filename:
            posters.delete_poster(new_filename)
        raise
    # Only remove the old file once the database points at the new one.
    if new_filename != old_filename:
        posters.delete_poster(old_filename)
    return redirect(f"/titles/{item.id}?msg=updated")


@router.post("/titles/{title_id}/details", name="fetch_details")
def fetch_details(db: DbSession, item: ExistingTitle) -> RedirectResponse:
    """ "Get details" on a title's page: fill in credits, links and anything missing from the online source."""
    try:
        online = find_online(item)
    except lookup.LookupFailed:
        return redirect(f"/titles/{item.id}?msg=details_offline")
    if online is None:
        return redirect(f"/titles/{item.id}?msg=details_missing")

    filename = None
    image_url = online[1].image_url
    if item.poster_filename is None and image_url:
        try:
            filename = posters.save_poster(*posters.read_poster(io.BytesIO(lookup.fetch_image(image_url))))
        except (lookup.LookupFailed, posters.PosterError):
            pass  # the details are still worth keeping without the image
    try:
        crud.save_online_details(db, item, online, poster_filename=filename)
    except Exception:
        posters.delete_poster(filename)
        raise
    return redirect(f"/titles/{item.id}?msg=details")


@router.post("/titles/{title_id}/delete", name="delete_title")
def delete_title(db: DbSession, item: ExistingTitle) -> RedirectResponse:
    filename = item.poster_filename
    crud.delete_title(db, item)
    posters.delete_poster(filename)
    return redirect("/?msg=deleted")


# --- Episode progress (series only) -----------------------------------------


@router.post("/titles/{title_id}/episodes", name="set_episode")
def set_episode(db: DbSession, item: ExistingSeries, position: Annotated[str, Form()]) -> RedirectResponse:
    """Clicking an episode marks it and everything before it as watched.

    Clicking the last watched episode again un-marks it; "reset" clears all progress.
    """
    if position == "reset":
        new_position = None
    else:
        try:
            season, episode = (int(part) for part in position.split("-", 1))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "That episode doesn't exist.") from None
        if not item.has_episode(season, episode):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "That episode doesn't exist.")
        if (season, episode) == item.progress:
            new_position = item.episode_before(season, episode)
        else:
            new_position = (season, episode)

    crud.set_progress(db, item, new_position)
    return redirect_after_progress(item, f"/titles/{item.id}")


@router.post("/titles/{title_id}/next", name="next_episode")
def mark_next_episode(
    db: DbSession, item: ExistingSeries, return_to: Annotated[str, Form()] = "/"
) -> RedirectResponse:
    """The quick "✓ next episode" button on cards and on the series page."""
    next_episode = item.next_episode
    if next_episode is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You've already watched every episode.")
    crud.set_progress(db, item, next_episode)
    return redirect_after_progress(item, safe_return_path(return_to))


# --- Reading progress (books only) ------------------------------------------


@router.post("/titles/{title_id}/page", name="set_page")
def set_page(
    db: DbSession, item: ExistingBook, current_page: Annotated[int, Form(ge=0, le=MAX_PAGES)]
) -> RedirectResponse:
    """The "I'm on page …" form on a book's page."""
    if item.pages and current_page >= item.pages:
        # Reached the last page: send the user to rate it and mark it read.
        crud.set_current_page(db, item, item.pages)
        return redirect(f"/titles/{item.id}/edit?finished=1")
    crud.set_current_page(db, item, current_page)
    return redirect(f"/titles/{item.id}")
