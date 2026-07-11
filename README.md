# ramsey

Movie critic application. Rate and keep track of what movies and shows you have seen.

## Features

- Instant search for movies and shows, backed by the IMDB suggestion API
- Watched library with full watch history: first watched, rewatches, and backfilling past dates
- Watchlist for things you want to see, with a "Pick for me" random suggestion
- Ratings (1-10 stars) and personal notes per title
- Filter the library by movies/shows and sort by recency, rating, watch count, or title
- Stats page: watches per month, rating distribution, and most rewatched titles
- Export the whole library as JSON or CSV
- Four selectable themes: Marquee, VHS '88, Noir, and Chef's Table
- Installable on the phone home screen as a PWA

Built with FastAPI, Jinja2, and HTMX. The library is stored in SQLite;
Redis caches search results.

## Configuration

Create a `.env` file in the project root:

```bash
# Any real browser user agent works; IMDB rejects the default python one
RAMSEY_USER_AGENT='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'

# IMDB search suggestion API
RAMSEY_QUERY_URL=https://v2.sg.media-imdb.com/suggestion/
```

Optional settings and their defaults:

```bash
RAMSEY_REDIS__HOST=localhost      # use "redis" when the app runs inside docker compose
RAMSEY_REDIS__PORT=6379           # the compose redis is mapped to 6378 on the host
RAMSEY_DATABASE__PATH=ramsey.db   # compose.yml overrides this to /data/ramsey.db (volume)
```

## Installation

### Docker

You can install the entire application's stack using the following command:

```bash
docker compose up --build -d
```

After that you should have a web app running at `http://localhost:8000`

### Source

If you only plan on using the application you can install using the following command:

```bash
make install
```

Otherwise if you want to develop the application should use:

```bash
make install-dev
```

To run the application you can simply use:

```bash
make run
```

## Maintenance commands

```bash
# One-off import of watched movies from the old redis storage into sqlite
python -m ramsey.migrate

# Resolve the title type (movie/series/...) of movies saved before types were stored
python -m ramsey.backfill
```

Both are safe to re-run.
