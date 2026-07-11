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
    type TEXT,
    year TEXT,
    people TEXT NOT NULL DEFAULT '',
    image TEXT NOT NULL DEFAULT '',
    rating INTEGER,
    notes TEXT,
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

    # Add columns missing from databases created with an older schema
    columns = {row[1] for row in db.execute("PRAGMA table_info(movies)")}
    for column in ("notes", "type"):
        if column not in columns:
            db.execute(f"ALTER TABLE movies ADD COLUMN {column} TEXT")
            db.commit()

    return db


def get_movie(movie_id: str) -> sqlite3.Row | None:
    """Get a single stored movie by its identifier."""

    db = get_db()
    query = "SELECT * FROM movies WHERE id = ?"
    return db.execute(query, (movie_id,)).fetchone()


def insert_movie(movie: MovieData, added_at: float | None = None) -> None:
    """Store a new movie."""

    db = get_db()
    query = (
        "INSERT INTO movies (id, title, type, year, people, image, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    values = (
        movie["id"],
        movie["title"],
        movie.get("type"),
        movie["year"],
        movie["people"],
        movie["image"],
        added_at or time.time(),
    )

    db.execute(query, values)
    db.commit()


def has_watch(movie_id: str, watched_at: float) -> bool:
    """Check whether a watch at the exact same time already exists."""

    db = get_db()
    query = "SELECT 1 FROM watches WHERE movie_id = ? AND watched_at = ?"
    return db.execute(query, (movie_id, watched_at)).fetchone() is not None


def add_watch(movie_id: str, watched_at: float | None = None) -> None:
    """Record a watch event for a movie."""

    db = get_db()
    query = "INSERT INTO watches (movie_id, watched_at) VALUES (?, ?)"
    db.execute(query, (movie_id, watched_at or time.time()))
    db.commit()


def get_watches(movie_id: str) -> list[sqlite3.Row]:
    """Get the watch events of a movie, most recent first."""

    db = get_db()
    query = (
        "SELECT id, watched_at FROM watches WHERE movie_id = ? "
        "ORDER BY watched_at DESC, id DESC"
    )

    return db.execute(query, (movie_id,)).fetchall()


def get_watch_times() -> list[float]:
    """Get the timestamps of all watch events."""

    db = get_db()
    rows = db.execute("SELECT watched_at FROM watches").fetchall()

    return [row["watched_at"] for row in rows]


def get_watch(watch_id: int) -> sqlite3.Row | None:
    """Get a single watch event."""

    db = get_db()
    query = "SELECT * FROM watches WHERE id = ?"
    return db.execute(query, (watch_id,)).fetchone()


def delete_watch(watch_id: int) -> None:
    """Delete a single watch event."""

    db = get_db()
    db.execute("DELETE FROM watches WHERE id = ?", (watch_id,))
    db.commit()


def remove_latest_watch(movie_id: str) -> None:
    """Remove the most recent watch event.

    Removing the last one moves the movie to the watchlist.
    """

    db = get_db()
    query = (
        "DELETE FROM watches WHERE id = ("
        "  SELECT id FROM watches WHERE movie_id = ?"
        "  ORDER BY watched_at DESC, id DESC LIMIT 1"
        ")"
    )

    db.execute(query, (movie_id,))
    db.commit()


def set_notes(movie_id: str, notes: str | None) -> None:
    """Set or clear the notes of a movie."""

    db = get_db()
    db.execute("UPDATE movies SET notes = ? WHERE id = ?", (notes, movie_id))
    db.commit()


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


def get_saved_ids() -> set[str]:
    """Get the identifiers of all stored movies."""

    db = get_db()
    rows = db.execute("SELECT id FROM movies").fetchall()

    return {row["id"] for row in rows}


def get_watched_ids() -> set[str]:
    """Get the identifiers of movies with at least one watch."""

    db = get_db()
    rows = db.execute("SELECT DISTINCT movie_id FROM watches").fetchall()

    return {row["movie_id"] for row in rows}


def get_movies() -> list[dict]:
    """Get all movies with their watch dates, most recently watched first."""

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
