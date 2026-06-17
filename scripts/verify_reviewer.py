# scripts/verify_reviewer.py
import asyncio
import sys
import uuid
from datetime import UTC, datetime

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from loguru import logger

from agents.graph import app
from agents.state import CarouselState, FewShotContext, RawNewsItem, SlideContent

load_dotenv()


async def run_verification() -> None:
    logger.configure(
        handlers=[{"sink": sys.stdout, "format": "{message}", "serialize": True}]
    )
    print("--- Starting Human-on-the-Loop & Reviewer Verification ---\n")

    # Mock State with intentional errors
    bad_slides = [
        SlideContent(
            position=1,
            title="Intro",
            body_text="In today's digital landscape, AI is a game-changer. "
            * 6,  # Cliche + length violation (>280)
            keywords=["AI"],
            char_count=320,
        ),
        SlideContent(
            position=2,
            title="No CTA",
            body_text="That's all folks.",
            keywords=[],
            char_count=17,
        ),
    ]

    context = FewShotContext(
        examples=[], similarity_scores=[], brand_voice_summary="Punchy and short."
    )

    mock_news = RawNewsItem(
        title="AI Automation in 2026",
        text="AI agents are now generating highly engaging carousels autonomously.",
        source="TechCrunch",
        url="https://example.com",
        published_at=datetime.now(UTC),
        relevance_score=0.99,
    )

    initial_state: CarouselState = {
        "carousel_id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "raw_news": mock_news,
        "rag_context": context,
        "draft_slides": [slide.model_dump() for slide in bad_slides],
        "feedback": None,
        "render_result": None,
        "iteration_count": 0,
        "status": "REVIEWING",
        "error_message": None,
    }

    # CRITICAL: thread_id required for MemorySaver
    # Explicitly type as RunnableConfig to satisfy Pylance
    config: RunnableConfig = {"configurable": {"thread_id": "test_thread"}}

    print("[1] Invoking graph (Should pause BEFORE reviewer_node)....")
    # Using 'writer' as start to immediately trigger edge to 'reviewer_node'
    # Use underscore '_' to indicate the return value is intentionally ignored
    _ = await app.ainvoke(initial_state, config=config)  # type: ignore[reportUnknownMemberType]

    # Check if graph paused
    current_state_info = app.get_state(config)
    next_node = current_state_info.next
    print(f"\n[2] Graph paused. Next node to execute: {next_node}")

    if "reviewer_node" in next_node:
        print("[3] Human on the loop confirmed. Resuming execution of reviewer_node...")

        # Resume graph by passing None
        final_state = await app.ainvoke(None, config=config)  # type: ignore[reportUnknownMemberType]

        feedback = final_state.get("feedback")
        iteration_count = final_state.get("iteration_count")

        print(
            f"\n[4] Execution Complete. Iteration Count incremented to: {iteration_count}"
        )
        if feedback:
            print(f"Overall Status: {feedback.overall_status}")
            print(f"Cliches Found: {feedback.cliche_violations}")
            print(f"Length Errors: {feedback.length_errors}")
            print(f"Instructions: {feedback.revision_instructions}")
        else:
            print("[ERROR] No feedback generated.")
    else:
        print("[ERROR] Graph did not pause before reviewer_node.")


if __name__ == "__main__":
    asyncio.run(run_verification())
