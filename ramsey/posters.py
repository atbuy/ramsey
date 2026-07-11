"""Store movie posters locally, so pages never load them from the CDN."""

import requests

from ramsey import db
from ramsey.settings import get_settings

# Wide enough to stay sharp on high density screens at card size
STORED_WIDTH = 500


def resize_url(url: str, width: int = STORED_WIDTH) -> str:
    """Get a poster URL resized by the IMDB image CDN.

    The stored URL keeps the original resolution; the size is only a
    rendering choice, so nothing is lost. Other images pass through.
    """

    if "._V1_." in url:
        return url.replace("._V1_.", f"._V1_UX{width}_.")

    return url


def fetch(movie_id: str) -> bool:
    """Download and store the poster of a movie. Best effort."""

    movie = db.get_movie(movie_id)
    if movie is None:
        return False

    url = resize_url(movie["image"])
    if not url.startswith("http"):
        return False

    settings = get_settings()
    try:
        response = requests.get(
            url,
            headers={"User-Agent": settings.user_agent},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return False

    content_type = response.headers.get("content-type", "image/jpeg")
    if not content_type.startswith("image/"):
        return False

    db.set_poster(movie_id, response.content, content_type)
    return True
