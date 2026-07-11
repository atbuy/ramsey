"""Backfill the type of movies saved before types were stored.

Queries the suggestion API with each movie's IMDB ID. Safe to re-run;
movies that already have a type or have no IMDB ID are skipped.

Usage: python -m ramsey.backfill
"""

from ramsey.db import get_db
from ramsey.parsing import search_query


def main() -> None:
    db = get_db()
    rows = db.execute(
        "SELECT id FROM movies WHERE type IS NULL AND id LIKE 'tt%'"
    ).fetchall()

    updated = 0
    for row in rows:
        results = search_query(row["id"])
        match = next((m for m in results if m["id"] == row["id"]), None)
        if match is None or not match["type"]:
            print(f"Could not resolve {row['id']}, skipping.")
            continue

        query = "UPDATE movies SET type = ? WHERE id = ?"
        db.execute(query, (match["type"], row["id"]))
        updated += 1

    db.commit()
    print(f"Backfilled the type of {updated} of {len(rows)} movies.")


if __name__ == "__main__":
    main()
