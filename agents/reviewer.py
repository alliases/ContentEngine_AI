# agents/reviewer.py
import os
from typing import Any, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import SecretStr
from tenacity import RetryCallState, retry, stop_after_attempt, wait_exponential

from agents.state import FeedbackModel, FewShotContext, SlideContent
from api.config import settings


def log_retry(retry_state: RetryCallState) -> None:
    """Logs the retry attempt in structured JSON format before sleeping."""
    outcome = retry_state.outcome
    error_msg = (
        str(outcome.exception()) if outcome and outcome.failed else "Unknown error"
    )

    logger.warning(
        {
            "event": "reviewer_llm_retry",
            "attempt": retry_state.attempt_number,
            "error": error_msg,
        }
    )


class ReviewerAgent:
    def __init__(self) -> None:
        self.cliches = [
            "In today's digital landscape",
            "Game-changer",
            "Crucial",
            "Tap into",
            "Leverage",
            "It's no secret that",
            "The fact is",
        ]

        # Use Groq if key is available (fast & cheap validation), otherwise fallback to OpenAI
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            llm = ChatGroq(model="llama3-8b-8192", api_key=SecretStr(groq_key))
            self.llm: Any = llm.with_structured_output(FeedbackModel)  # type: ignore[reportUnknownMemberType]
            logger.info({"event": "reviewer_init", "model": "llama3-8b-8192 (Groq)"})
        else:
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY)
            self.llm: Any = llm.with_structured_output(FeedbackModel)  # type: ignore[reportUnknownMemberType]
            logger.info(
                {"event": "reviewer_init", "model": "gpt-4o-mini (OpenAI Fallback)"}
            )

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are the Brand Voice Reviewer.
Your job is to evaluate if the slides match the brand voice and to compile revision instructions.

Brand Voice Guidelines: {brand_voice}

The Python static analyzer has already found the following errors:
Cliches: {cliches}
Length Issues: {lengths}
Structure Issues: {structures}

Based on these hard errors and your evaluation of the tone, generate a structured FeedbackModel.
If ANY static errors exist, or if the tone deviates significantly, you MUST set overall_status to 'NEEDS_REVISION'.
Provide clear `revision_instructions` for the Writer agent to fix these specific issues.""",
                ),
                ("user", "Here are the draft slides:\n{slides_text}"),
            ]
        )

    def _check_cliches(self, text: str) -> list[str]:
        violations: list[str] = []
        lower_text = text.lower()
        for cliche in self.cliches:
            if cliche.lower() in lower_text:
                violations.append(f"Found cliche: '{cliche}'")
        return violations

    def _check_length(self, slides: list[SlideContent]) -> list[str]:
        errors: list[str] = []
        for slide in slides:
            if slide.char_count > 280:
                errors.append(
                    f"Slide {slide.position}: {slide.char_count} chars (max 280)."
                )
        return errors

    def _check_structure(self, slides: list[SlideContent]) -> list[str]:
        errors: list[str] = []
        if not slides:
            return ["No slides provided."]
        # Ensure Slide 1 is Hook/Title focused
        if not slides[0].title and len(slides[0].body_text) > 100:
            errors.append("Slide 1 lacks a clear hook or is too text-heavy.")
        # Ensure CTA on last slide (basic check)
        last_slide_text = slides[-1].body_text.lower()
        if (
            "call to action" not in last_slide_text
            and "link" not in last_slide_text
            and "comment" not in last_slide_text
        ):
            errors.append(
                "Final slide does not appear to have a strong Call to Action (CTA)."
            )
        return errors

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=log_retry,
    )
    async def review(
        self, slides: list[SlideContent], context: FewShotContext
    ) -> FeedbackModel:
        """
        Executes hybrid review: Deterministic Python checks + LLM Voice Analysis.
        Invokes LLM purely asynchronously and catches network errors.
        """
        all_text = " ".join([s.body_text for s in slides])

        # 1. Deterministic Checks
        cliche_errors = self._check_cliches(all_text)
        length_errors = self._check_length(slides)
        structure_errors = self._check_structure(slides)

        slides_str = "\n".join(
            [f"Slide {s.position}: {s.title or ''} - {s.body_text}" for s in slides]
        )

        chain: Any = self.prompt | self.llm

        # 2. Async LLM Invocation for formatting and semantic evaluation
        raw_feedback = await chain.ainvoke(
            {
                "brand_voice": context.brand_voice_summary,
                "cliches": cliche_errors or "None",
                "lengths": length_errors or "None",
                "structures": structure_errors or "None",
                "slides_text": slides_str,
            }
        )
        feedback = cast(FeedbackModel, raw_feedback)

        # Safeguard: Force NEEDS_REVISION if python checks failed, even if LLM hallucinated APPROVED
        has_errors = bool(cliche_errors or length_errors or structure_errors)
        if has_errors and feedback.overall_status == "APPROVED":
            logger.warning(
                {
                    "event": "reviewer_status_override",
                    "reason": "Hard python checks failed but LLM approved.",
                }
            )
            feedback.overall_status = "NEEDS_REVISION"

        logger.info(
            {
                "event": "review_completed",
                "status": feedback.overall_status,
                "score": feedback.brand_voice_score,
            }
        )
        return feedback
