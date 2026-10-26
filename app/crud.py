"""Data-access functions. Routes call these instead of building queries themselves."""

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.catalog import Kind, Status
from app.models import Episode, Season, Title
from app.schemas import TitleIn

# Whitelisted sort options: user input only ever selects a key, never raw SQL.
SORT_OPTIONS = {
    "newest": ("Recently added", (Title.created_at.desc(), Title.id.desc())),
    "title": ("Title A–Z", (func.lower(Title.title).asc(),)),
    "title_desc": ("Title Z–A", (func.lower(Title.title).desc(),)),
    "year_desc": ("Year (newest)", (Title.year.desc(), func.lower(Title.title))),
    "year_asc": ("Year (oldest)", (Title.year.asc(), func.lower(Title.title))),
    "rating_desc": ("Rating (highest)", (Title.rating.desc().nulls_last(), func.lower(Title.title))),
    "rating_asc": ("Rating (lowest)", (Title.rating.asc().nulls_last(), func.lower(Title.title))),
}
DEFAULT_SORT = "newest"


@dataclass(frozen=True)
class Stats:
    total: int
    in_progress: int
    finished: int
    dropped: int
    avg_rating: float | None
    by_kind: dict[Kind, int]

    @property
    def planned(self) -> int:
        return self.total - self.in_progress - self.finished - self.dropped


def _like_pattern(text: str) -> str:
    """Escape LIKE wildcards so a search for '100%' matches literally."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_titles(
    db: Session,
    *,
    query: str = "",
    genre: str | None = None,
    status: Status | None = None,
    kind: Kind | None = None,
    sort: str = DEFAULT_SORT,
) -> list[Title]:
    stmt = select(Title)
    if query:
        pattern = _like_pattern(query)
        stmt = stmt.where(or_(Title.title.ilike(pattern, escape="\\"), Title.author.ilike(pattern, escape="\\")))
    if genre:
        stmt = stmt.where(Title.genre == genre)
    if status:
        stmt = stmt.where(Title.status == status)
    if kind:
        stmt = stmt.where(Title.kind == kind)
    _, order_by = SORT_OPTIONS.get(sort, SORT_OPTIONS[DEFAULT_SORT])
    return list(db.scalars(stmt.order_by(*order_by)))


def get_title(db: Session, title_id: int) -> Title | None:
    return db.get(Title, title_id)


def _sync_seasons(item: Title, episode_counts: list[int]) -> None:
    """Update seasons in place rather than replacing the list.

    Replacing would insert the new rows before deleting the old ones,
    which breaks the unique (title_id, number) constraint.
    """
    for season, count in zip(item.seasons, episode_counts):
        season.episode_count = count
    for number in range(len(item.seasons) + 1, len(episode_counts) + 1):
        item.seasons.append(Season(number=number, episode_count=episode_counts[number - 1]))
    del item.seasons[len(episode_counts):]


def create_title(db: Session, data: TitleIn, poster_filename: str | None = None) -> Title:
    item = Title(**data.model_dump(exclude={"seasons"}), poster_filename=poster_filename)
    _sync_seasons(item, data.seasons)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_title(db: Session, item: Title, data: TitleIn, *, poster_filename: str | None) -> Title:
    # poster_filename is required so a caller can't wipe the image by forgetting it.
    for field, value in data.model_dump(exclude={"seasons"}).items():
        setattr(item, field, value)
    _sync_seasons(item, data.seasons)
    item.poster_filename = poster_filename
    db.commit()
    db.refresh(item)
    return item


def set_progress(db: Session, item: Title, position: Episode | None) -> None:
    """Set the last watched episode (None = start over). Ticking off an episode means you're watching."""
    item.progress_season, item.progress_episode = position if position else (None, None)
    if position is not None:
        item.status = Status.IN_PROGRESS
    db.commit()


def set_current_page(db: Session, item: Title, page: int) -> None:
    """Record the page a book is on. Updating the page means you're reading it."""
    item.current_page = page
    item.status = Status.IN_PROGRESS
    db.commit()


def delete_title(db: Session, item: Title) -> None:
    db.delete(item)
    db.commit()


def get_stats(db: Session) -> Stats:
    total, in_progress, finished, dropped, avg_rating = db.execute(
        select(
            func.count(Title.id),
            func.count(Title.id).filter(Title.status == Status.IN_PROGRESS),
            func.count(Title.id).filter(Title.status == Status.FINISHED),
            func.count(Title.id).filter(Title.status == Status.DROPPED),
            func.avg(Title.rating),
        )
    ).one()
    counts = dict(db.execute(select(Title.kind, func.count(Title.id)).group_by(Title.kind)).tuples().all())
    return Stats(
        total=total,
        in_progress=in_progress,
        finished=finished,
        dropped=dropped,
        avg_rating=avg_rating,
        by_kind={kind: counts.get(kind, 0) for kind in Kind},
    )
