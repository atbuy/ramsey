from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379
    data_key: str = "RAMSEY-DATA"
    search_prefix: str = "RAMSEY-SEARCH"
    movie_prefix: str = "RAMSEY-MOVIE"
    search_ttl: int = 60 * 60 * 24 * 7


class DatabaseSettings(BaseModel):
    path: str = "ramsey.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAMSEY_", env_nested_delimiter="__")

    redis: RedisSettings = RedisSettings()
    database: DatabaseSettings = DatabaseSettings()
    user_agent: str
    query_url: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
