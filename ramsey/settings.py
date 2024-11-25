from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAMSEY_", env_nested_delimiter="__")

    user_agent: str
    query_url: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
