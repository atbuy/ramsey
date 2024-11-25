from functools import lru_cache

from redis import Redis

from ramsey.settings import get_settings


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    """Initialize a redis connection."""

    settings = get_settings()

    redis = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        decode_responses=True,
    )

    return redis
