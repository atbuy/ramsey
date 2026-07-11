"""One-off migration of watched movies from redis to sqlite.

Legacy movies have no IMDB ID, so a stable one is derived from the old
identifier instead. The redis data is left untouched, so the migration
is safe to re-run.

Usage: python -m ramsey.migrate
"""

import hashlib
import json
import time

from ramsey.cache import get_redis
from ramsey.db import get_db
from ramsey.settings import get_settings


def main() -> None:
    settings = get_settings()
    redis = get_redis()
    db = get_db()

    cached = redis.get(settings.redis.data_key) or "{}"
    movies = json.loads(cached).get("movies", {})

    migrated = 0
    for identifier, movie in movies.items():
        digest = hashlib.md5(identifier.encode()).hexdigest()[:12]
        movie_id = f"legacy-{digest}"

        query = "SELECT 1 FROM movies WHERE id = ?"
        if db.execute(query, (movie_id,)).fetchone() is not None:
            continue

        # The old identifier stored missing years as the string "None"
        year = movie.get("year")
        if year in (None, "None", ""):
            year = None

        stored_at = float(movie.get("stored_at") or time.time())
        db.execute(
            "INSERT INTO movies (id, title, year, people, image, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                movie_id,
                movie["title"],
                year,
                movie.get("people", ""),
                movie.get("image", ""),
                stored_at,
            ),
        )

        # The exact watch dates are unknown, so every watch gets the stored date
        times_watched = max(int(movie.get("times_watched") or 1), 1)
        for _ in range(times_watched):
            db.execute(
                "INSERT INTO watches (movie_id, watched_at) VALUES (?, ?)",
                (movie_id, stored_at),
            )

        migrated += 1

    db.commit()
    print(f"Migrated {migrated} of {len(movies)} movies (rest already migrated).")


if __name__ == "__main__":
    main()
