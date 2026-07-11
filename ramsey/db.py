import sqlite3
import time
from functools import lru_cache
from pathlib import Path

from ramsey.parsing import MovieData
from ramsey.settings import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS movies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year TEXT,
    people TEXT NOT NULL DEFAULT '',
    image TEXT NOT NULL DEFAULT '',
    rating INTEGER,
    added_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id TEXT NOT NULL REFERENCES movies (id) ON DELETE CASCADE,
    watched_at REAL NOT NULL
);
"""


@lru_cache(maxsize=1)
def get_db() -> sqlite3.Connection:
    """Initialize the sqlite connection and create the schema."""

    settings = get_settings()

    path = Path(settings.database.path)
    path.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)

    return db


def get_movie(movie_id: str) -> sqlite3.Row | None:
    """Get a single stored movie by its identifier."""

    db = get_db()
    query = "SELECT * FROM movies WHERE id = ?"
    return db.execute(query, (movie_id,)).fetchone()


def insert_movie(movie: MovieData) -> None:
    """Store a new movie."""

    db = get_db()
    query = (
        "INSERT INTO movies (id, title, year, people, image, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    values = (
        movie["id"],
        movie["title"],
        movie["year"],
        movie["people"],
        movie["image"],
        time.time(),
    )

    db.execute(query, values)
    db.commit()


def add_watch(movie_id: str, watched_at: float | None = None) -> None:
    """Record a watch event for a movie."""

    db = get_db()
    query = "INSERT INTO watches (movie_id, watched_at) VALUES (?, ?)"
    db.execute(query, (movie_id, watched_at or time.time()))
    db.commit()


def count_watches(movie_id: str) -> int:
    """Count how many times a movie has been watched."""

    db = get_db()
    query = "SELECT COUNT(*) FROM watches WHERE movie_id = ?"
    row = db.execute(query, (movie_id,)).fetchone()

    return int(row[0])


def remove_latest_watch(movie_id: str) -> bool:
    """Remove the most recent watch event, always keeping the first one."""

    if count_watches(movie_id) <= 1:
        return False

    db = get_db()
    query = (
        "DELETE FROM watches WHERE id = ("
        "  SELECT id FROM watches WHERE movie_id = ?"
        "  ORDER BY watched_at DESC, id DESC LIMIT 1"
        ")"
    )

    db.execute(query, (movie_id,))
    db.commit()

    return True


def set_rating(movie_id: str, rating: int | None) -> None:
    """Set or clear the rating of a movie."""

    db = get_db()
    db.execute("UPDATE movies SET rating = ? WHERE id = ?", (rating, movie_id))
    db.commit()


def delete_movie(movie_id: str) -> None:
    """Delete a movie and all of its watch events."""

    db = get_db()
    db.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
    db.commit()


def get_watched() -> list[dict]:
    """Get all watched movies with their watch dates, most recently watched first."""

    db = get_db()
    movies = db.execute("SELECT * FROM movies").fetchall()
    watches = db.execute(
        "SELECT movie_id, watched_at FROM watches ORDER BY watched_at, id"
    ).fetchall()

    # Group the watch dates of each movie, oldest first
    dates: dict[str, list[float]] = {}
    for watch in watches:
        dates.setdefault(watch["movie_id"], []).append(watch["watched_at"])

    out = []
    for movie in movies:
        entry = dict(movie)
        entry["watch_dates"] = dates.get(movie["id"], [])
        out.append(entry)

    out.sort(key=lambda m: max(m["watch_dates"], default=m["added_at"]), reverse=True)

    return out
