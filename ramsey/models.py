from pydantic import BaseModel


class SearchQuery(BaseModel):
    search: str


class APISaveMovie(BaseModel):
    identifier: str
