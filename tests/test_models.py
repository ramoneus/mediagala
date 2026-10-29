"""Episode and reading progress, worked out from the stored bookmark."""

from app.catalog import Kind, Status
from app.models import Season, Title


def series(progress=None) -> Title:
    """A two-season series (3 + 2 episodes) with the given last watched episode."""
    season, episode = progress or (None, None)
    return Title(
        kind=Kind.SERIES,
        seasons=[Season(number=1, episode_count=3), Season(number=2, episode_count=2)],
        progress_season=season,
        progress_episode=episode,
    )


def test_not_started():
    item = series()
    assert item.total_episodes == 5
    assert item.watched_episodes == 0
    assert item.progress_percent == 0
    assert item.next_episode == (1, 1)


def test_end_of_a_season_moves_to_the_next_one():
    item = series((1, 3))
    assert item.watched_episodes == 3
    assert item.progress_percent == 60
    assert item.next_episode == (2, 1)
    assert item.watched_in_season(1) == 3
    assert item.watched_in_season(2) == 0


def test_everything_watched():
    item = series((2, 2))
    assert item.next_episode is None
    assert item.progress_percent == 100


def test_episodes_up_to_the_bookmark_count_as_watched():
    item = series((2, 1))
    assert item.is_episode_watched(1, 3)
    assert item.is_episode_watched(2, 1)
    assert not item.is_episode_watched(2, 2)


def test_episode_before_crosses_seasons():
    item = series()
    assert item.episode_before(2, 1) == (1, 3)
    assert item.episode_before(1, 2) == (1, 1)
    assert item.episode_before(1, 1) is None


def test_has_episode_bounds():
    item = series()
    assert item.has_episode(2, 2)
    assert not item.has_episode(2, 3)
    assert not item.has_episode(3, 1)
    assert not item.has_episode(0, 1)


def test_reading_percent():
    assert Title(pages=None, current_page=10).reading_percent == 0
    assert Title(pages=200, current_page=50).reading_percent == 25
    assert Title(pages=200, current_page=250).reading_percent == 100


def test_status_label_depends_on_kind():
    assert Title(kind=Kind.GAME, status=Status.FINISHED).status_label == "Completed"
    assert Title(kind=Kind.BOOK, status=Status.IN_PROGRESS).status_label == "Reading"
    assert Title(kind=Kind.MOVIE, status=Status.PLANNED).status_label == "Watchlist"
