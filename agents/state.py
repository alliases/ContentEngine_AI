# agents/state.py
from datetime import datetime

from pydantic import BaseModel


class RawNewsItem(BaseModel):
    title: str
    text: str
    source: str
    url: str
    published_at: datetime
    relevance_score: float = 0.0
