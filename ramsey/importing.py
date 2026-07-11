"""Import a library from a Ramsey export or from IMDB / Letterboxd CSVs.

Imports only ever add: existing movies are kept as they are, and watch
events are deduplicated by their exact time, so re-importing the same
file is safe.
"""

import csv
import hashlib
import io
import json
from datetime import datetime

from ramsey import db

PLACEHOLDER_IMAGE = "/static/images/no_image.webp"

# IMDB exports write the title type with varying spelling across formats
IMDB_TYPES = {
    "movie": "movie",
    "tvseries": "tvSeries",
    "tvminiseries": "tvMiniSeries",
    "tvmovie": "tvMovie",
    "tvspecial": "tvSpecial",
    "tvepisode": "tvEpisode",
    "tvshort": "short",
    "short": "short",
    "video": "video",
    "videogame": "videoGame",
    "musicvideo": "musicVideo",
}


def parse_timestamp(value: str | None) -> float | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return None


def import_file(filename: str, content: bytes) -> str:
    """Import an uploaded file, detecting its format from the content."""

    text = content.decode("utf-8-sig", errors="replace")

    if text.lstrip().startswith("{"):
        added, watches, skipped = import_ramsey(json.loads(text))
    else:
        reader = csv.DictReader(io.StringIO(text))
        headers = set(reader.fieldnames or [])
        if "Const" in headers:
            added, watches, skipped = import_imdb(reader)
        elif "Letterboxd URI" in headers:
            added, watches, skipped = import_letterboxd(reader, filename, headers)
        else:
            raise ValueError("Unrecognized file format")

    return f"Imported {added} titles and {watches} watches, skipped {skipped}"


def import_ramsey(data: dict) -> tuple[int, int, int]:
    """Restore movies from a Ramsey JSON export."""

    added = watches = skipped = 0
    for movie in data.get("movies", []):
        if db.get_movie(movie["id"]) is not None:
            skipped += 1
            continue

        db.insert_movie(
            {
                "id": movie["id"],
                "title": movie["title"],
                "type": movie.get("type"),
                "year": movie.get("year"),
                "people": movie.get("people") or "",
                "image": movie.get("image") or PLACEHOLDER_IMAGE,
            },
            parse_timestamp(movie.get("added_at")),
        )
        added += 1

        if movie.get("rating"):
            db.set_rating(movie["id"], int(movie["rating"]))
        if movie.get("notes"):
            db.set_notes(movie["id"], movie["notes"])
        for watch in movie.get("watches", []):
            db.add_watch(movie["id"], parse_timestamp(watch))
            watches += 1

    return added, watches, skipped


def import_imdb(reader: csv.DictReader) -> tuple[int, int, int]:
    """Import an IMDB ratings or watchlist CSV export.

    Rated rows count as watched on the rating date;
    unrated rows go to the watchlist.
    """

    added = watches = skipped = 0
    for row in reader:
        movie_id = (row.get("Const") or "").strip()
        if not movie_id.startswith("tt") or db.get_movie(movie_id) is not None:
            skipped += 1
            continue

        type_key = (row.get("Title Type") or "").replace(" ", "").replace("-", "")
        added_at = parse_timestamp(row.get("Created") or row.get("Date Rated"))
        db.insert_movie(
            {
                "id": movie_id,
                "title": row.get("Title") or movie_id,
                "type": IMDB_TYPES.get(type_key.lower()),
                "year": (row.get("Year") or "").strip() or None,
                "people": (row.get("Directors") or "").strip(),
                "image": PLACEHOLDER_IMAGE,
            },
            added_at,
        )
        added += 1

        rating = (row.get("Your Rating") or "").strip()
        if rating.isdigit():
            db.set_rating(movie_id, max(1, min(10, int(rating))))
            db.add_watch(movie_id, parse_timestamp(row.get("Date Rated")) or added_at)
            watches += 1

    return added, watches, skipped


def import_letterboxd(
    reader: csv.DictReader,
    filename: str,
    headers: set[str],
) -> tuple[int, int, int]:
    """Import a Letterboxd CSV (diary, watched, ratings, reviews or watchlist).

    Letterboxd exports have no IMDB IDs, so movies get a stable derived
    one; running "python -m ramsey.backfill" afterwards resolves their
    type, poster and people. Watchlist exports share their columns with
    watched.csv, so they are recognized by the file name.
    """

    watchlist_file = "watchlist" in (filename or "").lower()

    added = watches = skipped = 0
    for row in reader:
        title = (row.get("Name") or "").strip()
        if not title:
            skipped += 1
            continue

        year = (row.get("Year") or "").strip() or None
        digest = hashlib.md5(f"{title}|{year}".lower().encode()).hexdigest()[:12]
        movie_id = f"lb-{digest}"
        added_at = parse_timestamp(row.get("Date"))

        created = False
        if db.get_movie(movie_id) is None:
            db.insert_movie(
                {
                    "id": movie_id,
                    "title": title,
                    "type": None,
                    "year": year,
                    "people": "",
                    "image": PLACEHOLDER_IMAGE,
                },
                added_at,
            )
            added += 1
            created = True

        rating = (row.get("Rating") or "").strip()
        if rating:
            # Letterboxd rates with 0.5-5 stars
            db.set_rating(movie_id, max(1, min(10, round(float(rating) * 2))))

        review = (row.get("Review") or "").strip()
        if review:
            db.set_notes(movie_id, review)

        watched = False
        if not watchlist_file:
            stamp = parse_timestamp(row.get("Watched Date")) or added_at
            if stamp is None or not db.has_watch(movie_id, stamp):
                db.add_watch(movie_id, stamp)
                watches += 1
                watched = True

        if not created and not watched:
            skipped += 1

    return added, watches, skipped
