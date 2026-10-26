"""Fill an empty database with sample titles of every kind: `python -m app.seed`."""

from sqlalchemy import func, select

from app import crud
from app.database import SessionLocal, init_db
from app.models import Title
from app.schemas import TitleIn

SAMPLE_TITLES = [
    {"title": "Inception", "year": 2010, "genre": "Sci-Fi", "status": "watched", "rating": 9,
     "description": "A thief who steals secrets through dream-sharing is given a chance at redemption."},
    {"title": "Spirited Away", "year": 2001, "genre": "Animation", "status": "watched", "rating": 10,
     "description": "A young girl wanders into a world ruled by gods, witches and spirits."},
    {"title": "Parasite", "year": 2019, "genre": "Thriller", "status": "watched", "rating": 9,
     "description": "Greed and class discrimination threaten a newly formed bond between two families."},
    {"title": "The Grand Budapest Hotel", "year": 2014, "genre": "Comedy", "status": "watched", "rating": 8,
     "description": "The adventures of a legendary concierge and his trusted lobby boy."},
    {"title": "Mad Max: Fury Road", "year": 2015, "genre": "Action", "status": "watched", "rating": 8,
     "description": "In a post-apocalyptic wasteland, Max teams up with Furiosa to flee a tyrant."},
    {"title": "Seven Samurai", "year": 1954, "genre": "Drama", "status": "watchlist",
     "description": "A village of farmers hires seven samurai to defend them from bandits."},
    {"title": "Arrival", "year": 2016, "genre": "Sci-Fi", "status": "watchlist",
     "description": "A linguist works with the military to communicate with alien visitors."},
    {"title": "Heat", "year": 1995, "genre": "Crime", "status": "watchlist",
     "description": "A detective hunts a professional thief planning one last score."},
    {"kind": "series", "title": "Breaking Bad", "year": 2008, "genre": "Crime", "status": "watched", "rating": 10,
     "seasons": [7, 13, 13, 13, 16],
     "description": "A chemistry teacher turned drug manufacturer builds an empire in New Mexico."},
    {"kind": "series", "title": "Severance", "year": 2022, "genre": "Sci-Fi", "status": "watching",
     "seasons": [9, 10], "progress_season": 2, "progress_episode": 3,
     "description": "Office workers have their memories surgically divided between work and personal lives."},
    {"kind": "series", "title": "Dark", "year": 2017, "genre": "Mystery", "status": "watchlist",
     "seasons": [10, 8, 8],
     "description": "A missing child sets four families on a hunt across generations of a small German town."},
    {"kind": "series", "title": "Lost", "year": 2004, "genre": "Mystery", "status": "dropped",
     "seasons": [25, 24, 23, 14, 18, 18], "progress_season": 3, "progress_episode": 7,
     "description": "Survivors of a plane crash must work together to stay alive on a mysterious island."},
    {"kind": "anime", "title": "Frieren: Beyond Journey's End", "year": 2023, "genre": "Fantasy", "status": "watching",
     "seasons": [28], "progress_season": 1, "progress_episode": 12,
     "description": "An elf mage reflects on life and loss after her hero party's quest has ended."},
    {"kind": "anime", "title": "Attack on Titan", "year": 2013, "genre": "Action", "status": "watched", "rating": 9,
     "seasons": [25, 12, 22, 30],
     "description": "Humanity fights for survival against giant man-eating Titans."},
    {"kind": "game", "title": "Elden Ring", "year": 2022, "genre": "RPG", "status": "watched", "rating": 10,
     "completion": "story_dlc", "hours_played": 160,
     "description": "An open-world action RPG set in the Lands Between."},
    {"kind": "game", "title": "Hollow Knight", "year": 2017, "genre": "Platformer", "status": "watching",
     "hours_played": 22,
     "description": "A hand-drawn adventure through a vast, ruined kingdom of insects."},
    {"kind": "game", "title": "Hades", "year": 2020, "genre": "Action", "status": "watched", "rating": 9,
     "completion": "full", "hours_played": 95,
     "description": "A rogue-like dungeon crawler about escaping the Underworld."},
    {"kind": "book", "title": "Project Hail Mary", "author": "Andy Weir", "year": 2021, "genre": "Sci-Fi",
     "status": "watched", "rating": 9, "pages": 476,
     "description": "A lone astronaut wakes up with no memory and a mission to save Earth."},
    {"kind": "book", "title": "The Name of the Wind", "author": "Patrick Rothfuss", "year": 2007, "genre": "Fantasy",
     "status": "watching", "pages": 662, "current_page": 240,
     "description": "The legendary Kvothe tells the true story of his life."},
    {"kind": "book", "title": "Dune", "author": "Frank Herbert", "year": 1965, "genre": "Sci-Fi",
     "status": "watchlist", "pages": 688,
     "description": "A noble family is caught in a struggle for the desert planet Arrakis."},
    {"kind": "game", "title": "Disco Elysium", "year": 2019, "genre": "RPG", "status": "watchlist",
     "description": "A detective RPG where your own mind is your strangest companion."},
]


def main() -> None:
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(func.count(Title.id))):
            print("Database already has titles — nothing to do.")
            return
        for sample in SAMPLE_TITLES:
            crud.create_title(db, TitleIn.model_validate(sample))
        print(f"Added {len(SAMPLE_TITLES)} sample titles.")


if __name__ == "__main__":
    main()
