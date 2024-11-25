from pydantic import BaseModel


class SearchQuery(BaseModel):
    search: str
