# agents/writer.py
from typing import Any, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field
from tenacity import RetryCallState, retry, stop_after_attempt, wait_exponential

from agents.state import FeedbackModel, FewShotContext, RawNewsItem, SlideContent
from api.config import settings


class SlideDeck(BaseModel):
    """Wrapper model to satisfy LangChain/OpenAI structured output requirements."""

    slides: list[SlideContent] = Field(
        description="The sequence of slides making up the carousel."
    )


def log_retry(retry_state: RetryCallState) -> None:
    """Logs the retry attempt in structured JSON format before sleeping."""
    outcome = retry_state.outcome
    error_msg = (
        str(outcome.exception()) if outcome and outcome.failed else "Unknown error"
    )

    logger.warning(
        {
            "event": "writer_llm_retry",
            "attempt": retry_state.attempt_number,
            "error": error_msg,
        }
    )


class WriterAgent:
    def __init__(self) -> None:
        # Initialize OpenAI with strict Pydantic schema enforcement
        # gpt-4o-mini is cost-effective and highly capable of structured generation
        # Explicit type casting for LangChain dynamic methods
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY,
        )
        self.llm: Any = llm.with_structured_output(SlideDeck)  # type: ignore[reportUnknownMemberType]

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert copywriter for LinkedIn and Instagram carousels.
                    Your Brand Voice: {brand_voice}
                    Analyze these successful past posts to understand the style:
                    {examples}

                    Task: Create a 5-7 slide carousel.
                    - Slide 1: Hook (one powerful statement, question, or statistic).
                    - Slides 2 to N-1: Core body (one distinct idea per slide, 3-5 lines max).
                    - Final Slide: CTA (Call to action).

                    {revision_context}

                    For keywords, wrap them exactly in <keyword> tags. Example: We leverage <keyword>AI automation</keyword> to scale.
                    Ensure char_count accurately reflects the length of the body_text.
                    Output STRICTLY as the requested JSON schema.""",
                ),
                ("user", "Topic: {topic}\n\nContext/News:\n{news_text}"),
            ]
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=log_retry,
    )
    async def generate(
        self,
        topic: str,
        news: RawNewsItem,
        context: FewShotContext,
        draft_slides: list[SlideContent] | None = None,
        feedback: FeedbackModel | None = None,
    ) -> list[SlideContent]:
        """
        Executes the prompt against the LLM.
        Operates in 'creation' mode or 'edit' mode depending on provided feedback.
        Retries up to 3 times on API or parsing failures.
        """
        examples_str = (
            "\n---\n".join(context.examples)
            if context.examples
            else "No specific examples provided."
        )

        # Determine if we are in Edit Mode based on feedback
        revision_context = ""
        if draft_slides and feedback:
            slides_text = "\n".join(
                [
                    f"Slide {s.position}: {s.title or 'No Title'} - {s.body_text}"
                    for s in draft_slides
                ]
            )
            revision_context = f"""
            CRITICAL INSTRUCTION: YOU ARE IN EDIT MODE.
            The Reviewer Agent rejected the previous draft. You MUST fix the issues below.

            PREVIOUS DRAFT:
            {slides_text}

            REVIEWER FEEDBACK (REVISION INSTRUCTIONS):
            {feedback.revision_instructions}

            Apply these corrections precisely while maintaining the overall structure.
            """

        chain: Any = self.prompt | self.llm

        # Await the async invocation to prevent event loop blocking
        raw_deck = await chain.ainvoke(
            {
                "brand_voice": context.brand_voice_summary,
                "examples": examples_str,
                "topic": topic,
                "news_text": news.text,
                "revision_context": revision_context,
            }
        )

        # Enforce strict type bounding for Pylance and extract the list
        deck = cast(SlideDeck, raw_deck)
        slides = deck.slides

        logger.info(
            {
                "event": "writer_generation_success",
                "slides_generated": len(slides),
                "is_revision": bool(revision_context),
                "topic": topic,
            }
        )
        return slides
