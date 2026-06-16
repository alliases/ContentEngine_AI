# agents/state.py

from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel


class RawNewsItem(BaseModel):
    title: str
    text: str
    source: str
    url: str
    published_at: datetime
    relevance_score: float = 0.0


class FewShotContext(BaseModel):
    examples: list[str]
    similarity_scores: list[float]
    brand_voice_summary: str


class SlideContent(BaseModel):
    position: int
    title: str | None
    body_text: str
    keywords: list[str]
    char_count: int


class FeedbackModel(BaseModel):
    overall_status: Literal["APPROVED", "NEEDS_REVISION"]
    brand_voice_score: float
    cliche_violations: list[str]
    length_errors: list[str]
    structural_issues: list[str]
    revision_instructions: str


class CarouselState(TypedDict):
    """
    Single Source of Truth for the LangGraph execution.
    Passed between all nodes during the carousel generation lifecycle.
    """

    carousel_id: str
    tenant_id: str
    raw_news: RawNewsItem | None
    rag_context: FewShotContext | None
    draft_slides: list[SlideContent] | None
    feedback: FeedbackModel | None
    iteration_count: int  # CRITICAL: Ensures Actor-Critic loop terminates
    status: Literal[
        "WRITING",
        "REVIEWING",
        "APPROVED_BY_AI",
        "NEEDS_REVISION",
        "FALLBACK",
        "RENDERING",
    ]
    error_message: str | None
