from typing import TypedDict

import requests
from bs4 import BeautifulSoup

from ramsey.settings import get_settings


class MovieData(TypedDict):
    title: str
    year: str | None
    people: str
    image: str


def search_query(query: str) -> list[MovieData]:
    """Send query and parse response with movie data."""

    settings = get_settings()

    headers = {"User-Agent": settings.user_agent}
    url = f"{settings.query_url}{query}"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "lxml")
    result = soup.find("section", attrs={"data-testid": "find-results-section-title"})

    if result is None:
        print("Could not find results.")
        return []

    results = []

    first = result.find("li")
    if first is not None:
        results.append(first)

    try:
        second = first.find_next_sibling("li")
    except Exception:
        second = None
    else:
        results.append(second)

    try:
        third = second.find_next_sibling("li")
    except Exception:
        third = None
    else:
        results.append(third)

    try:
        fourth = third.find_next_sibling("li")
    except Exception:
        fourth = None
    else:
        results.append(fourth)

    try:
        fifth = fourth.find_next_sibling("li")
    except Exception:
        fifth = None
    else:
        results.append(fifth)

    out = []
    for result in results:
        # Get source image from host
        image_element = result.find("img")
        image = "/static/images/no_image.webp"
        if image_element is not None:
            image = str(image_element["src"])

        title = str(result.find("a").text)

        metadata = result.find("ul")
        year = str(metadata.find("li").text)
        if not year.isdigit():
            people = year
            year = None
        else:
            people = str(metadata.find_next_sibling("ul").text)

        data = {"title": title, "year": year, "people": people, "image": image}
        out.append(data)

    return out
