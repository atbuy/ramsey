from typing import TypedDict
from urllib.parse import quote

import requests

from ramsey.settings import get_settings


class MovieData(TypedDict):
    id: str
    title: str
    year: str | None
    people: str
    image: str


def search_query(query: str) -> list[MovieData]:
    """Send query to the suggestion API and parse the movie data."""

    settings = get_settings()

    # The API nests results under the first character of the query
    term = query.strip().lower()
    url = f"{settings.query_url}{term[0]}/{quote(term)}.json"
    headers = {"User-Agent": settings.user_agent}

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Search failed with status {response.status_code}.")
        return []

    out: list[MovieData] = []
    for item in response.json().get("d", []):
        # Skip results that are not titles (e.g. people)
        if not str(item.get("id", "")).startswith("tt"):
            continue

        image = "/static/images/no_image.webp"
        if "i" in item:
            image = item["i"]["imageUrl"]

        # Shows have a year range (e.g. "2008-2013"), movies a single year
        year = item.get("yr") or item.get("y")

        data: MovieData = {
            "id": item["id"],
            "title": item["l"],
            "year": str(year) if year else None,
            "people": item.get("s", ""),
            "image": image,
        }
        out.append(data)

        if len(out) == 5:
            break

    return out
