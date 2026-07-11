"""Backfill missing movie data from the suggestion API.

Resolves the title type, poster and people of movies that lack them --
movies saved before types were stored, and movies imported from IMDB or
Letterboxd CSVs. Titles with an IMDB ID are matched exactly; others
(e.g. Letterboxd imports) are matched by title and year. Safe to re-run.

Usage: python -m ramsey.backfill
"""

from ramsey import posters
from ramsey.db import get_db, get_posterless_ids
from ramsey.parsing import MovieData, search_query

PLACEHOLDER_IMAGE = "/static/images/no_image.webp"


def resolve(movie) -> MovieData | None:
    """Find the API result matching a stored movie."""

    if movie["id"].startswith("tt"):
        results = search_query(movie["id"])
        return next((m for m in results if m["id"] == movie["id"]), None)

    results = search_query(movie["title"])
    candidates = [m for m in results if m["title"].lower() == movie["title"].lower()]
    if movie["year"]:
        by_year = [m for m in candidates if (m["year"] or "").startswith(movie["year"])]
        candidates = by_year or candidates

    return candidates[0] if candidates else None


def main() -> None:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM movies WHERE type IS NULL OR image = ? OR people = ''",
        (PLACEHOLDER_IMAGE,),
    ).fetchall()

    updated = 0
    for row in rows:
        match = resolve(row)
        if match is None:
            print(f"Could not resolve {row['title']} ({row['id']}), skipping.")
            continue

        db.execute(
            "UPDATE movies SET type = ?, image = ?, people = ? WHERE id = ?",
            (
                row["type"] or match["type"],
                match["image"] if row["image"] == PLACEHOLDER_IMAGE else row["image"],
                row["people"] or match["people"],
                row["id"],
            ),
        )
        updated += 1

    db.commit()
    print(f"Backfilled {updated} of {len(rows)} movies with missing data.")

    # Download posters that are not stored locally yet
    missing = get_posterless_ids()
    fetched = sum(1 for movie_id in missing if posters.fetch(movie_id))
    print(f"Downloaded {fetched} of {len(missing)} missing posters.")


if __name__ == "__main__":
    main()
